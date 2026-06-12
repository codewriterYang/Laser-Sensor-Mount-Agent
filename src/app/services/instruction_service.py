"""指导书 Service — ApprovedProcessGraph → AssemblyInstruction → PDF (03_ARCHITECTURE.md §1.2)。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fpdf import FPDF
from sqlalchemy.orm import Session

from ..models.orm import AssemblyInstruction
from ..models.schemas import (
    ApprovedProcessGraphSchema,
    AssemblyInstructionSchema,
    SectionSchema,
)
from ..repositories.approved_process_repository import ApprovedProcessRepository
from ..repositories.draft_process_repository import DraftProcessRepository
from ..repositories.instruction_repository import InstructionRepository
from ..repositories.product_graph_repository import ProductGraphRepository
from .image_service import ImageService
from ..logger import logger


class ApprovedProcessNotFoundError(Exception):
    pass


class RenderFailedError(Exception):
    pass


class InstructionNotFoundError(Exception):
    pass


class PDFExportFailedError(Exception):
    pass


EXPORTS_DIR = Path("exports")

# CJK 字体路径，按优先级尝试
_CJK_FONT_PATHS = [
    "C:/Windows/Fonts/simhei.ttf",     # 黑体 (Windows TTF，优先避免 TTC 子集化问题)
    "C:/Windows/Fonts/msyh.ttc",       # 微软雅黑 (Windows)
    "C:/Windows/Fonts/simsun.ttc",     # 宋体 (Windows)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux
    "/System/Library/Fonts/PingFang.ttc",  # macOS
]

_cjk_font_path: str | None = None


def _get_cjk_font_path() -> str | None:
    """在系统中查找可用的 CJK TrueType 字体。"""
    global _cjk_font_path
    if _cjk_font_path is not None:
        return _cjk_font_path if _cjk_font_path else None
    for path in _CJK_FONT_PATHS:
        if Path(path).exists():
            _cjk_font_path = path
            return path
    _cjk_font_path = ""
    return None


def _make_pdf() -> FPDF:
    """创建 FPDF 实例，如果可用则添加 CJK 字体支持。"""
    pdf = FPDF()
    cjk_path = _get_cjk_font_path()
    if cjk_path:
        pdf.add_font("CJK", "", cjk_path)
        pdf.add_font("CJK", "B", cjk_path)
    return pdf


class InstructionService:
    """从 ApprovedProcessGraph 渲染 AssemblyInstruction 并导出 PDF。"""

    def __init__(self, db: Session):
        self.db = db
        self.approved_repo = ApprovedProcessRepository(db)
        self.draft_repo = DraftProcessRepository(db)
        self.pg_repo = ProductGraphRepository(db)
        self.instruction_repo = InstructionRepository(db)
        self.image_service = ImageService()

    def render(self, approved_process_id: UUID) -> tuple[UUID, AssemblyInstructionSchema]:
        """从 ApprovedProcessGraph 渲染 AssemblyInstruction。

        返回 (instruction_id, AssemblyInstructionSchema)。
        """
        apg = self.approved_repo.get_by_id(approved_process_id)
        if apg is None:
            raise ApprovedProcessNotFoundError(approved_process_id)

        data = json.loads(apg.graph_json)
        approved = ApprovedProcessGraphSchema(**data)

        # 通过链路追溯获取真实零件尺寸：ApprovedProcess → DraftProcess → ProductGraph
        part_dims = self._get_part_dimensions(apg.draft_process_id)

        # 为每个步骤生成图片（基于真实 STEP 尺寸数据，非 AI 虚构）
        step_dicts = [s.model_dump() for s in approved.steps]
        image_paths = self.image_service.generate_all_step_images(step_dicts, part_dims)

        # 构建包含图片路径的章节
        sections = self._build_sections(approved, image_paths)

        instruction_id = uuid.uuid4()
        instruction = AssemblyInstructionSchema(
            instructionId=instruction_id,
            title=f"装配指导书 — {approved.approvedBy}",
            sections=sections,
        )

        ai = AssemblyInstruction(
            id=str(instruction_id),
            approved_process_id=str(approved_process_id),
            instruction_json=instruction.model_dump_json(),
        )
        self.instruction_repo.save(ai)

        return instruction_id, instruction

    def _get_part_dimensions(self, draft_process_id: str | None) -> dict | None:
        """通过链路追溯获取零件真实尺寸。

        ApprovedProcess → DraftProcess → ProductGraph → 从节点 metadata 中提取尺寸。
        """
        if not draft_process_id:
            return None
        try:
            from uuid import UUID
            draft = self.draft_repo.get_by_id(UUID(draft_process_id))
            if not draft:
                return None
            import json
            draft_data = json.loads(draft.graph_json)
            pg_id = draft_data.get("productGraphId") or draft.product_graph_id
            if not pg_id:
                return None
            pg = self.pg_repo.get_by_id(UUID(pg_id))
            if not pg:
                return None
            pg_data = json.loads(pg.graph_json)
            # 找第一个有尺寸数据的节点
            for node in pg_data.get("nodes", []):
                meta = node.get("metadata", {})
                if meta.get("length") and meta.get("width") and meta.get("height"):
                    return {
                        "length": meta["length"],
                        "width": meta["width"],
                        "height": meta["height"],
                    }
            return None
        except Exception as e:
            logger.warning(f"获取零件尺寸失败：{e}")
            return None

    def _build_sections(
        self, approved: ApprovedProcessGraphSchema, image_paths: dict[int, str] | None = None
    ) -> list[SectionSchema]:
        image_paths = image_paths or {}
        sections = [
            SectionSchema(
                sectionType="cover",
                content=f"装配指导书\n\n审核人：{approved.approvedBy}\n日期：{approved.approvedAt.isoformat()}",
            ),
            SectionSchema(
                sectionType="overview",
                content=f"本指导书包含 {len(approved.steps)} 个装配步骤，请严格按照顺序操作。",
            ),
        ]

        for step in approved.steps:
            parts = "、".join(step.requiredParts) if step.requiredParts else "无"
            tools = "、".join(step.requiredTools) if step.requiredTools else "无"
            content = (
                f"步骤 {step.sequence}：{step.title}\n\n"
                f"{step.description}\n\n"
                f"所需零件：{parts}\n"
                f"所需工具：{tools}"
            )
            img_path = image_paths.get(step.sequence)
            sections.append(SectionSchema(sectionType="step", content=content, imagePath=img_path))

        sections.append(SectionSchema(
            sectionType="safety",
            content="请穿戴适当的个人防护装备（PPE）。遵守所有安全操作规程。确认所有紧固件已按规定扭矩拧紧。",
        ))
        sections.append(SectionSchema(
            sectionType="ending",
            content=f"装配指导书结束。生成时间：{datetime.now(timezone.utc).isoformat()}",
        ))

        return sections

    def get_instruction(self, instruction_id: UUID) -> AssemblyInstructionSchema | None:
        """根据 ID 获取 AssemblyInstruction。"""
        ai = self.instruction_repo.get_by_id(instruction_id)
        if ai is None:
            return None
        data = json.loads(ai.instruction_json)
        return AssemblyInstructionSchema(**data)

    def export_pdf(self, instruction_id: UUID) -> str:
        """将 AssemblyInstruction 导出为含图片的 PDF。返回文件路径。"""
        ai = self.instruction_repo.get_by_id(instruction_id)
        if ai is None:
            raise InstructionNotFoundError(instruction_id)

        data = json.loads(ai.instruction_json)
        instruction = AssemblyInstructionSchema(**data)

        try:
            EXPORTS_DIR.mkdir(exist_ok=True)
            pdf_path = EXPORTS_DIR / f"{instruction_id}.pdf"

            pdf = _make_pdf()
            has_cjk = _get_cjk_font_path() is not None
            font_name = "CJK" if has_cjk else "Helvetica"
            pdf.set_auto_page_break(auto=True, margin=15)

            # 封面页
            pdf.add_page()
            pdf.set_font(font_name, "B", 16)
            pdf.cell(0, 10, "装配指导书", new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.ln(5)

            for section in instruction.sections:
                if section.sectionType == "cover":
                    pdf.set_font(font_name, "B", 14)
                    for line in section.content.split("\n"):
                        pdf.cell(0, 8, line.strip(), new_x="LMARGIN", new_y="NEXT", align="C")
                    pdf.ln(5)
                elif section.sectionType == "overview":
                    pdf.set_font(font_name, "I" if not has_cjk else "", 10)
                    pdf.cell(0, 8, section.content, new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(3)
                elif section.sectionType == "step":
                    pdf.set_font(font_name, "B", 11)
                    lines = section.content.split("\n")
                    pdf.cell(0, 7, lines[0], new_x="LMARGIN", new_y="NEXT")  # 步骤标题
                    pdf.set_font(font_name, "", 10)
                    for line in lines[1:]:
                        if line.strip():
                            pdf.cell(0, 6, f"  {line.strip()}", new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(2)

                    # 嵌入步骤图片（如果可用）
                    if section.imagePath and Path(section.imagePath).exists():
                        try:
                            pdf.image(section.imagePath, x=20, w=170)
                            pdf.ln(4)
                        except Exception:
                            pass  # 无法嵌入图片时跳过
                    pdf.ln(4)
                elif section.sectionType == "safety":
                    pdf.set_font(font_name, "B", 10)
                    pdf.cell(0, 8, "安全须知：", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font(font_name, "", 10)
                    pdf.multi_cell(0, 6, section.content)
                    pdf.ln(3)
                elif section.sectionType == "ending":
                    pdf.set_font(font_name, "I" if not has_cjk else "", 9)
                    pdf.cell(0, 8, section.content, new_x="LMARGIN", new_y="NEXT", align="C")

            pdf.output(str(pdf_path))
            ai.pdf_path = str(pdf_path)
            self.db.flush()

            return str(pdf_path)
        except Exception as e:
            raise PDFExportFailedError(f"PDF 导出失败: {e}")
