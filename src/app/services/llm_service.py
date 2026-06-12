"""LLM Service — OpenAI-compatible text generation.

Calls deepseek-v4-flash on Volcano Engine by default.
Falls back to rule-based templates when no API key is configured.
"""

from __future__ import annotations

import json

from openai import OpenAI

from .. import config
from ..models.schemas import StepSchema


class LLMService:
    """Generate natural-language assembly step descriptions via LLM.

    When LLM_API_KEY is not configured, falls back to template-based generation.
    """

    def __init__(self):
        self._client: OpenAI | None = None
        if config.is_llm_configured():
            self._client = OpenAI(
                base_url=config.LLM_BASE_URL,
                api_key=config.LLM_API_KEY,
            )

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @property
    def model_name(self) -> str:
        return config.LLM_MODEL

    def generate_step(
        self,
        part_name: str,
        part_material: str,
        relation: str,
        target_name: str,
        sequence: int,
    ) -> StepSchema:
        """Generate a single assembly step description.

        Uses LLM when configured; otherwise falls back to template.
        """
        if self._client is not None:
            return self._llm_step(part_name, part_material, relation, target_name, sequence)
        return self._template_step(part_name, part_material, relation, target_name, sequence)

    def _llm_step(
        self,
        part_name: str,
        part_material: str,
        relation: str,
        target_name: str,
        sequence: int,
    ) -> StepSchema:
        """Call LLM to generate step text."""
        import uuid

        material_hint = f" (material: {part_material})" if part_material else ""

        prompt = f"""You are generating an assembly instruction step for factory workers.

Context:
- Part to install: {part_name}{material_hint}
- Step number: {sequence}
- Relation type: {relation}
- Attached to / interacts with: {target_name or "the assembly base"}

Assembly rules to follow:
- Base / plate parts are placed first
- Fasteners (screws, bolts) are installed near the end
- Washers always follow their matching fastener
- Sensors are mounted after their bracket/mount

Return ONLY a JSON object (no markdown, no code fences) with these exact keys:
{{"title": "short imperative title in English", "description": "one or two sentences describing what to do, mentioning materials if provided", "requiredTools": ["tool names"]}}"""

        try:
            response = self._client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            raw = response.choices[0].message.content.strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            data = json.loads(raw)
            return StepSchema(
                stepId=uuid.uuid4(),
                sequence=sequence,
                title=data.get("title", f"Install {part_name}"),
                description=data.get("description", f"Install {part_name} onto {target_name}"),
                requiredParts=[part_name] + ([target_name] if target_name else []),
                requiredTools=data.get("requiredTools", []),
            )
        except Exception:
            # Fall back to template on any LLM error
            return self._template_step(part_name, part_material, relation, target_name)

    def _template_step(
        self,
        part_name: str,
        part_material: str,
        relation: str,
        target_name: str,
        sequence: int,
    ) -> StepSchema:
        """Template-based fallback when LLM is unavailable."""
        import uuid

        material_suffix = f" ({part_material})" if part_material else ""

        if relation == "fastened_by":
            title = f"Fasten {part_name}"
            if target_name:
                description = f"Secure the {target_name} using {part_name}{material_suffix}"
            else:
                description = f"Fasten with {part_name}{material_suffix}"
            tools = ["Hex Wrench", "Torque Wrench"]
        elif relation == "attached_to":
            title = f"Attach {part_name}"
            if target_name:
                description = f"Mount the {part_name} onto the {target_name}{material_suffix}"
            else:
                description = f"Install the {part_name}{material_suffix}"
            tools = ["Hex Wrench"]
        else:
            title = f"Install {part_name}"
            description = f"Place the {part_name}{material_suffix} as the base component"
            tools = []

        return StepSchema(
            stepId=uuid.uuid4(),
            sequence=sequence,
            title=title,
            description=description,
            requiredParts=[part_name] + ([target_name] if target_name else []),
            requiredTools=tools,
        )
