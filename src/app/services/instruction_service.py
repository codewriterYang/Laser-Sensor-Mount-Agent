"""Instruction Service — ApprovedProcessGraph → AssemblyInstruction → PDF (03_ARCHITECTURE.md §1.2)."""

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
from ..repositories.instruction_repository import InstructionRepository
from .image_service import ImageService


class ApprovedProcessNotFoundError(Exception):
    pass


class RenderFailedError(Exception):
    pass


class InstructionNotFoundError(Exception):
    pass


class PDFExportFailedError(Exception):
    pass


EXPORTS_DIR = Path("exports")


class InstructionService:
    """Render AssemblyInstruction from ApprovedProcessGraph and export PDF."""

    def __init__(self, db: Session):
        self.db = db
        self.approved_repo = ApprovedProcessRepository(db)
        self.instruction_repo = InstructionRepository(db)
        self.image_service = ImageService()

    def render(self, approved_process_id: UUID) -> tuple[UUID, AssemblyInstructionSchema]:
        """Render an AssemblyInstruction from an ApprovedProcessGraph.

        Returns (instruction_id, AssemblyInstructionSchema).
        """
        apg = self.approved_repo.get_by_id(approved_process_id)
        if apg is None:
            raise ApprovedProcessNotFoundError(approved_process_id)

        data = json.loads(apg.graph_json)
        approved = ApprovedProcessGraphSchema(**data)

        # Generate images for each step (non-blocking — continues on failure)
        step_dicts = [s.model_dump() for s in approved.steps]
        image_paths = {}
        if self.image_service.enabled:
            image_paths = self.image_service.generate_all_step_images(step_dicts)

        # Build sections with image paths
        sections = self._build_sections(approved, image_paths)

        instruction_id = uuid.uuid4()
        instruction = AssemblyInstructionSchema(
            instructionId=instruction_id,
            title=f"Assembly Instructions — {approved.approvedBy}",
            sections=sections,
        )

        ai = AssemblyInstruction(
            id=str(instruction_id),
            approved_process_id=str(approved_process_id),
            instruction_json=instruction.model_dump_json(),
        )
        self.instruction_repo.save(ai)

        return instruction_id, instruction

    def _build_sections(
        self, approved: ApprovedProcessGraphSchema, image_paths: dict[int, str] | None = None
    ) -> list[SectionSchema]:
        image_paths = image_paths or {}
        sections = [
            SectionSchema(
                sectionType="cover",
                content=f"Assembly Instructions\nApproved by: {approved.approvedBy}\nDate: {approved.approvedAt.isoformat()}",
            ),
            SectionSchema(
                sectionType="overview",
                content=f"This document contains {len(approved.steps)} assembly steps for the approved process.",
            ),
        ]

        for step in approved.steps:
            parts = ", ".join(step.requiredParts) if step.requiredParts else "None"
            tools = ", ".join(step.requiredTools) if step.requiredTools else "None"
            content = (
                f"Step {step.sequence}: {step.title}\n\n"
                f"{step.description}\n\n"
                f"Required Parts: {parts}\n"
                f"Required Tools: {tools}"
            )
            img_path = image_paths.get(step.sequence)
            sections.append(SectionSchema(sectionType="step", content=content, imagePath=img_path))

        sections.append(SectionSchema(
            sectionType="safety",
            content="Wear appropriate PPE. Follow all safety guidelines. Verify all fasteners are properly torqued.",
        ))
        sections.append(SectionSchema(
            sectionType="ending",
            content=f"End of assembly instructions. Generated at {datetime.now(timezone.utc).isoformat()}",
        ))

        return sections

    def get_instruction(self, instruction_id: UUID) -> AssemblyInstructionSchema | None:
        """Retrieve an AssemblyInstruction by ID."""
        ai = self.instruction_repo.get_by_id(instruction_id)
        if ai is None:
            return None
        data = json.loads(ai.instruction_json)
        return AssemblyInstructionSchema(**data)

    def export_pdf(self, instruction_id: UUID) -> str:
        """Export an AssemblyInstruction as PDF with embedded images. Returns the file path."""
        ai = self.instruction_repo.get_by_id(instruction_id)
        if ai is None:
            raise InstructionNotFoundError(instruction_id)

        data = json.loads(ai.instruction_json)
        instruction = AssemblyInstructionSchema(**data)

        try:
            EXPORTS_DIR.mkdir(exist_ok=True)
            pdf_path = EXPORTS_DIR / f"{instruction_id}.pdf"

            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)

            # Title page
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "Assembly Instructions", new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.ln(5)

            for section in instruction.sections:
                if section.sectionType == "cover":
                    pdf.set_font("Helvetica", "B", 14)
                    for line in section.content.split("\n"):
                        pdf.cell(0, 8, line.strip(), new_x="LMARGIN", new_y="NEXT", align="C")
                    pdf.ln(5)
                elif section.sectionType == "overview":
                    pdf.set_font("Helvetica", "I", 10)
                    pdf.cell(0, 8, section.content, new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(3)
                elif section.sectionType == "step":
                    pdf.set_font("Helvetica", "B", 11)
                    lines = section.content.split("\n")
                    pdf.cell(0, 7, lines[0], new_x="LMARGIN", new_y="NEXT")  # Step title
                    pdf.set_font("Helvetica", "", 10)
                    for line in lines[1:]:
                        if line.strip():
                            pdf.cell(0, 6, f"  {line.strip()}", new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(2)

                    # Embed step image if available
                    if section.imagePath and Path(section.imagePath).exists():
                        try:
                            pdf.image(section.imagePath, x=20, w=170)
                            pdf.ln(4)
                        except Exception:
                            pass  # Skip image if it can't be embedded
                    pdf.ln(4)
                elif section.sectionType == "safety":
                    pdf.set_font("Helvetica", "B", 10)
                    pdf.cell(0, 8, "SAFETY NOTES:", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("Helvetica", "", 10)
                    pdf.multi_cell(0, 6, section.content)
                    pdf.ln(3)
                elif section.sectionType == "ending":
                    pdf.set_font("Helvetica", "I", 9)
                    pdf.cell(0, 8, section.content, new_x="LMARGIN", new_y="NEXT", align="C")

            pdf.output(str(pdf_path))
            ai.pdf_path = str(pdf_path)
            self.db.flush()

            return str(pdf_path)
        except Exception as e:
            raise PDFExportFailedError(f"PDF export failed: {e}")
