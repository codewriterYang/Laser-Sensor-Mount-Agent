"""Unit tests for ProcessGenerationService."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.app.models.orm import Base, ProductGraph
from src.app.services.process_generation_service import (
    ProcessGenerationFailedError,
    ProcessGenerationService,
    ProductGraphNotFoundError,
)


DEMO_GRAPH_JSON = json.dumps({
    "graphId": str(uuid4()),
    "nodes": [
        {"nodeId": "a1000000-0000-0000-0000-000000000001", "nodeType": "assembly", "name": "Laser Sensor Mount Assembly"},
        {"nodeId": "a1000000-0000-0000-0000-000000000002", "nodeType": "part", "name": "Base Plate", "metadata": {"material": "Aluminum 6061"}},
        {"nodeId": "a1000000-0000-0000-0000-000000000003", "nodeType": "part", "name": "Bracket", "metadata": {"material": "Steel"}},
        {"nodeId": "a1000000-0000-0000-0000-000000000004", "nodeType": "part", "name": "Laser Sensor"},
        {"nodeId": "a1000000-0000-0000-0000-000000000005", "nodeType": "part", "name": "Screw M4x12"},
        {"nodeId": "a1000000-0000-0000-0000-000000000006", "nodeType": "part", "name": "Washer M4"},
    ],
    "edges": [
        {"edgeId": "e1", "source": "a1000000-0000-0000-0000-000000000001", "target": "a1000000-0000-0000-0000-000000000002", "relation": "contains"},
        {"edgeId": "e2", "source": "a1000000-0000-0000-0000-000000000001", "target": "a1000000-0000-0000-0000-000000000003", "relation": "contains"},
        {"edgeId": "e3", "source": "a1000000-0000-0000-0000-000000000003", "target": "a1000000-0000-0000-0000-000000000004", "relation": "attached_to"},
        {"edgeId": "e4", "source": "a1000000-0000-0000-0000-000000000003", "target": "a1000000-0000-0000-0000-000000000005", "relation": "fastened_by"},
        {"edgeId": "e5", "source": "a1000000-0000-0000-0000-000000000005", "target": "a1000000-0000-0000-0000-000000000006", "relation": "contains"},
    ],
})


class TestProcessGenerationService:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.session = Session(bind=self.engine)
        self.svc = ProcessGenerationService(self.session)
        # Seed a ProductGraph
        self.pg = ProductGraph(
            id=str(uuid4()),
            step_file_id=str(uuid4()),
            graph_json=DEMO_GRAPH_JSON,
            status="generated",
        )
        self.session.add(self.pg)
        self.session.commit()
        self.pg_id = self.pg.id
        yield
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)

    # --- Success cases ---

    def test_generate_returns_process_id_and_draft(self):
        """Generate must return processId and DraftProcessGraph with steps."""
        process_id, draft = self.svc.generate(self.pg_id)

        assert process_id is not None
        assert draft.processId == process_id
        assert draft.status == "reviewing"
        assert len(draft.steps) == 5  # 5 parts

    def test_generated_steps_have_continuous_sequence(self):
        """Invariant: sequence must be continuous and start from 1."""
        _, draft = self.svc.generate(self.pg_id)

        sequences = [s.sequence for s in draft.steps]
        assert sequences == list(range(1, len(sequences) + 1))

    def test_generated_steps_have_required_fields(self):
        """Invariant: each step must have title and description."""
        _, draft = self.svc.generate(self.pg_id)

        for step in draft.steps:
            assert step.title, f"Step {step.sequence} has empty title"
            assert step.description, f"Step {step.sequence} has empty description"
            assert step.sequence >= 1

    def test_base_plate_is_first_step(self):
        """Domain Rule: Base First — base/plate parts come first."""
        _, draft = self.svc.generate(self.pg_id)

        first_step = draft.steps[0]
        assert "base" in first_step.title.lower() or "plate" in first_step.title.lower()

    def test_washer_after_screw(self):
        """Domain Rule: Washer Follow Fastener."""
        _, draft = self.svc.generate(self.pg_id)

        screw_idx = None
        washer_idx = None
        for i, s in enumerate(draft.steps):
            if "screw" in s.title.lower():
                screw_idx = i
            if "washer" in s.title.lower():
                washer_idx = i

        assert screw_idx is not None, "Screw step not found"
        assert washer_idx is not None, "Washer step not found"
        assert washer_idx > screw_idx, f"Washer ({washer_idx}) must be after Screw ({screw_idx})"

    def test_sensor_after_bracket(self):
        """Domain Rule: Sensor After Mount."""
        _, draft = self.svc.generate(self.pg_id)

        bracket_idx = None
        sensor_idx = None
        for i, s in enumerate(draft.steps):
            if "bracket" in s.title.lower():
                bracket_idx = i
            if "sensor" in s.title.lower():
                sensor_idx = i

        assert bracket_idx is not None, "Bracket step not found"
        assert sensor_idx is not None, "Sensor step not found"
        assert sensor_idx > bracket_idx, f"Sensor ({sensor_idx}) must be after Bracket ({bracket_idx})"

    def test_get_draft_returns_none_for_unknown(self):
        """get_draft must return None for unknown ID."""
        result = self.svc.get_draft(uuid4())
        assert result is None

    def test_get_draft_returns_draft_for_known(self):
        """get_draft must return DraftProcessGraph for known ID."""
        process_id, _ = self.svc.generate(self.pg_id)
        draft = self.svc.get_draft(process_id)
        assert draft is not None
        assert draft.processId == process_id

    # --- Error cases ---

    def test_generate_nonexistent_graph_raises(self):
        """Non-existent ProductGraph must raise ProductGraphNotFoundError."""
        with pytest.raises(ProductGraphNotFoundError):
            self.svc.generate(uuid4())
