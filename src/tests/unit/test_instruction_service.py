"""Unit tests for InstructionService."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.app.models.orm import ApprovedProcessGraph, AssemblyInstruction, Base
from src.app.services.instruction_service import (
    ApprovedProcessNotFoundError,
    InstructionNotFoundError,
    InstructionService,
)

DEMO_APPROVED_JSON = json.dumps({
    "approvedProcessId": str(uuid4()),
    "approvedBy": "Engineer",
    "approvedAt": "2026-06-12T00:00:00Z",
    "steps": [
        {"stepId": "00000000-0000-0000-0000-000000000001", "sequence": 1, "title": "Install Base Plate", "description": "Place the base plate", "requiredParts": ["Base Plate"], "requiredTools": []},
        {"stepId": "00000000-0000-0000-0000-000000000002", "sequence": 2, "title": "Install Bracket", "description": "Mount the bracket", "requiredParts": ["Bracket"], "requiredTools": ["Hex Wrench"]},
        {"stepId": "00000000-0000-0000-0000-000000000003", "sequence": 3, "title": "Install Sensor", "description": "Attach sensor to bracket", "requiredParts": ["Laser Sensor", "Bracket"], "requiredTools": ["Hex Wrench"]},
    ],
})


class TestInstructionService:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.session = Session(bind=self.engine)
        self.svc = InstructionService(self.session)
        self.approved_id = str(uuid4())
        apg = ApprovedProcessGraph(
            id=self.approved_id,
            draft_process_id=str(uuid4()),
            graph_json=DEMO_APPROVED_JSON,
            approved_by="Engineer",
            approved_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
        )
        self.session.add(apg)
        self.session.commit()
        yield
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_render_returns_instruction_id_and_schema(self):
        instruction_id, instruction = self.svc.render(UUID(self.approved_id))
        assert instruction_id is not None
        assert instruction.instructionId == instruction_id
        assert len(instruction.sections) >= 2

    def test_render_sections_have_all_types(self):
        _, instruction = self.svc.render(UUID(self.approved_id))
        types = {s.sectionType for s in instruction.sections}
        assert "cover" in types
        assert "overview" in types
        assert "step" in types
        assert "safety" in types
        assert "ending" in types

    def test_render_step_sections_match_approved_steps(self):
        _, instruction = self.svc.render(UUID(self.approved_id))
        step_sections = [s for s in instruction.sections if s.sectionType == "step"]
        assert len(step_sections) == 3

    def test_render_nonexistent_approved_raises(self):
        with pytest.raises(ApprovedProcessNotFoundError):
            self.svc.render(uuid4())

    def test_get_instruction_returns_schema(self):
        instruction_id, _ = self.svc.render(UUID(self.approved_id))
        result = self.svc.get_instruction(instruction_id)
        assert result is not None
        assert result.instructionId == instruction_id

    def test_get_instruction_returns_none_for_unknown(self):
        assert self.svc.get_instruction(uuid4()) is None

    def test_export_pdf_creates_file(self):
        instruction_id, _ = self.svc.render(UUID(self.approved_id))
        pdf_path = self.svc.export_pdf(instruction_id)
        assert pdf_path.endswith(".pdf")
        assert Path(pdf_path).exists()

    def test_export_pdf_nonexistent_instruction_raises(self):
        from src.app.services.instruction_service import InstructionNotFoundError
        with pytest.raises(InstructionNotFoundError):
            self.svc.export_pdf(uuid4())
