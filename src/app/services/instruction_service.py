"""指导书 Service — ApprovedProcessGraph → AssemblyInstruction → PDF (03_ARCHITECTURE.md §1.2)。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
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


_BEIJING_TZ = timezone(timedelta(hours=8))


def _beijing_now_str() -> str:
    """获取当前北京时间，格式：2026年6月12日22时30分15秒"""
    now = datetime.now(_BEIJING_TZ)
    return f"{now.year}年{now.month}月{now.day}日{now.hour}时{now.minute}分{now.second}秒"


def _to_beijing_str(dt: datetime) -> str:
    """将 datetime 转为北京时间字符串。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    bj = dt.astimezone(_BEIJING_TZ)
    return f"{bj.year}年{bj.month}月{bj.day}日{bj.hour}时{bj.minute}分{bj.second}秒"


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

    def render(self, approved_process_id: UUID, mode: str = "comparison") -> tuple[UUID, AssemblyInstructionSchema]:
        """从 ApprovedProcessGraph 渲染 AssemblyInstruction。

        mode: "reference_only" | "text_and_image" | "comparison"
        返回 (instruction_id, AssemblyInstructionSchema)。
        """
        apg = self.approved_repo.get_by_id(approved_process_id)
        if apg is None:
            raise ApprovedProcessNotFoundError(approved_process_id)

        data = json.loads(apg.graph_json)
        approved = ApprovedProcessGraphSchema(**data)

        # 通过链路追溯获取零件数据：ApprovedProcess → DraftProcess → ProductGraph
        overall_dims, per_step_info = self._get_part_data(apg.draft_process_id)

        # 获取 STEP 文件文本（用于生成参考图）
        step_text = self._get_step_text(apg.draft_process_id)

        # 为每个步骤生成图片（基于真实 STEP 尺寸和曲面类型数据）
        step_dicts = [s.model_dump() for s in approved.steps]
        image_paths = self.image_service.generate_all_step_images(
            step_dicts, overall_dims, per_step_info,
            step_text=step_text,
            mode=mode,
        )

        # 构建包含图片路径的章节
        sections = self._build_sections(approved, image_paths)

        instruction_id = uuid.uuid4()
        instruction = AssemblyInstructionSchema(
            instructionId=instruction_id,
            title=f"装配指导书 — {approved.approvedBy}",
            sections=sections,
            mode=mode,
        )

        ai = AssemblyInstruction(
            id=str(instruction_id),
            approved_process_id=str(approved_process_id),
            instruction_json=instruction.model_dump_json(),
        )
        self.instruction_repo.save(ai)

        return instruction_id, instruction

    def render_stream(self, approved_process_id: UUID, mode: str = "comparison"):
        """流式渲染 AssemblyInstruction，逐步 yield 进度事件。

        Yields:
            dict: {"type": "progress|done|error", "step": N, "total": N, "message": "...", ...}
        """
        try:
            apg = self.approved_repo.get_by_id(approved_process_id)
            if apg is None:
                yield {"type": "error", "message": f"未找到已审核工艺: {approved_process_id}"}
                return

            data = json.loads(apg.graph_json)
            approved = ApprovedProcessGraphSchema(**data)

            overall_dims, per_step_info = self._get_part_data(apg.draft_process_id)
            step_text = self._get_step_text(apg.draft_process_id)

            step_dicts = [s.model_dump() for s in approved.steps]
            total = len(step_dicts)
            image_paths = {}

            # 逐步生成图片
            for i, step in enumerate(step_dicts):
                seq = i + 1  # 用循环索引作为步骤编号
                title = step.get("title", "")

                yield {
                    "type": "progress",
                    "step": i + 1,
                    "total": total,
                    "message": f"正在生成步骤 {i + 1}/{total}：{title}",
                }

                info = per_step_info.get(seq) if per_step_info else None
                step_dims = None
                if info:
                    step_dims = {
                        "length": info.get("length", 0),
                        "width": info.get("width", 0),
                        "height": info.get("height", 0),
                    }

                path = self.image_service.generate_step_image(
                    title, step.get("description", ""), seq,
                    total_steps=total,
                    part_dimensions=step_dims or overall_dims,
                    part_info=info,
                    step_text=step_text,
                    mode=mode,
                )
                if path:
                    image_paths[seq] = path

                yield {
                    "type": "progress",
                    "step": i + 1,
                    "total": total,
                    "message": f"步骤 {i + 1}/{total} 已完成：{title}",
                    "image_path": path,
                }

            # 构建最终指导书
            sections = self._build_sections(approved, image_paths)
            instruction_id = uuid.uuid4()
            instruction = AssemblyInstructionSchema(
                instructionId=instruction_id,
                title=f"装配指导书 — {approved.approvedBy}",
                sections=sections,
                mode=mode,
            )

            ai = AssemblyInstruction(
                id=str(instruction_id),
                approved_process_id=str(approved_process_id),
                instruction_json=instruction.model_dump_json(),
            )
            self.instruction_repo.save(ai)

            yield {
                "type": "done",
                "instructionId": str(instruction_id),
                "message": f"指导书渲染完成，共 {total} 个步骤",
            }

        except Exception as e:
            yield {"type": "error", "message": str(e)}

    def _get_part_data(self, draft_process_id: str | None) -> tuple[dict | None, dict | None]:
        """通过链路追溯获取零件数据。

        ApprovedProcess → DraftProcess → ProductGraph → 从节点 metadata 中提取尺寸和曲面类型。
        返回 (整体尺寸, 每步骤零件信息)。
        """
        if not draft_process_id:
            return None, None
        try:
            from uuid import UUID as _UUID
            draft = self.draft_repo.get_by_id(_UUID(draft_process_id))
            if not draft:
                return None, None

            draft_data = json.loads(draft.graph_json)
            pg_id = draft_data.get("productGraphId") or draft.product_graph_id
            if not pg_id:
                return None, None

            pg = self.pg_repo.get_by_id(_UUID(pg_id))
            if not pg:
                return None, None

            pg_data = json.loads(pg.graph_json)
            nodes = pg_data.get("nodes", [])
            edges = pg_data.get("edges", [])

            # 构建节点 ID → 节点信息映射
            node_map = {}
            for node in nodes:
                node_map[node["nodeId"]] = node

            # 获取整体尺寸（从装配体根节点）
            overall_dims = None
            for node in nodes:
                meta = node.get("metadata", {})
                if meta.get("length") and meta.get("width") and meta.get("height"):
                    overall_dims = {
                        "length": meta["length"],
                        "width": meta["width"],
                        "height": meta["height"],
                    }
                    break

            # 从步骤的 requiredParts 匹配到零件节点
            steps = draft_data.get("steps", [])
            per_step_info = {}
            for step in steps:
                seq = step.get("sequence", 0)
                required_parts = step.get("requiredParts", [])
                # 在节点中查找匹配的零件
                for node in nodes:
                    node_name = node.get("name", "")
                    if node_name in required_parts or any(p in node_name for p in required_parts):
                        meta = node.get("metadata", {})
                        info = {
                            "name": node_name,
                            "faceCount": meta.get("faceCount", 0),
                            "surfaceTypes": meta.get("surfaceTypes", []),
                            "length": meta.get("length", 0),
                            "width": meta.get("width", 0),
                            "height": meta.get("height", 0),
                            "color": self._parse_color(meta.get("color")),
                        }
                        per_step_info[seq] = info
                        break

            return overall_dims, per_step_info

        except Exception as e:
            logger.warning(f"获取零件数据失败：{e}")
            return None, None

    def _get_step_text(self, draft_process_id: str | None) -> str | None:
        """获取 STEP 文件文本（用于生成参考图）。

        通过 DraftProcess → ProductGraph → 文件路径 → 读取文件。
        """
        if not draft_process_id:
            return None
        try:
            from uuid import UUID as _UUID
            draft = self.draft_repo.get_by_id(_UUID(draft_process_id))
            if not draft:
                return None

            draft_data = json.loads(draft.graph_json)
            pg_id = draft_data.get("productGraphId") or draft.product_graph_id
            if not pg_id:
                return None

            pg = self.pg_repo.get_by_id(_UUID(pg_id))
            if not pg:
                return None

            # 尝试从 ProductGraph metadata 获取文件路径
            pg_data = json.loads(pg.graph_json)
            file_path = pg_data.get("filePath") or pg_data.get("metadata", {}).get("filePath")

            # 从根节点 metadata 中查找 filePath
            if not file_path:
                for node in pg_data.get("nodes", []):
                    if node.get("nodeType") == "assembly":
                        meta = node.get("metadata", {})
                        file_path = meta.get("filePath")
                        if file_path:
                            break

            if not file_path:
                # 通过 ProductGraph.step_file_id 查找 StepFile 表
                if hasattr(pg, 'step_file_id') and pg.step_file_id:
                    from ..repositories.step_file_repository import StepFileRepository
                    sf_repo = StepFileRepository(self.db)
                    sf = sf_repo.get_by_id(UUID(pg.step_file_id))
                    if sf and sf.file_path:
                        file_path = sf.file_path

            if not file_path:
                # 最后尝试 uploads 目录中最新的 .step 文件
                uploads_dir = Path("uploads")
                step_files = sorted(
                    uploads_dir.glob("*.step"),
                    key=lambda f: f.stat().st_mtime,
                    reverse=True,
                )
                if step_files:
                    file_path = str(step_files[0])
                    logger.warning(f"使用 uploads 目录最新文件作为 fallback: {file_path}")

            if file_path and Path(file_path).exists():
                return Path(file_path).read_text(encoding="utf-8", errors="replace")

            return None
        except Exception as e:
            logger.warning(f"获取 STEP 文件文本失败：{e}")
            return None

    @staticmethod
    def _parse_color(color_str: str | None) -> tuple[float, float, float] | None:
        """解析 hex 颜色字符串为 (R, G, B) 元组（0.0~1.0）。"""
        if not color_str or not color_str.startswith("#") or len(color_str) != 7:
            return None
        try:
            r = int(color_str[1:3], 16) / 255.0
            g = int(color_str[3:5], 16) / 255.0
            b = int(color_str[5:7], 16) / 255.0
            return (r, g, b)
        except ValueError:
            return None

    def _build_sections(
        self, approved: ApprovedProcessGraphSchema, image_paths: dict[int, str] | None = None
    ) -> list[SectionSchema]:
        image_paths = image_paths or {}
        sections = [
            SectionSchema(
                sectionType="cover",
                content=f"装配指导书\n\n审核人：{approved.approvedBy}\n日期：{_to_beijing_str(approved.approvedAt)}",
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
            content=f"装配指导书结束。生成时间：{_beijing_now_str()}",
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
