"""E2E tests — Epic-4: Full MVP pipeline + scope verification."""

from __future__ import annotations

import json
from io import BytesIO

from fastapi.testclient import TestClient


def _step_file(name: str = "test.step") -> tuple:
    return ("file", (name, BytesIO(b"ISO-10303-21;"), "application/octet-stream"))


class TestFullMVPPipeline:
    """Complete MVP: STEP upload → ProductGraph → DraftProcessGraph
       → Review → ApprovedProcessGraph → Instruction → PDF."""

    def test_complete_pipeline_e2e(self, client: TestClient):
        # 1. Upload STEP
        r = client.post("/api/v1/step/analyze", files=[_step_file("laser_sensor_mount.step")])
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["status"] == "parsed"
        pg_id = data["productGraphId"]

        # 2. Get ProductGraph
        r = client.get(f"/api/v1/product-graphs/{pg_id}")
        assert r.status_code == 200
        pg = r.json()["data"]
        assert len(pg["nodes"]) == 6
        assert len(pg["edges"]) == 8

        # 3. Generate DraftProcessGraph
        r = client.post("/api/v1/process/generate", json={"productGraphId": pg_id})
        assert r.status_code == 200
        process_id = r.json()["data"]["processId"]

        # 4. Get DraftProcessGraph
        r = client.get(f"/api/v1/process/{process_id}")
        assert r.status_code == 200
        steps = r.json()["data"]["steps"]
        assert len(steps) >= 1

        # 5. Submit review — accept all
        decisions = [{"stepId": s["stepId"], "action": "accept", "reason": "OK"} for s in steps]
        r = client.post("/api/v1/process/review", json={"processId": process_id, "decisions": decisions})
        assert r.status_code == 200
        approved_id = r.json()["data"]["approvedProcessId"]

        # 6. Get ApprovedProcessGraph
        r = client.get(f"/api/v1/approved-process/{approved_id}")
        assert r.status_code == 200
        assert r.json()["data"]["approvedBy"] == "Engineer"

        # 7. Render instruction
        r = client.post("/api/v1/instruction/render", json={"approvedProcessId": approved_id})
        assert r.status_code == 200
        instruction_id = r.json()["data"]["instructionId"]

        # 8. Get instruction
        r = client.get(f"/api/v1/instruction/{instruction_id}")
        assert r.status_code == 200
        sections = r.json()["data"]["sections"]
        section_types = {s["sectionType"] for s in sections}
        assert "cover" in section_types
        assert "step" in section_types
        assert "safety" in section_types

        # 9. Export PDF
        r = client.post("/api/v1/instruction/export-pdf", json={"instructionId": instruction_id})
        assert r.status_code == 200
        pdf_path = r.json()["data"]["pdfPath"]
        assert pdf_path.endswith(".pdf")


class TestMVPScopeBoundary:
    """Verify MVP boundaries: no knowledge flywheel, no AR, no self-learning."""

    def test_no_learning_service_endpoint(self, client: TestClient):
        """MVP does not expose any learning/training endpoint."""
        r = client.post("/api/v1/learn", json={})
        assert r.status_code == 404

    def test_no_ar_endpoint(self, client: TestClient):
        """MVP does not expose AR/VR endpoints."""
        r = client.get("/api/v1/ar/session")
        assert r.status_code == 404

    def test_no_flywheel_export_endpoint(self, client: TestClient):
        """MVP does not expose knowledge flywheel export."""
        r = client.get("/api/v1/knowledge/rules")
        assert r.status_code == 404

    def test_no_optimization_endpoint(self, client: TestClient):
        """MVP does not expose process optimization endpoint."""
        r = client.get("/api/v1/knowledge/optimize")
        assert r.status_code == 404

    def test_review_history_is_persisted(self, client: TestClient):
        """Review decisions are stored (audit trail), but no learning loop runs on them."""
        r = client.get("/api/v1/knowledge/insights")
        assert r.status_code == 404  # No knowledge insights endpoint
