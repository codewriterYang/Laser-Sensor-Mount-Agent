"""Contract tests — validate all API endpoints match 05_CONTRACT.md."""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient


# --- helpers ---

def _step_file(name: str = "test.step", content: bytes = b"ISO-10303-21;") -> tuple:
    return ("file", (name, BytesIO(content), "application/octet-stream"))


def _create_product_graph(client: TestClient) -> str:
    """Upload a STEP file and return the productGraphId."""
    r = client.post("/api/v1/step/analyze", files=[_step_file("laser_sensor_mount.step")])
    assert r.status_code == 200
    return r.json()["data"]["productGraphId"]


def _create_draft_process(client: TestClient) -> str:
    """Generate a DraftProcessGraph and return the processId."""
    pg_id = _create_product_graph(client)
    r = client.post("/api/v1/process/generate", json={"productGraphId": pg_id})
    assert r.status_code == 200
    return r.json()["data"]["processId"]


def _create_approved(client: TestClient) -> str:
    """Go through full Epic-1+2 to create an ApprovedProcessGraph, return its ID."""
    process_id = _create_draft_process(client)
    r = client.get(f"/api/v1/process/{process_id}")
    steps = r.json()["data"]["steps"]
    decisions = [{"stepId": s["stepId"], "action": "accept", "reason": "OK"} for s in steps]
    r = client.post("/api/v1/process/review", json={"processId": process_id, "decisions": decisions})
    assert r.status_code == 200
    return r.json()["data"]["approvedProcessId"]


# === Epic-1: STEP Analysis ===


class TestStepAnalysisContract:
    """Contract §4.1 — POST /api/v1/step/analyze"""

    def test_analyze_step_returns_200_and_valid_schema(self, client: TestClient):
        response = client.post("/api/v1/step/analyze", files=[_step_file("laser_sensor_mount.step")])
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "timestamp" in body
        data = body["data"]
        assert "stepFileId" in data
        assert "productGraphId" in data
        assert data["status"] == "parsed"

    def test_analyze_step_invalid_extension_returns_error(self, client: TestClient):
        response = client.post("/api/v1/step/analyze", files=[_step_file("invalid.txt")])
        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "STEP_FILE_INVALID"

    def test_analyze_step_no_filename_returns_error(self, client: TestClient):
        response = client.post("/api/v1/step/analyze", files=[_step_file("no_extension")])
        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "STEP_FILE_INVALID"


class TestProductGraphContract:
    """Contract §4.2 — GET /api/v1/product-graphs/{productGraphId}"""

    def test_get_product_graph_returns_valid_shape(self, client: TestClient):
        pg_id = _create_product_graph(client)
        response = client.get(f"/api/v1/product-graphs/{pg_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "graphId" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        assert len(data["nodes"]) == 6
        assert len(data["edges"]) == 8

    def test_get_product_graph_not_found_returns_error(self, client: TestClient):
        response = client.get("/api/v1/product-graphs/00000000-0000-0000-0000-00000000dead")
        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "PRODUCT_GRAPH_NOT_FOUND"


# === Epic-2: Process Generation ===


class TestProcessGenerationContract:
    """Contract §5.1 — POST /api/v1/process/generate"""

    def test_generate_process_returns_valid_shape(self, client: TestClient):
        pg_id = _create_product_graph(client)
        response = client.post("/api/v1/process/generate", json={"productGraphId": pg_id})

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "processId" in data
        assert data["status"] == "reviewing"
        assert isinstance(data["steps"], list)
        assert len(data["steps"]) >= 1

        # Verify step structure (Contract §9 — DraftProcessGraph)
        for step in data["steps"]:
            assert "stepId" in step
            assert "sequence" in step
            assert step["sequence"] >= 1
            assert "title" in step
            assert len(step["title"]) > 0
            assert "description" in step
            assert len(step["description"]) > 0

    def test_generate_process_missing_graph_returns_error(self, client: TestClient):
        response = client.post("/api/v1/process/generate", json={
            "productGraphId": "00000000-0000-0000-0000-00000000dead"
        })
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PRODUCT_GRAPH_NOT_FOUND"


class TestDraftProcessGetContract:
    """Contract §5.2 — GET /api/v1/process/{processId}"""

    def test_get_draft_process_returns_valid_shape(self, client: TestClient):
        process_id = _create_draft_process(client)
        response = client.get(f"/api/v1/process/{process_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["processId"] == process_id
        assert "steps" in body["data"]

    def test_get_draft_process_not_found_returns_error(self, client: TestClient):
        response = client.get("/api/v1/process/00000000-0000-0000-0000-00000000dead")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROCESS_NOT_FOUND"


# === Epic-2: Review ===


class TestReviewContract:
    """Contract §6.1 — POST /api/v1/process/review"""

    def test_submit_review_accept_returns_approved_process(self, client: TestClient):
        process_id = _create_draft_process(client)

        # Get draft steps to accept them
        r = client.get(f"/api/v1/process/{process_id}")
        steps = r.json()["data"]["steps"]
        decisions = [{"stepId": s["stepId"], "action": "accept", "reason": "OK"} for s in steps]

        response = client.post("/api/v1/process/review", json={
            "processId": process_id,
            "decisions": decisions,
        })

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "approvedProcessId" in data
        assert data["status"] == "approved"

    def test_submit_review_invalid_action_returns_error(self, client: TestClient):
        process_id = _create_draft_process(client)
        response = client.post("/api/v1/process/review", json={
            "processId": process_id,
            "decisions": [
                {"stepId": "00000000-0000-0000-0000-000000000001", "action": "invalid_action", "reason": ""}
            ]
        })
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_REVIEW_ACTION"

    def test_submit_review_empty_decisions_returns_error(self, client: TestClient):
        process_id = _create_draft_process(client)
        response = client.post("/api/v1/process/review", json={
            "processId": process_id,
            "decisions": []
        })
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "REVIEW_REQUIRED"

    def test_submit_review_not_found_returns_error(self, client: TestClient):
        response = client.post("/api/v1/process/review", json={
            "processId": "00000000-0000-0000-0000-00000000dead",
            "decisions": [
                {"stepId": "00000000-0000-0000-0000-000000000001", "action": "accept", "reason": "OK"}
            ]
        })
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROCESS_NOT_FOUND"


class TestApprovedProcessGetContract:
    """Contract §6.2 — GET /api/v1/approved-process/{approvedProcessId}"""

    def test_get_approved_process_returns_valid_shape(self, client: TestClient):
        process_id = _create_draft_process(client)
        r = client.get(f"/api/v1/process/{process_id}")
        steps = r.json()["data"]["steps"]
        decisions = [{"stepId": s["stepId"], "action": "accept", "reason": "OK"} for s in steps]

        review_r = client.post("/api/v1/process/review", json={
            "processId": process_id, "decisions": decisions
        })
        approved_id = review_r.json()["data"]["approvedProcessId"]

        response = client.get(f"/api/v1/approved-process/{approved_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["approvedProcessId"] == approved_id
        assert "approvedBy" in data
        assert "approvedAt" in data
        assert isinstance(data["steps"], list)

    def test_get_approved_process_not_found_returns_error(self, client: TestClient):
        response = client.get("/api/v1/approved-process/00000000-0000-0000-0000-00000000dead")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "APPROVED_PROCESS_NOT_FOUND"


# === Epic-3: Instruction (not implemented) ===


class TestInstructionRenderContract:
    """Contract §7.1 — POST /api/v1/instruction/render"""
    def test_render_instruction_returns_instruction_id(self, client: TestClient):
        approved_id = _create_approved(client)
        response = client.post("/api/v1/instruction/render", json={
            "approvedProcessId": approved_id
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        body = response.json()
        assert body["success"] is True
        assert "instructionId" in body["data"]

    def test_render_instruction_not_found_returns_error(self, client: TestClient):
        response = client.post("/api/v1/instruction/render", json={
            "approvedProcessId": "00000000-0000-0000-0000-00000000dead"
        })
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "APPROVED_PROCESS_NOT_FOUND"


class TestInstructionGetContract:
    """Contract §7.2 — GET /api/v1/instruction/{instructionId}"""
    def test_get_instruction_returns_valid_shape(self, client: TestClient):
        approved_id = _create_approved(client)
        r = client.post("/api/v1/instruction/render", json={"approvedProcessId": approved_id})
        instruction_id = r.json()["data"]["instructionId"]

        response = client.get(f"/api/v1/instruction/{instruction_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["instructionId"] == instruction_id
        assert isinstance(data["sections"], list)
        assert len(data["sections"]) >= 2  # cover + overview + at least one step

    def test_get_instruction_not_found_returns_error(self, client: TestClient):
        response = client.get("/api/v1/instruction/00000000-0000-0000-0000-00000000dead")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "INSTRUCTION_NOT_FOUND"


class TestPdfExportContract:
    """Contract §8.1 — POST /api/v1/instruction/export-pdf"""
    def test_export_pdf_returns_path(self, client: TestClient):
        approved_id = _create_approved(client)
        r = client.post("/api/v1/instruction/render", json={"approvedProcessId": approved_id})
        instruction_id = r.json()["data"]["instructionId"]

        response = client.post("/api/v1/instruction/export-pdf", json={
            "instructionId": instruction_id
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        body = response.json()
        assert body["success"] is True
        assert "pdfPath" in body["data"]
        assert body["data"]["pdfPath"].endswith(".pdf")

    def test_export_pdf_not_found_returns_error(self, client: TestClient):
        response = client.post("/api/v1/instruction/export-pdf", json={
            "instructionId": "00000000-0000-0000-0000-00000000dead"
        })
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "INSTRUCTION_NOT_FOUND"
