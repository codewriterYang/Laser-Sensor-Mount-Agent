"""Integration tests for Repositories (06_DATABASE.md §12)."""

from __future__ import annotations

import json
import os
import tempfile
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.app.models.orm import (
    Base,
    ProductGraph,
    StepFile,
    DraftProcessGraph,
    ApprovedProcessGraph,
    ReviewDecision,
    AssemblyInstruction,
)
from src.app.repositories.product_graph_repository import ProductGraphRepository
from src.app.repositories.step_file_repository import StepFileRepository
from src.app.repositories.draft_process_repository import DraftProcessRepository
from src.app.repositories.approved_process_repository import ApprovedProcessRepository
from src.app.repositories.instruction_repository import InstructionRepository
from src.app.repositories.review_decision_repository import ReviewDecisionRepository


@pytest.fixture
def db_session():
    """Create a temp-file SQLite database for repository tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    os.unlink(path)


class TestStepFileRepository:
    def test_save_creates_record(self, db_session: Session):
        repo = StepFileRepository(db_session)
        sf = StepFile(file_name="test.step", file_path="/uploads/test.step", file_size=1024, status="uploaded")
        saved = repo.save(sf)

        assert saved.id is not None
        db_session.commit()

        fetched = repo.get_by_id(UUID(saved.id))
        assert fetched is not None
        assert fetched.file_name == "test.step"
        assert fetched.status == "uploaded"

    def test_update_status(self, db_session: Session):
        repo = StepFileRepository(db_session)
        sf = StepFile(file_name="test.step", file_path="/uploads/test.step", file_size=0, status="uploaded")
        repo.save(sf)
        db_session.commit()

        repo.update_status(UUID(sf.id), "parsing")
        db_session.commit()

        fetched = repo.get_by_id(UUID(sf.id))
        assert fetched.status == "parsing"

    def test_get_by_id_returns_none_for_unknown(self, db_session: Session):
        repo = StepFileRepository(db_session)
        assert repo.get_by_id(uuid4()) is None


class TestProductGraphRepository:
    def test_save_and_get_by_id(self, db_session: Session):
        repo = ProductGraphRepository(db_session)
        step_file_id = str(uuid4())
        graph_json = json.dumps({"graphId": str(uuid4()), "nodes": [], "edges": []})
        pg = ProductGraph(step_file_id=step_file_id, graph_json=graph_json, status="draft")
        repo.save(pg)
        db_session.commit()

        fetched = repo.get_by_id(UUID(pg.id))
        assert fetched is not None
        assert fetched.step_file_id == step_file_id
        assert fetched.status == "draft"

    def test_get_by_step_file(self, db_session: Session):
        repo = ProductGraphRepository(db_session)
        step_file_id = str(uuid4())
        graph_json = json.dumps({"graphId": str(uuid4()), "nodes": [], "edges": []})
        pg = ProductGraph(step_file_id=step_file_id, graph_json=graph_json, status="draft")
        repo.save(pg)
        db_session.commit()

        fetched = repo.get_by_step_file(UUID(step_file_id))
        assert fetched is not None
        assert fetched.step_file_id == step_file_id

    def test_update_status(self, db_session: Session):
        repo = ProductGraphRepository(db_session)
        pg = ProductGraph(step_file_id=str(uuid4()), graph_json="{}", status="draft")
        repo.save(pg)
        db_session.commit()

        repo.update_status(UUID(pg.id), "generated")
        db_session.commit()

        fetched = repo.get_by_id(UUID(pg.id))
        assert fetched.status == "generated"

    def test_get_by_id_returns_none_for_unknown(self, db_session: Session):
        repo = ProductGraphRepository(db_session)
        assert repo.get_by_id(uuid4()) is None


class TestDraftProcessRepository:
    def test_save_and_get_by_id(self, db_session: Session):
        repo = DraftProcessRepository(db_session)
        dpg = DraftProcessGraph(
            product_graph_id=str(uuid4()),
            graph_json=json.dumps({"processId": str(uuid4()), "status": "reviewing", "steps": []}),
            status="reviewing",
            generated_by="rule_engine",
        )
        repo.save(dpg)
        db_session.commit()

        fetched = repo.get_by_id(UUID(dpg.id))
        assert fetched is not None
        assert fetched.status == "reviewing"

    def test_get_by_product_graph(self, db_session: Session):
        repo = DraftProcessRepository(db_session)
        pg_id = str(uuid4())
        dpg = DraftProcessGraph(
            product_graph_id=pg_id,
            graph_json=json.dumps({"processId": str(uuid4()), "status": "draft", "steps": []}),
            status="draft",
            generated_by="rule_engine",
        )
        repo.save(dpg)
        db_session.commit()

        fetched = repo.get_by_product_graph(UUID(pg_id))
        assert fetched is not None
        assert fetched.product_graph_id == pg_id

    def test_update_status(self, db_session: Session):
        repo = DraftProcessRepository(db_session)
        dpg = DraftProcessGraph(
            product_graph_id=str(uuid4()),
            graph_json="{}",
            status="draft",
            generated_by="rule_engine",
        )
        repo.save(dpg)
        db_session.commit()

        repo.update_status(UUID(dpg.id), "approved")
        db_session.commit()

        fetched = repo.get_by_id(UUID(dpg.id))
        assert fetched.status == "approved"

    def test_update_graph_json(self, db_session: Session):
        repo = DraftProcessRepository(db_session)
        dpg = DraftProcessGraph(
            product_graph_id=str(uuid4()),
            graph_json="{}",
            status="draft",
            generated_by="rule_engine",
        )
        repo.save(dpg)
        db_session.commit()

        new_json = json.dumps({"processId": str(uuid4()), "status": "approved", "steps": [{"title": "Step 1"}]})
        repo.update_graph_json(UUID(dpg.id), new_json, "approved")
        db_session.commit()

        fetched = repo.get_by_id(UUID(dpg.id))
        assert fetched.status == "approved"
        assert "Step 1" in fetched.graph_json

    def test_get_by_id_returns_none_for_unknown(self, db_session: Session):
        repo = DraftProcessRepository(db_session)
        assert repo.get_by_id(uuid4()) is None


class TestApprovedProcessRepository:
    def test_save_and_get_by_id(self, db_session: Session):
        from datetime import datetime, timezone

        repo = ApprovedProcessRepository(db_session)
        apg = ApprovedProcessGraph(
            draft_process_id=str(uuid4()),
            graph_json=json.dumps({"approvedProcessId": str(uuid4()), "approvedBy": "Engineer", "approvedAt": "2026-06-12T00:00:00Z", "steps": []}),
            approved_by="Engineer",
            approved_at=datetime.now(timezone.utc),
        )
        repo.save(apg)
        db_session.commit()

        fetched = repo.get_by_id(UUID(apg.id))
        assert fetched is not None
        assert fetched.approved_by == "Engineer"

    def test_get_by_id_returns_none_for_unknown(self, db_session: Session):
        repo = ApprovedProcessRepository(db_session)
        assert repo.get_by_id(uuid4()) is None


class TestReviewDecisionRepository:
    def test_save_and_get_by_process(self, db_session: Session):
        repo = ReviewDecisionRepository(db_session)
        process_id = str(uuid4())

        rd1 = ReviewDecision(process_id=process_id, step_id=str(uuid4()), action="accept", reason="OK")
        rd2 = ReviewDecision(process_id=process_id, step_id=str(uuid4()), action="modify", reason="Change order")
        repo.save(rd1)
        repo.save(rd2)
        db_session.commit()

        decisions = repo.get_by_process(UUID(process_id))
        assert len(decisions) == 2
        actions = {d.action for d in decisions}
        assert actions == {"accept", "modify"}

    def test_get_by_process_returns_empty_for_unknown(self, db_session: Session):
        repo = ReviewDecisionRepository(db_session)
        assert repo.get_by_process(uuid4()) == []


class TestInstructionRepository:
    def test_save_and_get_by_id(self, db_session: Session):
        repo = InstructionRepository(db_session)
        ai = AssemblyInstruction(
            approved_process_id=str(uuid4()),
            instruction_json=json.dumps({"instructionId": str(uuid4()), "title": "Test", "sections": []}),
        )
        repo.save(ai)
        db_session.commit()

        fetched = repo.get_by_id(UUID(ai.id))
        assert fetched is not None
        assert "Test" in fetched.instruction_json

    def test_get_by_approved_process(self, db_session: Session):
        repo = InstructionRepository(db_session)
        approved_id = str(uuid4())
        ai = AssemblyInstruction(
            approved_process_id=approved_id,
            instruction_json=json.dumps({"instructionId": str(uuid4()), "title": "Test", "sections": []}),
        )
        repo.save(ai)
        db_session.commit()

        fetched = repo.get_by_approved_process(UUID(approved_id))
        assert fetched is not None

    def test_get_by_id_returns_none_for_unknown(self, db_session: Session):
        repo = InstructionRepository(db_session)
        assert repo.get_by_id(uuid4()) is None
