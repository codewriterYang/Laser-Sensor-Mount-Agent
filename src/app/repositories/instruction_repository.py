"""AssemblyInstruction repository — 06_DATABASE.md §9."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from ..models.orm import AssemblyInstruction


class InstructionRepository:
    """CRUD for assembly_instructions table."""

    def __init__(self, db: Session):
        self.db = db

    def save(self, instruction: AssemblyInstruction) -> AssemblyInstruction:
        self.db.add(instruction)
        self.db.flush()
        return instruction

    def get_by_id(self, instruction_id: UUID) -> AssemblyInstruction | None:
        return self.db.query(AssemblyInstruction).filter(AssemblyInstruction.id == str(instruction_id)).first()

    def get_by_approved_process(self, approved_process_id: UUID) -> AssemblyInstruction | None:
        return self.db.query(AssemblyInstruction).filter(
            AssemblyInstruction.approved_process_id == str(approved_process_id)
        ).first()
