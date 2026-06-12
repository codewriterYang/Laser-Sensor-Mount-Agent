"""E2E tests — Epic-3: Render instruction → Export PDF."""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient


def _step_file(name: str = "test.step") -> tuple:
    return ("file", (name, BytesIO(b"ISO-10303-21;"), "application/octet-stream"))


def _setup_approved(client: TestClient) -> str:
    """Full Epic-1+2 flow to create an ApprovedProcessGraph, return its ID."""
    r = client.post("/api/v1/step/analyze", files=[_step_file("laser_sensor_mount.step")])
    pg_id = r.json()["data"]["productGraphId"]
    r = client.post("/api/v1/process/generate", json={"productGraphId": pg_id})
    process_id = r.json()["data"]["processId"]
    r = client.get(f"/api/v1/process/{process_id}")
    steps = r.json()["data"]["steps"]
    decisions = [{"stepId": s["stepId"], "action": "accept", "reason": "OK"} for s in steps]
    r = client.post("/api/v1/process/review", json={"processId": process_id, "decisions": decisions})
    return r.json()["data"]["approvedProcessId"]


class TestEpic3EndToEnd:
    """Epic-3: ApprovedProcessGraph → AssemblyInstruction → PDF."""

    def test_render_instruction_and_export_pdf(self, client: TestClient):
        approved_id = _setup_approved(client)

        # Render
        r = client.post("/api/v1/instruction/render", json={"approvedProcessId": approved_id})
        assert r.status_code == 200
        instruction_id = r.json()["data"]["instructionId"]

        # Get instruction
        r = client.get(f"/api/v1/instruction/{instruction_id}")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["instructionId"] == instruction_id
        sections = data["sections"]
        assert any(s["sectionType"] == "cover" for s in sections)
        assert any(s["sectionType"] == "step" for s in sections)

        # Export PDF
        r = client.post("/api/v1/instruction/export-pdf", json={"instructionId": instruction_id})
        assert r.status_code == 200
        pdf_path = r.json()["data"]["pdfPath"]
        assert pdf_path.endswith(".pdf")

    def test_render_nonexistent_approved(self, client: TestClient):
        r = client.post("/api/v1/instruction/render", json={
            "approvedProcessId": "00000000-0000-0000-0000-00000000dead"
        })
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "APPROVED_PROCESS_NOT_FOUND"

    def test_export_pdf_nonexistent_instruction(self, client: TestClient):
        r = client.post("/api/v1/instruction/export-pdf", json={
            "instructionId": "00000000-0000-0000-0000-00000000dead"
        })
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "INSTRUCTION_NOT_FOUND"
