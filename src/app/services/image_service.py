"""图片生成 Service — 步骤描述 → 装配示意图 (Doubao Seedream 4.5)。

使用 OpenAI-compatible images API（火山引擎）。
API 不可用时生成 Pillow 占位图。
"""

from __future__ import annotations

import base64
import uuid
from io import BytesIO
from pathlib import Path

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

from .. import config

IMAGES_DIR = Path("exports/images")


class ImageService:
    """为装配步骤生成示意图。

    优先使用 Doubao Seedream API，失败时使用 Pillow 生成占位图。
    """

    def __init__(self):
        self._client: OpenAI | None = None
        if config.IMAGE_API_KEY and config.IMAGE_API_KEY != "your_api_key_here":
            self._client = OpenAI(
                base_url=config.IMAGE_BASE_URL,
                api_key=config.IMAGE_API_KEY,
            )

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @property
    def api_available(self) -> bool:
        return self._client is not None

    def generate_step_image(self, step_title: str, step_description: str, sequence: int) -> str | None:
        """为一个装配步骤生成示意图。返回文件路径。未配置 API 时跳过。"""
        if not self._client:
            return None  # 测试模式下跳过

        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        image_path = IMAGES_DIR / f"step_{sequence}_{uuid.uuid4().hex[:8]}.png"

        # 先尝试 API
        result = self._api_generate(step_title, step_description, sequence, image_path)
        if result:
            return result

        # 回退到 Pillow 生成的示意图
        return self._fallback_diagram(step_title, step_description, sequence, image_path)

    def _api_generate(self, title: str, desc: str, seq: int, path: Path) -> str | None:
        """调用 Doubao Seedream 生成图片。"""
        prompt = (
            f"Technical assembly illustration, isometric view, clean line drawing style, "
            f"white background. Step {seq}: {title}. {desc}. "
            f"Show mechanical parts being assembled. Industrial CAD-style rendering. "
            f"Clear labels, professional engineering diagram."
        )

        try:
            response = self._client.images.generate(
                model=config.IMAGE_MODEL,
                prompt=prompt,
                size="2048x2048",  # Doubao 要求 >= 3686400 像素
                n=1,
                response_format="b64_json",
            )

            if response.data and response.data[0].b64_json:
                image_data = base64.b64decode(response.data[0].b64_json)
                image = Image.open(BytesIO(image_data))
                image.save(str(path), "PNG")
                return str(path)

            return None
        except Exception:
            return None

    def _fallback_diagram(self, title: str, desc: str, seq: int, path: Path) -> str:
        """用 Pillow 生成装配示意图占位图。"""
        img = Image.new("RGB", (800, 500), "white")
        draw = ImageDraw.Draw(img)

        # 标题栏
        draw.rectangle([0, 0, 800, 60], fill="#1a56db")
        draw.text((20, 18), f"步骤 {seq}: {title}", fill="white")

        # 装配示意图区域（简单框图）
        draw.rectangle([50, 100, 750, 420], outline="#cbd5e1", width=2)

        # 绘制简单的零件表示

        # 底座零件
        draw.rectangle([150, 320, 650, 380], fill="#93c5fd", outline="#1e40af", width=2)
        draw.text((340, 340), "底座 / Base", fill="#1e3a5f")

        # 中间零件
        draw.rectangle([250, 240, 550, 320], fill="#fde68a", outline="#92400e", width=2)
        draw.text((340, 272), "零件 / Part", fill="#78350f")

        # 顶部零件 / 工具指示
        draw.rectangle([300, 160, 500, 240], fill="#a7f3d0", outline="#065f46", width=2)
        draw.text((350, 192), "工具 / Tool", fill="#064e3b")

        # 箭头指示
        draw.line([400, 140, 400, 160], fill="#ef4444", width=3)
        draw.line([390, 150, 400, 140], fill="#ef4444", width=3)
        draw.line([410, 150, 400, 140], fill="#ef4444", width=3)

        # 页脚
        draw.rectangle([0, 440, 800, 500], fill="#f8fafc")
        draw.text((20, 455), desc[:80] + ("..." if len(desc) > 80 else ""), fill="#64748b")

        img.save(str(path), "PNG")
        return str(path)

    def generate_all_step_images(self, steps: list[dict]) -> dict[int, str]:
        """为所有步骤生成图片。返回 {sequence: image_path}。"""
        results = {}
        for step in steps:
            seq = step.get("sequence", 0)
            title = step.get("title", "")
            desc = step.get("description", "")
            path = self.generate_step_image(title, desc, seq)
            if path:
                results[seq] = path
        return results
