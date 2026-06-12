"""ApprovedProcessGraph repository — 06_DATABASE.md §8."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from ..models.orm import ApprovedProcessGraph


class ApprovedProcessRepository:
    """CRUD for approved_process_graphs table."""

    def __init__(self, db: Session):
        self.db = db

    def save(self, apg: ApprovedProcessGraph) -> ApprovedProcessGraph:
        self.db.add(apg)
        self.db.flush()
        return apg

    def get_by_id(self, approved_process_id: UUID) -> ApprovedProcessGraph | None:
        return self.db.query(ApprovedProcessGraph).filter(ApprovedProcessGraph.id == str(approved_process_id)).first()
