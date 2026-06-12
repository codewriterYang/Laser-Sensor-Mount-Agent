"""Review Service — DraftProcessGraph → ApprovedProcessGraph (03_ARCHITECTURE.md §1.2)."""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.orm import ApprovedProcessGraph, ReviewDecision
from ..models.schemas import (
    ApprovedProcessGraphSchema,
    DraftProcessGraphSchema,
    ReviewDecisionSchema,
    StepSchema,
)
from ..repositories.approved_process_repository import ApprovedProcessRepository
from ..repositories.draft_process_repository import DraftProcessRepository
from ..repositories.review_decision_repository import ReviewDecisionRepository


class ProcessNotFoundError(Exception):
    pass


class InvalidReviewActionError(Exception):
    pass


class ReviewRequiredError(Exception):
    pass


VALID_ACTIONS = {"accept", "modify", "delete", "insert"}


class ReviewService:
    """Process engineer review decisions → ApprovedProcessGraph."""

    def __init__(self, db: Session):
        self.db = db
        self.draft_repo = DraftProcessRepository(db)
        self.approved_repo = ApprovedProcessRepository(db)
        self.review_repo = ReviewDecisionRepository(db)

    def submit_review(
        self, process_id: UUID, decisions: list[ReviewDecisionSchema], reviewer: str = "Engineer"
    ) -> tuple[UUID, ApprovedProcessGraphSchema]:
        """Submit review decisions and generate an ApprovedProcessGraph.

        Returns (approved_process_id, ApprovedProcessGraphSchema).
        """
        # 1. Look up DraftProcessGraph
        dpg = self.draft_repo.get_by_id(process_id)
        if dpg is None:
            raise ProcessNotFoundError(process_id)

        draft_data = json.loads(dpg.graph_json)
        draft = DraftProcessGraphSchema(**draft_data)

        # 2. Validate decisions
        if not decisions:
            raise ReviewRequiredError("At least one review decision is required")

        for d in decisions:
            if d.action not in VALID_ACTIONS:
                raise InvalidReviewActionError(f"Invalid action: {d.action}")

        # 3. Apply decisions to steps
        updated_steps = self._apply_decisions(draft.steps, decisions)

        # 4. Persist review decisions
        for d in decisions:
            rd = ReviewDecision(
                process_id=str(process_id),
                step_id=str(d.stepId),
                action=d.action,
                reason=d.reason,
                reviewer=reviewer,
            )
            self.review_repo.save(rd)

        # 5. Update DraftProcessGraph status
        self.draft_repo.update_graph_json(process_id, draft.model_dump_json(), "approved")

        # 6. Create ApprovedProcessGraph — use same UUID for schema and DB
        approved_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        approved = ApprovedProcessGraphSchema(
            approvedProcessId=approved_id,
            approvedBy=reviewer,
            approvedAt=now,
            steps=updated_steps,
        )

        apg = ApprovedProcessGraph(
            id=str(approved_id),
            draft_process_id=str(process_id),
            graph_json=approved.model_dump_json(),
            approved_by=reviewer,
            approved_at=now,
        )
        self.approved_repo.save(apg)

        return approved_id, approved

    def _apply_decisions(
        self, steps: list[StepSchema], decisions: list[ReviewDecisionSchema]
    ) -> list[StepSchema]:
        """Apply review decisions to the step list."""
        step_map = {str(s.stepId): s for s in steps}
        result = []

        for d in decisions:
            sid = str(d.stepId)

            if d.action == "accept":
                if sid in step_map:
                    result.append(step_map[sid])

            elif d.action == "delete":
                # Skip this step (don't add to result)
                pass

            elif d.action == "modify":
                if sid in step_map:
                    modified = step_map[sid].model_copy(deep=True)
                    modified.title = f"{modified.title} (Modified)"
                    modified.description = d.reason or modified.description
                    result.append(modified)

            elif d.action == "insert":
                new_step = StepSchema(
                    stepId=uuid.uuid4(),
                    sequence=len(result) + 1,
                    title=f"Added Step",
                    description=d.reason or "Engineer-inserted step",
                    requiredParts=[],
                    requiredTools=[],
                )
                result.append(new_step)

        # Re-sequence
        for i, s in enumerate(result, 1):
            s.sequence = i

        return result

    def get_approved(self, approved_process_id: UUID) -> ApprovedProcessGraphSchema | None:
        """Retrieve an ApprovedProcessGraph by ID."""
        apg = self.approved_repo.get_by_id(approved_process_id)
        if apg is None:
            return None
        data = json.loads(apg.graph_json)
        return ApprovedProcessGraphSchema(**data)
