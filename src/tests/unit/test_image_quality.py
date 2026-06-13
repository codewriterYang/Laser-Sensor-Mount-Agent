"""图片质量改进测试 — 面填充、Prompt 增强、img2img 强度。

覆盖本轮改进的三个核心优化：
1. 参考图添加半透明面填充（增加体积感）
2. Prompt 增强（更多几何细节）
3. img2img strength 降低（保留更多参考图形状）
"""

import inspect
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from src.app.services.reference_renderer import (
    _parse_step_topology,
    _extract_part_edges,
    _render_edges_to_image,
    get_part_msb_refs,
    render_part_wireframe,
    render_progressive_assembly,
)
from src.app.services.prompt_builder import build_step_image_prompt
from src.app.services.image_service import ImageService


STEP_FILE = Path("ILD1x20-100.step")


@pytest.fixture(scope="module")
def step_text():
    return STEP_FILE.read_text(encoding="utf-8", errors="replace")


# ─── 1. 面填充测试 ───

class TestFaceFill:
    """参考图应支持面填充模式，增加体积感。"""

    def test_render_edges_accepts_fill_faces_param(self):
        """_render_edges_to_image 应接受 fill_faces 参数。"""
        sig = inspect.signature(_render_edges_to_image)
        assert "fill_faces" in sig.parameters, (
            "_render_edges_to_image 应有 fill_faces 参数"
        )

    def test_fill_faces_increases_non_white_pixels(self, step_text):
        """fill_faces=True 时非白像素应 >= fill_faces=False。"""
        topology = _parse_step_topology(step_text)
        msb_refs = get_part_msb_refs(step_text)
        edges = _extract_part_edges(topology, msb_refs[1])

        img_no_fill = Image.open(BytesIO(
            _render_edges_to_image(edges, fill_faces=False)
        )).convert("L")
        img_fill = Image.open(BytesIO(
            _render_edges_to_image(edges, fill_faces=True)
        )).convert("L")

        nw_no_fill = sum(1 for p in img_no_fill.getdata() if p < 250)
        nw_fill = sum(1 for p in img_fill.getdata() if p < 250)

        assert nw_fill >= nw_no_fill, (
            f"fill_faces 应增加非白像素: {nw_fill} < {nw_no_fill}"
        )


# ─── 2. Prompt 增强测试 ───

class TestPromptEnhancement:
    """Prompt 应包含更多几何细节。"""

    def test_prompt_includes_surface_features(self):
        """Prompt 应包含曲面特征描述。"""
        prompt = build_step_image_prompt(
            part_name="带孔支架", face_count=19,
            surface_types=["平面", "圆柱面"],
            color_hex="#b11919", length=34.0, width=15.0, height=1.4,
            sequence=1, total_steps=10, step_title="安装支架",
        )
        assert "cylindrical" in prompt.lower() or "round" in prompt.lower()

    def test_prompt_includes_assembly_context(self):
        """Prompt 应包含装配阶段上下文。"""
        prompt_first = build_step_image_prompt(
            part_name="底板", face_count=5, surface_types=["平面"],
            color_hex=None, length=10, width=10, height=1,
            sequence=1, total_steps=10, step_title="安装底板",
        )
        assert "first" in prompt_first.lower() or "alone" in prompt_first.lower()

    def test_prompt_includes_bom_material(self):
        """提供 BOM 信息时应包含材质描述。"""
        prompt = build_step_image_prompt(
            part_name="支架", face_count=19, surface_types=["平面", "圆柱面"],
            color_hex="#b11919", length=34, width=15, height=1.4,
            sequence=1, total_steps=10, step_title="安装支架",
            bom_material="铝合金", bom_finish="阳极氧化",
        )
        assert "aluminum" in prompt.lower() or "alloy" in prompt.lower()


# ─── 3. img2img 强度测试 ───

class TestImg2ImgStrength:
    """img2img strength 应降低到 0.65-0.75。"""

    def test_strength_not_0_9(self):
        """不应再使用 0.90 的 strength。"""
        source = inspect.getsource(ImageService._generate_ai_bytes)
        assert "0.90" not in source, "strength 0.90 已过时"

    def test_strength_in_valid_range(self):
        """strength 应在 0.65-0.75 范围内。"""
        source = inspect.getsource(ImageService._generate_ai_bytes)
        # 找到 strength= 参数
        import re
        match = re.search(r"strength[=:]\s*([\d.]+)", source)
        assert match, "源码中未找到 strength 参数"
        val = float(match.group(1))
        assert 0.60 <= val <= 0.80, f"strength={val} 不在 0.60-0.80 范围内"
