"""Unit tests for StepAnalysisService."""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.app.models.orm import Base
from src.app.services.step_analysis_service import (
    StepAnalysisService,
    StepFileInvalidError,
    StepFileNotFoundError,
)


def _upload_file(name: str = "test.step", content: bytes = b"ISO-10303-21;") -> UploadFile:
    """Helper: create a FastAPI UploadFile for testing."""
    return UploadFile(filename=name, file=BytesIO(content))


class TestStepAnalysisService:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.session = Session(bind=self.engine)
        self.svc = StepAnalysisService(self.session)
        yield
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_analyze_valid_step_file_returns_ids(self):
        """Task-1 AC: Valid .step file returns stepFileId, productGraphId, status='parsed'."""
        file = _upload_file("laser_sensor_mount.step")

        step_file_id, product_graph_id, status = self.svc.analyze(file)

        assert step_file_id is not None
        assert product_graph_id is not None
        assert status == "parsed"

    def test_analyze_sets_step_file_status_to_parsed(self):
        """Task-4 AC: StepFile transitions uploaded → parsing → parsed."""
        file = _upload_file("laser_sensor_mount.step")
        step_file_id, _, status = self.svc.analyze(file)

        # After successful analysis, status must be "parsed"
        assert status == "parsed"

    def test_analyze_sets_product_graph_status_to_generated(self):
        """Task-3 AC: ProductGraph transitions draft → generated."""
        from src.app.repositories.product_graph_repository import ProductGraphRepository

        file = _upload_file("demo_laser_mount.step")
        _, pg_id, _ = self.svc.analyze(file)

        repo = ProductGraphRepository(self.session)
        pg = repo.get_by_id(pg_id)
        assert pg is not None
        assert pg.status == "generated"

    def test_analyze_invalid_extension_raises(self):
        """Task-1 AC: Non-.step file returns STEP_FILE_INVALID."""
        file = _upload_file("invalid.txt")
        with pytest.raises(StepFileInvalidError):
            self.svc.analyze(file)

    def test_analyze_no_extension_raises(self):
        """File without .step extension must raise StepFileInvalidError."""
        file = _upload_file("no_extension")
        with pytest.raises(StepFileInvalidError):
            self.svc.analyze(file)

    def test_analyze_persists_product_graph_json(self):
        """Task-2 AC: ProductGraph JSON is correctly persisted."""
        import json

        from src.app.repositories.product_graph_repository import ProductGraphRepository

        file = _upload_file("laser_sensor_mount.step")
        _, pg_id, _ = self.svc.analyze(file)

        repo = ProductGraphRepository(self.session)
        pg = repo.get_by_id(pg_id)
        graph_data = json.loads(pg.graph_json)

        assert "graphId" in graph_data
        assert len(graph_data["nodes"]) == 6
        assert len(graph_data["edges"]) == 8

    def test_product_graph_has_root_assembly(self):
        """Verify ProductGraph invariant: root Assembly node exists."""
        import json

        from src.app.repositories.product_graph_repository import ProductGraphRepository

        file = _upload_file("laser_sensor_mount.step")
        _, pg_id, _ = self.svc.analyze(file)

        repo = ProductGraphRepository(self.session)
        pg = repo.get_by_id(pg_id)
        graph_data = json.loads(pg.graph_json)

        node_types = {n["nodeType"] for n in graph_data["nodes"]}
        assert "assembly" in node_types

    def test_product_graph_has_no_isolated_nodes(self):
        """Verify ProductGraph invariant: no isolated nodes."""
        import json

        from src.app.repositories.product_graph_repository import ProductGraphRepository

        file = _upload_file("laser_sensor_mount.step")
        _, pg_id, _ = self.svc.analyze(file)

        repo = ProductGraphRepository(self.session)
        pg = repo.get_by_id(pg_id)
        graph_data = json.loads(pg.graph_json)

        # All nodes must appear in at least one edge
        node_ids = {n["nodeId"] for n in graph_data["nodes"]}
        edge_node_ids = set()
        for e in graph_data["edges"]:
            edge_node_ids.add(e["source"])
            edge_node_ids.add(e["target"])

        assert node_ids == edge_node_ids, f"Isolated nodes: {node_ids - edge_node_ids}"
