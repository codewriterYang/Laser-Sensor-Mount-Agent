"""LLM Service — OpenAI-compatible 文本生成。

默认调用火山引擎上的 DeepSeek 模型。
未配置 API key 时使用中文模板。
"""

from __future__ import annotations

import json

from openai import OpenAI

from .. import config
from ..models.schemas import StepSchema


class LLMService:
    """通过 LLM 生成自然语言装配步骤描述。

    未配置 LLM_API_KEY 时，使用中文模板生成。
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
        """生成单个装配步骤描述。

        配置了 LLM 时调用 API，否则使用中文模板。
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
        """调用 LLM 生成中文步骤文本。"""
        import uuid

        material_hint = f"（材质：{part_material}）" if part_material else ""

        relation_map = {
            "contains": "安装在装配体上",
            "attached_to": "连接固定",
            "fastened_by": "紧固件锁定",
        }
        relation_desc = relation_map.get(relation, "安装")

        prompt = f"""你正在为工厂装配工人编写装配指导书的步骤文本。请使用简体中文。

上下文：
- 需要安装的零件：{part_name}{material_hint}
- 步骤编号：第 {sequence} 步
- 关系类型：{relation_desc}
- 安装到 / 与之配合的零件：{target_name or "装配底座"}

装配规则（请严格遵守）：
- 底座 / 底板类零件最先安装
- 支架 / 安装座类零件其次
- 传感器在支架安装完成后安装
- 螺丝 / 螺栓等紧固件靠后安装
- 垫片必须紧跟在对应的紧固件之后

请只返回一个 JSON 对象（不要 markdown 代码块），包含以下字段：
{{"title": "简短的中文祈使句标题，例如：安装底板", "description": "一到两句话描述操作步骤，如有材质信息请提及", "requiredTools": ["所需工具名称列表，如：六角扳手"]}}"""

        try:
            response = self._client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            raw = response.choices[0].message.content.strip()

            # 去除可能的 markdown 代码块标记
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            data = json.loads(raw)
            return StepSchema(
                stepId=uuid.uuid4(),
                sequence=sequence,
                title=data.get("title", f"安装 {part_name}"),
                description=data.get("description", f"将 {part_name} 安装到 {target_name} 上"),
                requiredParts=[part_name] + ([target_name] if target_name else []),
                requiredTools=data.get("requiredTools", []),
            )
        except Exception:
            # LLM 出错时回退到模板
            return self._template_step(part_name, part_material, relation, target_name, sequence)

    def _template_step(
        self,
        part_name: str,
        part_material: str,
        relation: str,
        target_name: str,
        sequence: int,
    ) -> StepSchema:
        """中文模板（LLM 不可用时的回退方案）。"""
        import uuid

        material_suffix = f"（{part_material}）" if part_material else ""

        if relation == "fastened_by":
            title = f"紧固 {part_name}"
            if target_name:
                description = f"使用 {part_name}{material_suffix} 将 {target_name} 锁紧固定，确保扭矩符合要求"
            else:
                description = f"用 {part_name}{material_suffix} 进行紧固，确保连接牢固可靠"
            tools = ["六角扳手", "扭矩扳手"]
        elif relation == "attached_to":
            title = f"安装 {part_name}"
            if target_name:
                description = f"将 {part_name}{material_suffix} 安装固定到 {target_name} 上，对齐定位孔"
            else:
                description = f"安装 {part_name}{material_suffix}，确保位置准确"
            tools = ["六角扳手"]
        else:
            title = f"安装 {part_name}"
            description = f"将 {part_name}{material_suffix} 放置到位，作为装配的基础组件"
            tools = []

        return StepSchema(
            stepId=uuid.uuid4(),
            sequence=sequence,
            title=title,
            description=description,
            requiredParts=[part_name] + ([target_name] if target_name else []),
            requiredTools=tools,
        )
