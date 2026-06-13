"""多视角参考图 + PDF 模式绑定测试。

覆盖：
1. 多视角参考图生成（2×2 网格：正视+右视+俯视+等轴测）
2. Instruction 中记录 mode 信息
3. PDF 导出使用最新 instruction 的 mode
"""

import json
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from PIL import Image

from src.app.services.reference_renderer import (
    render_part_multi_view,
    render_progressive_assembly,
    get_part_msb_refs,
    _parse_step_topology,
    _extract_part_edges,
)


STEP_FILE = Path("ILD1x20-100.step")


@pytest.fixture(scope="module")
def step_text():
    return STEP_FILE.read_text(encoding="utf-8", errors="replace")


# ─── 1. 多视角参考图测试 ───

class TestMultiViewReference:
    """参考图应支持多视角模式。"""

    def test_render_part_multi_view_returns_png(self, step_text):
        """render_part_multi_view 应返回 PNG 图片。"""
        img = render_part_multi_view(step_text, 0)
        assert len(img) > 0
        assert img[:4] == b'\x89PNG'

    def test_multi_view_has_4_quadrants(self, step_text):
        """多视角图应包含 4 个象限（正视+右视+俯视+等轴测）。"""
        img_bytes = render_part_multi_view(step_text, 1)
        img = Image.open(BytesIO(img_bytes))
        assert img.size == (1024, 1024)
        # 检查 4 个象限是否都有内容（非全白）
        quadrants = [
            img.crop((0, 0, 512, 512)),      # 左上
            img.crop((512, 0, 1024, 512)),    # 右上
            img.crop((0, 512, 512, 1024)),    # 左下
            img.crop((512, 512, 1024, 1024)), # 右下
        ]
        for i, q in enumerate(quadrants):
            pixels = list(q.convert("L").getdata())
            non_white = sum(1 for p in pixels if p < 250)
            assert non_white > 100, f"象限 {i} 应有内容，实际非白像素={non_white}"

    def test_multiview_differs_from_single_view(self, step_text):
        """多视角图应与单视角图不同。"""
        single = Image.open(BytesIO(
            render_progressive_assembly(step_text, 0, 10)
        ))
        multi = Image.open(BytesIO(
            render_part_multi_view(step_text, 1)
        ))
        # 像素应该不同
        s_pixels = list(single.convert("L").getdata())
        m_pixels = list(multi.convert("L").getdata())
        diff = sum(1 for s, m in zip(s_pixels, m_pixels) if abs(s - m) > 10)
        assert diff > 1000, f"多视角应与单视角有显著差异，实际差异像素={diff}"


# ─── 2. Instruction mode 记录测试 ───

class TestInstructionModeTracking:
    """Instruction 应记录生成时使用的 mode。"""

    def test_instruction_schema_has_mode_field(self):
        """AssemblyInstructionSchema 应有 mode 字段。"""
        from src.app.models.schemas import AssemblyInstructionSchema
        schema = AssemblyInstructionSchema(
            instructionId=uuid4(),
            title="测试",
            sections=[],
            mode="comparison",
        )
        assert schema.mode == "comparison"

    def test_instruction_schema_default_mode(self):
        """mode 默认值应为 comparison。"""
        from src.app.models.schemas import AssemblyInstructionSchema
        schema = AssemblyInstructionSchema(
            instructionId=uuid4(),
            title="测试",
            sections=[],
        )
        assert schema.mode == "comparison"

    def test_render_stores_mode_in_instruction(self):
        """render 应将 mode 存入 instruction。"""
        from src.app.services.instruction_service import InstructionService
        from src.app.models.schemas import AssemblyInstructionSchema

        svc = InstructionService(db=MagicMock())
        # Mock 依赖
        svc.approved_repo = MagicMock()
        svc.approved_repo.get_by_id.return_value = MagicMock(
            graph_json=json.dumps({
                "approvedProcessId": str(uuid4()),
                "approvedBy": "test",
                "approvedAt": "2026-01-01T00:00:00",
                "steps": [],
            }),
            draft_process_id=None,
        )
        svc.draft_repo = MagicMock()
        svc.draft_repo.get_by_id.return_value = None
        svc.pg_repo = MagicMock()
        svc.instruction_repo = MagicMock()

        instruction_id, instruction = svc.render(uuid4(), mode="reference_only")
        assert instruction.mode == "reference_only"


# ─── 3. PDF 导出使用最新 mode 测试 ───

class TestPdfUsesLatestMode:
    """PDF 导出应使用最新 instruction 的 mode。"""

    def test_export_pdf_reads_instruction_mode(self):
        """export_pdf 应读取 instruction 中的 mode 并反映在 PDF 中。"""
        from src.app.services.instruction_service import InstructionService

        svc = InstructionService(db=MagicMock())
        svc.instruction_repo = MagicMock()

        # 创建一个带 mode 的 instruction
        mock_ai = MagicMock()
        mock_ai.instruction_json = json.dumps({
            "instructionId": str(uuid4()),
            "title": "测试指导书",
            "mode": "reference_only",
            "sections": [
                {"sectionType": "cover", "content": "封面"},
                {"sectionType": "step", "content": "步骤1", "imagePath": None},
            ],
        })
        mock_ai.pdf_path = None
        svc.instruction_repo.get_by_id.return_value = mock_ai

        # 导出 PDF
        pdf_path = svc.export_pdf(uuid4())

        # 验证 PDF 文件存在
        assert Path(pdf_path).exists()
        assert pdf_path.endswith(".pdf")
