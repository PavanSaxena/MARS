from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestQueryRoute:
    @patch("app.api.routes.run_graph", return_value="Final decision: proceed.")
    def test_valid_query(self, mock_run):
        response = client.post("/api/query", json={"query": "Should we expand?"})
        assert response.status_code == 200
        assert response.json()["result"] == "Final decision: proceed."

    def test_empty_query_returns_400(self):
        response = client.post("/api/query", json={"query": "   "})
        assert response.status_code == 400

    def test_missing_query_field_returns_422(self):
        response = client.post("/api/query", json={})
        assert response.status_code == 422

    def test_root_health_check(self):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
