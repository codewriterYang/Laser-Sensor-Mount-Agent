"""Unit tests for ReviewService."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.app.models.orm import Base, DraftProcessGraph
from src.app.models.schemas import ReviewDecisionSchema
from src.app.services.review_service import (
    InvalidReviewActionError,
    ProcessNotFoundError,
    ReviewRequiredError,
    ReviewService,
)

S1 = UUID("00000000-0000-0000-0000-000000000001")
S2 = UUID("00000000-0000-0000-0000-000000000002")
S3 = UUID("00000000-0000-0000-0000-000000000003")
S4 = UUID("00000000-0000-0000-0000-000000000004")
S5 = UUID("00000000-0000-0000-0000-000000000005")

DEMO_DRAFT_JSON = json.dumps({
    "processId": str(uuid4()),
    "status": "reviewing",
    "steps": [
        {"stepId": str(S1), "sequence": 1, "title": "Install Base Plate", "description": "Place the Base Plate", "requiredParts": ["Base Plate"], "requiredTools": []},
        {"stepId": str(S2), "sequence": 2, "title": "Install Bracket", "description": "Mount the Bracket", "requiredParts": ["Bracket"], "requiredTools": ["Hex Wrench"]},
        {"stepId": str(S3), "sequence": 3, "title": "Install Laser Sensor", "description": "Attach the Laser Sensor", "requiredParts": ["Laser Sensor"], "requiredTools": ["Hex Wrench"]},
        {"stepId": str(S4), "sequence": 4, "title": "Fasten Screw M4x12", "description": "Secure with Screw", "requiredParts": ["Screw M4x12"], "requiredTools": ["Torque Wrench"]},
        {"stepId": str(S5), "sequence": 5, "title": "Install Washer M4", "description": "Place the Washer", "requiredParts": ["Washer M4"], "requiredTools": []},
    ],
})


class TestReviewService:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.session = Session(bind=self.engine)
        self.svc = ReviewService(self.session)
        self.dpg_id = str(uuid4())
        self.dpg = DraftProcessGraph(
            id=self.dpg_id,
            product_graph_id=str(uuid4()),
            graph_json=DEMO_DRAFT_JSON,
            status="reviewing",
            generated_by="rule_engine",
        )
        self.session.add(self.dpg)
        self.session.commit()
        yield
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)

    # --- Success cases ---

    def test_accept_all_steps_returns_approved(self):
        decisions = [
            ReviewDecisionSchema(stepId=S1, action="accept", reason="OK"),
            ReviewDecisionSchema(stepId=S2, action="accept", reason="OK"),
        ]
        approved_id, approved = self.svc.submit_review(UUID(self.dpg_id), decisions)
        assert approved_id is not None
        assert approved.approvedProcessId == approved_id
        assert approved.approvedBy == "Engineer"
        assert approved.approvedAt is not None
        assert len(approved.steps) == 2

    def test_accept_all_five_steps(self):
        decisions = [
            ReviewDecisionSchema(stepId=S1, action="accept", reason="OK"),
            ReviewDecisionSchema(stepId=S2, action="accept", reason="OK"),
            ReviewDecisionSchema(stepId=S3, action="accept", reason="OK"),
            ReviewDecisionSchema(stepId=S4, action="accept", reason="OK"),
            ReviewDecisionSchema(stepId=S5, action="accept", reason="OK"),
        ]
        _, approved = self.svc.submit_review(UUID(self.dpg_id), decisions)
        assert len(approved.steps) == 5

    def test_delete_step_reduces_count(self):
        decisions = [
            ReviewDecisionSchema(stepId=S2, action="delete", reason="Not needed"),
            ReviewDecisionSchema(stepId=S1, action="accept", reason="OK"),
        ]
        _, approved = self.svc.submit_review(UUID(self.dpg_id), decisions)
        assert len(approved.steps) == 1
        assert approved.steps[0].title == "Install Base Plate"

    def test_modify_step_updates_description(self):
        decisions = [
            ReviewDecisionSchema(stepId=S1, action="modify", reason="Use torque wrench instead", newTitle="安装底板（已审核）"),
        ]
        _, approved = self.svc.submit_review(UUID(self.dpg_id), decisions)
        assert len(approved.steps) == 1
        step = approved.steps[0]
        assert "已审核" in step.title
        assert "torque wrench" in step.description.lower()

    def test_insert_adds_new_step(self):
        decisions = [
            ReviewDecisionSchema(stepId=S1, action="accept", reason="OK"),
            ReviewDecisionSchema(stepId=UUID("00000000-0000-0000-0000-000000000000"), action="insert", reason="Add lubrication step"),
        ]
        _, approved = self.svc.submit_review(UUID(self.dpg_id), decisions)
        assert len(approved.steps) == 2
        assert approved.steps[1].title == "新增步骤"

    def test_review_records_approved_by(self):
        decisions = [
            ReviewDecisionSchema(stepId=S1, action="accept", reason="OK"),
        ]
        _, approved = self.svc.submit_review(UUID(self.dpg_id), decisions, reviewer="Zhang Wei")
        assert approved.approvedBy == "Zhang Wei"

    def test_review_records_approved_at(self):
        decisions = [
            ReviewDecisionSchema(stepId=S1, action="accept", reason="OK"),
        ]
        _, approved = self.svc.submit_review(UUID(self.dpg_id), decisions)
        assert approved.approvedAt is not None

    def test_approved_steps_have_continuous_sequence(self):
        decisions = [
            ReviewDecisionSchema(stepId=S1, action="accept", reason="OK"),
            ReviewDecisionSchema(stepId=S3, action="accept", reason="OK"),
            ReviewDecisionSchema(stepId=S5, action="accept", reason="OK"),
        ]
        _, approved = self.svc.submit_review(UUID(self.dpg_id), decisions)
        sequences = [s.sequence for s in approved.steps]
        assert sequences == [1, 2, 3]

    def test_get_approved_returns_none_for_unknown(self):
        result = self.svc.get_approved(uuid4())
        assert result is None

    def test_get_approved_returns_graph_for_known(self):
        decisions = [
            ReviewDecisionSchema(stepId=S1, action="accept", reason="OK"),
        ]
        approved_id, _ = self.svc.submit_review(UUID(self.dpg_id), decisions)
        result = self.svc.get_approved(approved_id)
        assert result is not None
        assert result.approvedProcessId == approved_id

    # --- Error cases ---

    def test_review_nonexistent_process_raises(self):
        with pytest.raises(ProcessNotFoundError):
            self.svc.submit_review(uuid4(), [
                ReviewDecisionSchema(stepId=uuid4(), action="accept", reason="OK")
            ])

    def test_review_empty_decisions_raises(self):
        with pytest.raises(ReviewRequiredError):
            self.svc.submit_review(UUID(self.dpg_id), [])

    def test_review_invalid_action_raises(self):
        with pytest.raises(InvalidReviewActionError):
            self.svc.submit_review(UUID(self.dpg_id), [
                ReviewDecisionSchema(stepId=uuid4(), action="foobar", reason="")
            ])
