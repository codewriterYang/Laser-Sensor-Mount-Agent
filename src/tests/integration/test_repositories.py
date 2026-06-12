"""Integration tests for Repositories (06_DATABASE.md §12)."""

from __future__ import annotations

import json
import os
import tempfile
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.app.models.orm import Base, ProductGraph, StepFile
from src.app.repositories.product_graph_repository import ProductGraphRepository
from src.app.repositories.step_file_repository import StepFileRepository


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
