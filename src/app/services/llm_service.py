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

    def generate_image_prompt(
        self,
        part_name: str,
        face_count: int,
        surface_types: list[str],
        color_hex: str | None,
        length: float,
        width: float,
        height: float,
        sequence: int,
        total_steps: int,
        step_title: str,
    ) -> str | None:
        """调用 LLM 生成图片 Prompt（英文，用于 Seedream img2img）。

        返回 None 表示 LLM 不可用或失败，由调用方使用 prompt_builder fallback。
        """
        if self._client is None:
            return None

        surfaces = "、".join(surface_types) if surface_types else "未知"
        color_desc = f"颜色为 {color_hex}" if color_hex else "金属银灰色"

        prompt = f"""你是一个 CAD 渲染专家。请为以下机械零件生成一段英文 Prompt，用于 AI 图片生成模型（Seedream）。

零件信息：
- 零件类型：{part_name}
- 面数：{face_count}
- 曲面类型：{surfaces}
- 尺寸：{length:.1f} x {width:.1f} x {height:.1f} mm
- {color_desc}
- 装配步骤：第 {sequence}/{total_steps} 步：{step_title}

要求：
1. 用英文描述，适合 AI 图片生成模型
2. 包含：形状描述、尺寸比例、颜色、材质、视角、装配上下文
3. 风格：技术工程插图，白色背景，专业打光
4. 只返回 Prompt 文本，不要 JSON，不要 markdown 代码块
5. 控制在 100-150 词"""

        try:
            response = self._client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            result = response.choices[0].message.content.strip()
            # 去除 markdown 代码块
            if result.startswith("```"):
                result = result.split("\n", 1)[-1]
                if result.endswith("```"):
                    result = result[:-3]
                result = result.strip()
            if len(result) > 20:
                from ..logger import logger
                logger.info(f"LLM 生成图片 Prompt：{result[:80]}...")
                return result
            return None
        except Exception as e:
            from ..logger import logger
            logger.warning(f"[LLM → Prompt 模板切换] LLM 生成 Prompt 失败（{type(e).__name__}: {e}），使用规则模板")
            return None

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
        except Exception as e:
            from ..logger import logger
            logger.warning(f"[LLM → 模板切换] LLM 调用失败（{type(e).__name__}: {e}），已自动切换到中文模板生成步骤文本")
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
