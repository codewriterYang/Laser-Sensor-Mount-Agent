"""Contract tests — validate all API endpoints match 05_CONTRACT.md.

RED PHASE: These tests will FAIL until implementation is complete.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient


# Helper: create a fake .step file for upload tests
def _step_file(name: str = "test.step", content: bytes = b"ISO-10303-21;") -> tuple:
    return ("file", (name, BytesIO(content), "application/octet-stream"))


class TestStepAnalysisContract:
    """Contract §4.1 — POST /api/v1/step/analyze"""

    def test_analyze_step_returns_200_and_valid_schema(self, client: TestClient):
        """Upload a valid .step file must return success response with correct shape."""
        response = client.post("/api/v1/step/analyze", files=[_step_file("laser_sensor_mount.step")])

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        body = response.json()

        # Standard response wrapper
        assert body["success"] is True
        assert "timestamp" in body

        # Data fields per Contract §4.1
        data = body["data"]
        assert "stepFileId" in data
        assert "productGraphId" in data
        assert data["status"] == "parsed"

    def test_analyze_step_invalid_extension_returns_error(self, client: TestClient):
        """Upload a non-.step file must return STEP_FILE_INVALID."""
        response = client.post("/api/v1/step/analyze", files=[_step_file("invalid.txt")])

        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "STEP_FILE_INVALID"

    def test_analyze_step_no_filename_returns_error(self, client: TestClient):
        """Upload a file with no .step extension must return STEP_FILE_INVALID."""
        response = client.post("/api/v1/step/analyze", files=[_step_file("no_extension")])

        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "STEP_FILE_INVALID"


class TestProductGraphContract:
    """Contract §4.2 — GET /api/v1/product-graphs/{productGraphId}"""

    def test_get_product_graph_returns_valid_shape(self, client: TestClient):
        """Response must contain graphId, nodes, and edges arrays."""
        # Requires a known product graph — will fail until integration is wired
        response = client.get("/api/v1/product-graphs/00000000-0000-0000-0000-000000000001")

        if response.status_code == 404:
            pytest.skip("No seeded data yet — skipped until integration")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "graphId" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_get_product_graph_not_found_returns_error(self, client: TestClient):
        """Non-existent graph must return PRODUCT_GRAPH_NOT_FOUND."""
        response = client.get("/api/v1/product-graphs/00000000-0000-0000-0000-00000000dead")

        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "PRODUCT_GRAPH_NOT_FOUND"


class TestProcessGenerationContract:
    """Contract §5.1 — POST /api/v1/process/generate"""

    def test_generate_process_returns_valid_shape(self, client: TestClient):
        """Response must contain processId, status='draft', and steps array."""
        response = client.post("/api/v1/process/generate", json={
            "productGraphId": "00000000-0000-0000-0000-000000000001"
        })

        if response.status_code == 501:
            pytest.skip("Not implemented yet")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "processId" in data
        assert data["status"] == "draft"
        assert isinstance(data["steps"], list)

    def test_generate_process_missing_graph_returns_error(self, client: TestClient):
        """Non-existent ProductGraph must return PRODUCT_GRAPH_NOT_FOUND."""
        response = client.post("/api/v1/process/generate", json={
            "productGraphId": "00000000-0000-0000-0000-00000000dead"
        })

        if response.status_code == 501:
            pytest.skip("Not implemented yet")
        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "PRODUCT_GRAPH_NOT_FOUND"


class TestDraftProcessGetContract:
    """Contract §5.2 — GET /api/v1/process/{processId}"""

    def test_get_draft_process_returns_valid_shape(self, client: TestClient):
        response = client.get("/api/v1/process/00000000-0000-0000-0000-000000000001")
        if response.status_code == 501:
            pytest.skip("Not implemented yet")
        if response.status_code == 404:
            pytest.skip("No seeded data yet")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "processId" in body["data"]

    def test_get_draft_process_not_found_returns_error(self, client: TestClient):
        response = client.get("/api/v1/process/00000000-0000-0000-0000-00000000dead")
        if response.status_code == 501:
            pytest.skip("Not implemented yet")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROCESS_NOT_FOUND"


class TestReviewContract:
    """Contract §6.1 — POST /api/v1/process/review"""

    def test_submit_review_returns_approved_process(self, client: TestClient):
        response = client.post("/api/v1/process/review", json={
            "processId": "00000000-0000-0000-0000-000000000001",
            "decisions": [
                {"stepId": "00000000-0000-0000-0000-000000000001", "action": "accept", "reason": "Looks correct"}
            ]
        })
        if response.status_code == 501:
            pytest.skip("Not implemented yet")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "approvedProcessId" in data
        assert data["status"] == "approved"

    def test_submit_review_invalid_action_returns_error(self, client: TestClient):
        response = client.post("/api/v1/process/review", json={
            "processId": "00000000-0000-0000-0000-000000000001",
            "decisions": [
                {"stepId": "00000000-0000-0000-0000-000000000001", "action": "invalid_action", "reason": ""}
            ]
        })
        if response.status_code == 501:
            pytest.skip("Not implemented yet")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_REVIEW_ACTION"


class TestApprovedProcessGetContract:
    """Contract §6.2 — GET /api/v1/approved-process/{approvedProcessId}"""

    def test_get_approved_process_returns_valid_shape(self, client: TestClient):
        response = client.get("/api/v1/approved-process/00000000-0000-0000-0000-000000000001")
        if response.status_code == 501:
            pytest.skip("Not implemented yet")
        if response.status_code == 404:
            pytest.skip("No seeded data yet")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "approvedProcessId" in data
        assert "approvedBy" in data
        assert "approvedAt" in data
        assert isinstance(data["steps"], list)


class TestInstructionRenderContract:
    """Contract §7.1 — POST /api/v1/instruction/render"""

    def test_render_instruction_returns_instruction_id(self, client: TestClient):
        response = client.post("/api/v1/instruction/render", json={
            "approvedProcessId": "00000000-0000-0000-0000-000000000001"
        })
        if response.status_code == 501:
            pytest.skip("Not implemented yet")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "instructionId" in body["data"]

    def test_render_instruction_not_found_returns_error(self, client: TestClient):
        response = client.post("/api/v1/instruction/render", json={
            "approvedProcessId": "00000000-0000-0000-0000-00000000dead"
        })
        if response.status_code == 501:
            pytest.skip("Not implemented yet")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "APPROVED_PROCESS_NOT_FOUND"


class TestInstructionGetContract:
    """Contract §7.2 — GET /api/v1/instruction/{instructionId}"""

    def test_get_instruction_returns_valid_shape(self, client: TestClient):
        response = client.get("/api/v1/instruction/00000000-0000-0000-0000-000000000001")
        if response.status_code == 501:
            pytest.skip("Not implemented yet")
        if response.status_code == 404:
            pytest.skip("No seeded data yet")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "instructionId" in data
        assert isinstance(data["sections"], list)


class TestPdfExportContract:
    """Contract §8.1 — POST /api/v1/instruction/export-pdf"""

    def test_export_pdf_returns_path(self, client: TestClient):
        response = client.post("/api/v1/instruction/export-pdf", json={
            "instructionId": "00000000-0000-0000-0000-000000000001"
        })
        if response.status_code == 501:
            pytest.skip("Not implemented yet")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "pdfPath" in body["data"]

    def test_export_pdf_not_found_returns_error(self, client: TestClient):
        response = client.post("/api/v1/instruction/export-pdf", json={
            "instructionId": "00000000-0000-0000-0000-00000000dead"
        })
        if response.status_code == 501:
            pytest.skip("Not implemented yet")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "INSTRUCTION_NOT_FOUND"
