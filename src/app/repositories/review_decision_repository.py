"""ReviewDecision 仓库 — 06_DATABASE.md §7。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from ..models.orm import ReviewDecision


class ReviewDecisionRepository:
    """review_decisions 表的 CRUD 操作。"""

    def __init__(self, db: Session):
        self.db = db

    def save(self, decision: ReviewDecision) -> ReviewDecision:
        self.db.add(decision)
        self.db.flush()
        return decision

    def get_by_process(self, process_id: UUID) -> list[ReviewDecision]:
        return self.db.query(ReviewDecision).filter(ReviewDecision.process_id == str(process_id)).all()
