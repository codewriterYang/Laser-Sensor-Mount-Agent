"""StepFile 仓库 — step_files 表的持久化层 (06_DATABASE.md §4)。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from ..models.orm import StepFile


class StepFileRepository:
    """StepFile 实体的 CRUD 操作。"""

    def __init__(self, db: Session):
        self.db = db

    def save(self, step_file: StepFile) -> StepFile:
        self.db.add(step_file)
        self.db.flush()
        return step_file

    def get_by_id(self, step_file_id: UUID) -> StepFile | None:
        return self.db.query(StepFile).filter(StepFile.id == str(step_file_id)).first()

    def update_status(self, step_file_id: UUID, status: str) -> StepFile | None:
        sf = self.get_by_id(step_file_id)
        if sf:
            sf.status = status
            self.db.flush()
        return sf
