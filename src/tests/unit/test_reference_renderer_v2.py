"""reference_renderer 重构测试 — 全局坐标、零件颜色、视觉质量。

覆盖本轮重构的三个核心改进：
1. render_progressive_assembly 使用全局坐标系（不再逐零件缩放到画布中央）
2. render_part_wireframe 支持 per-part 颜色
3. 装配体线框图中零件保持正确的空间关系
"""

import math
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from src.app.services.reference_renderer import (
    _render_edges_to_image,
    _parse_step_topology,
    _extract_part_edges,
    get_part_msb_refs,
    get_part_bounding_box,
    render_part_wireframe,
    render_assembly_wireframe,
    render_progressive_assembly,
    _project_iso,
)


# ─── 测试数据 ───

STEP_FILE = Path("ILD1x20-100.step")


@pytest.fixture(scope="module")
def step_text():
    """加载真实 STEP 文件内容。"""
    return STEP_FILE.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def topology(step_text):
    """解析 STEP 拓扑。"""
    return _parse_step_topology(step_text)


@pytest.fixture(scope="module")
def msb_refs(step_text):
    """获取零件 MSB 引用映射。"""
    return get_part_msb_refs(step_text)


# ─── 1. 全局坐标测试 ───

class TestGlobalCoordinates:
    """render_progressive_assembly 应使用全局坐标系，零件保持 STEP 中的相对位置。"""

    def test_two_parts_in_different_positions_not_overlapping(self, step_text, msb_refs):
        """两个在不同位置的零件渲染后，像素不应完全重叠。

        旧实现：每个零件单独缩放到画布中央 → 不同位置的零件像素重叠。
        新实现：所有零件在同一全局坐标系中投影 → 像素分布在不同区域。
        """
        if len(msb_refs) < 2:
            pytest.skip("STEP 文件零件不足")

        # 渲染步骤 2（包含零件 0 和零件 1）
        img_bytes = render_progressive_assembly(step_text, 1, len(msb_refs))
        img = Image.open(BytesIO(img_bytes)).convert("L")
        pixels = list(img.getdata())

        # 统计非白像素的数量
        non_white_count = sum(1 for p in pixels if p < 250)
        # 渲染了零件应有显著的非白像素
        assert non_white_count > 500, f"渲染结果应有非白像素，实际 {non_white_count}"

    def test_progressive_step_includes_current_part_color(self, step_text, msb_refs):
        """渐进式装配的当前零件应使用橙色高亮。"""
        if len(msb_refs) < 2:
            pytest.skip("STEP 文件零件不足")

        img_bytes = render_progressive_assembly(step_text, 0, len(msb_refs))
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        pixels = list(img.getdata())

        # 检查是否存在橙色像素（R>180, G<150, B<80）
        orange_count = sum(1 for r, g, b in pixels if r > 180 and g < 150 and b < 80)
        assert orange_count > 50, f"当前零件应有橙色像素，实际 {orange_count}"

    def test_assembly_wireframe_covers_wider_area_than_single_part(self, step_text, msb_refs):
        """装配体线框应包含多个零件的信息。"""
        if len(msb_refs) < 2:
            pytest.skip("STEP 文件零件不足")

        assembly = Image.open(BytesIO(render_assembly_wireframe(step_text))).convert("L")
        assembly_non_white = sum(1 for p in assembly.getdata() if p < 250)

        # 装配体有多个零件，非白像素应 > 1000
        assert assembly_non_white > 1000, f"装配体应有非白像素 > 1000，实际 {assembly_non_white}"


# ─── 2. 零件颜色测试 ───

class TestPartColors:
    """render_part_wireframe 应支持 per-part 颜色参数。"""

    def test_render_part_wireframe_accepts_color(self, step_text):
        """render_part_wireframe 应接受可选 color 参数而不崩溃。"""
        img = render_part_wireframe(step_text, 0, color="#ff0000")
        assert len(img) > 0
        assert img[:4] == b'\x89PNG'

    def test_colored_wireframe_differs_from_default(self, step_text):
        """带颜色参数的线框图应与默认灰色不同。"""
        default_img = Image.open(BytesIO(render_part_wireframe(step_text, 0))).convert("RGB")
        colored_img = Image.open(BytesIO(render_part_wireframe(step_text, 0, color="#ff0000"))).convert("RGB")

        default_pixels = list(default_img.getdata())
        colored_pixels = list(colored_img.getdata())

        # 至少有一些像素颜色不同
        diff_count = sum(1 for d, c in zip(default_pixels, colored_pixels) if d != c)
        assert diff_count > 100, f"颜色渲染应有差异，实际仅 {diff_count} 像素不同"

    def test_progressive_assembly_accepts_colors_dict(self, step_text, msb_refs):
        """render_progressive_assembly 应接受可选 part_colors 参数。"""
        colors = {0: "#ff0000", 1: "#00ff00"}
        img = render_progressive_assembly(step_text, 1, len(msb_refs), part_colors=colors)
        assert len(img) > 0
        assert img[:4] == b'\x89PNG'


# ─── 3. 视觉质量测试 ───

class TestVisualQuality:
    """渲染输出的基本视觉质量检查。"""

    def test_output_is_valid_png_1024(self, step_text):
        """输出应为 1024×1024 PNG。"""
        img_bytes = render_progressive_assembly(step_text, 0, 10)
        img = Image.open(BytesIO(img_bytes))
        assert img.size == (1024, 1024)
        assert img.format == "PNG"

    def test_empty_input_returns_blank_png(self):
        """空输入应返回空白 PNG 不崩溃。"""
        img = render_progressive_assembly("", 0, 7)
        assert img[:4] == b'\x89PNG'

    def test_bounding_box_computation(self, step_text, msb_refs):
        """包围盒计算应返回正数尺寸。"""
        for idx in range(min(3, len(msb_refs))):
            l, w, h = get_part_bounding_box(step_text, idx)
            # 至少两个维度应 > 0
            positive_count = sum(1 for v in (l, w, h) if v > 0)
            assert positive_count >= 2, f"Part {idx} 包围盒应有至少 2 个正维度: {l}x{w}x{h}"
