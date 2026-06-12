"""E2E tests — Epic-2: Process generation → Review → ApprovedProcessGraph."""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient


def _step_file(name: str = "test.step") -> tuple:
    return ("file", (name, BytesIO(b"ISO-10303-21;"), "application/octet-stream"))


class TestEpic2EndToEnd:
    """Epic-2: ProductGraph → DraftProcessGraph → Review → ApprovedProcessGraph."""

    def test_full_e2e_flow(self, client: TestClient):
        """Complete Epic-1 + Epic-2 flow: upload → generate → review → query approved."""
        # 1. Upload STEP (Epic-1)
        r = client.post("/api/v1/step/analyze", files=[_step_file("laser_sensor_mount.step")])
        assert r.status_code == 200
        pg_id = r.json()["data"]["productGraphId"]

        # 2. Generate DraftProcessGraph
        r = client.post("/api/v1/process/generate", json={"productGraphId": pg_id})
        assert r.status_code == 200
        data = r.json()["data"]
        process_id = data["processId"]
        assert data["status"] == "reviewing"
        assert len(data["steps"]) == 5

        # Verify domain rules in step order
        step_names = [s["title"] for s in data["steps"]]
        assert any("base" in name.lower() or "plate" in name.lower() for name in step_names[:1])

        # 3. Get DraftProcessGraph
        r = client.get(f"/api/v1/process/{process_id}")
        assert r.status_code == 200
        assert r.json()["data"]["processId"] == process_id
        steps = r.json()["data"]["steps"]

        # 4. Submit review — accept all steps
        decisions = [{"stepId": s["stepId"], "action": "accept", "reason": "Approved"} for s in steps]
        r = client.post("/api/v1/process/review", json={
            "processId": process_id,
            "decisions": decisions,
        })
        assert r.status_code == 200
        review_data = r.json()["data"]
        approved_id = review_data["approvedProcessId"]
        assert review_data["status"] == "approved"

        # 5. Get ApprovedProcessGraph
        r = client.get(f"/api/v1/approved-process/{approved_id}")
        assert r.status_code == 200
        approved = r.json()["data"]
        assert approved["approvedProcessId"] == approved_id
        assert approved["approvedBy"] == "Engineer"
        assert "approvedAt" in approved
        assert len(approved["steps"]) == 5

    def test_review_with_modify(self, client: TestClient):
        """Engineer modifies a step during review."""
        # Setup
        r = client.post("/api/v1/step/analyze", files=[_step_file("laser_sensor_mount.step")])
        pg_id = r.json()["data"]["productGraphId"]
        r = client.post("/api/v1/process/generate", json={"productGraphId": pg_id})
        process_id = r.json()["data"]["processId"]
        r = client.get(f"/api/v1/process/{process_id}")
        steps = r.json()["data"]["steps"]

        # Modify the first step
        decisions = []
        for s in steps:
            if s["sequence"] == 1:
                decisions.append({"stepId": s["stepId"], "action": "modify", "reason": "Add lubrication"})
            else:
                decisions.append({"stepId": s["stepId"], "action": "accept", "reason": "OK"})

        r = client.post("/api/v1/process/review", json={
            "processId": process_id, "decisions": decisions
        })
        assert r.status_code == 200
        approved_id = r.json()["data"]["approvedProcessId"]

        r = client.get(f"/api/v1/approved-process/{approved_id}")
        approved = r.json()["data"]
        assert len(approved["steps"]) == 5
        first_step = approved["steps"][0]
        assert "Modified" in first_step["title"]

    def test_review_with_delete(self, client: TestClient):
        """Engineer deletes a step during review."""
        # Setup
        r = client.post("/api/v1/step/analyze", files=[_step_file("laser_sensor_mount.step")])
        pg_id = r.json()["data"]["productGraphId"]
        r = client.post("/api/v1/process/generate", json={"productGraphId": pg_id})
        process_id = r.json()["data"]["processId"]
        r = client.get(f"/api/v1/process/{process_id}")
        steps = r.json()["data"]["steps"]

        # Delete the last step (Washer)
        decisions = []
        for s in steps:
            if s["sequence"] == 5:
                decisions.append({"stepId": s["stepId"], "action": "delete", "reason": "Not needed"})
            else:
                decisions.append({"stepId": s["stepId"], "action": "accept", "reason": "OK"})

        r = client.post("/api/v1/process/review", json={
            "processId": process_id, "decisions": decisions
        })
        assert r.status_code == 200
        approved_id = r.json()["data"]["approvedProcessId"]

        r = client.get(f"/api/v1/approved-process/{approved_id}")
        approved = r.json()["data"]
        assert len(approved["steps"]) == 4  # One deleted

    def test_error_review_empty_decisions(self, client: TestClient):
        """Empty decisions must return REVIEW_REQUIRED."""
        r = client.post("/api/v1/step/analyze", files=[_step_file("laser_sensor_mount.step")])
        pg_id = r.json()["data"]["productGraphId"]
        r = client.post("/api/v1/process/generate", json={"productGraphId": pg_id})
        process_id = r.json()["data"]["processId"]

        r = client.post("/api/v1/process/review", json={
            "processId": process_id, "decisions": []
        })
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "REVIEW_REQUIRED"

    def test_error_generate_nonexistent_graph(self, client: TestClient):
        """Non-existent ProductGraph must return PRODUCT_GRAPH_NOT_FOUND."""
        r = client.post("/api/v1/process/generate", json={
            "productGraphId": "00000000-0000-0000-0000-00000000dead"
        })
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "PRODUCT_GRAPH_NOT_FOUND"
