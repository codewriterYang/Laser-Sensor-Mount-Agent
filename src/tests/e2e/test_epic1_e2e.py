"""E2E tests — Epic-1: STEP file upload → ProductGraph generation."""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient


def _step_file(name: str = "test.step", content: bytes = b"ISO-10303-21;") -> tuple:
    """Helper: create a fake .step file for upload tests."""
    return ("file", (name, BytesIO(content), "application/octet-stream"))


class TestEpic1EndToEnd:
    """Epic-1: Complete flow — STEP upload → ProductGraph → Query."""

    def test_full_e2e_flow(self, client: TestClient):
        """Verify: Upload STEP → get stepFileId + productGraphId → query ProductGraph."""
        # 1. Upload and analyze STEP file
        r = client.post("/api/v1/step/analyze", files=[_step_file("laser_sensor_mount.step")])
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["data"]["status"] == "parsed"
        step_file_id = body["data"]["stepFileId"]
        product_graph_id = body["data"]["productGraphId"]

        # 2. Get ProductGraph
        r = client.get(f"/api/v1/product-graphs/{product_graph_id}")
        assert r.status_code == 200
        pg = r.json()
        assert len(pg["data"]["nodes"]) == 6
        assert len(pg["data"]["edges"]) == 8

        # 3. Verify ProductGraph invariants
        node_types = {n["nodeType"] for n in pg["data"]["nodes"]}
        assert "assembly" in node_types

        edge_relations = {e["relation"] for e in pg["data"]["edges"]}
        assert "contains" in edge_relations
        assert "attached_to" in edge_relations
        assert "fastened_by" in edge_relations

    def test_error_flow_invalid_extension(self, client: TestClient):
        """Error: non-.step file returns STEP_FILE_INVALID."""
        r = client.post("/api/v1/step/analyze", files=[_step_file("document.pdf")])
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "STEP_FILE_INVALID"

    def test_error_flow_no_extension(self, client: TestClient):
        """Error: file without .step extension returns STEP_FILE_INVALID."""
        r = client.post("/api/v1/step/analyze", files=[_step_file("noext")])
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "STEP_FILE_INVALID"
