"""
Tests for MARS Multi-Agent Decision System.
Run with: pytest tests/tests.py -v
"""

import pytest
from unittest.mock import patch, MagicMock

# ── Reasoning utilities ────────────────────────────────────────────────────────

from app.reasoning.similarity import compute_similarity
from app.reasoning.outcome_analysis import analyze_outcomes
from app.reasoning.confidence import calculate_confidence
from app.reasoning.explainability import generate_explanation


class TestComputeSimilarity:
    def test_empty_list_returns_zero(self):
        assert compute_similarity([]) == 0.0

    def test_single_case(self):
        cases = [{"distance": 0.2}]
        assert compute_similarity(cases) == pytest.approx(0.8)

    def test_multiple_cases(self):
        cases = [{"distance": 0.0}, {"distance": 0.5}, {"distance": 1.0}]
        # (1.0 + 0.5 + 0.0) / 3
        assert compute_similarity(cases) == pytest.approx(0.5)

    def test_missing_distance_defaults_to_one(self):
        cases = [{}]
        assert compute_similarity(cases) == pytest.approx(0.0)


class TestAnalyzeOutcomes:
    def test_empty_list_returns_zero(self):
        assert analyze_outcomes([]) == 0.0

    def test_all_success(self):
        cases = [{"outcome": "success"}, {"outcome": "success"}]
        assert analyze_outcomes(cases) == pytest.approx(1.0)

    def test_no_success(self):
        cases = [{"outcome": "failure"}, {"outcome": "unknown"}]
        assert analyze_outcomes(cases) == pytest.approx(0.0)

    def test_partial_success(self):
        cases = [{"outcome": "success"}, {"outcome": "failure"}]
        assert analyze_outcomes(cases) == pytest.approx(0.5)


class TestCalculateConfidence:
    def test_weighted_sum(self):
        result = calculate_confidence(similarity=1.0, outcome=1.0, metadata=1.0)
        assert result == pytest.approx(1.0)

    def test_zeros(self):
        assert calculate_confidence(0.0, 0.0, 0.0) == pytest.approx(0.0)

    def test_weights(self):
        # 0.5*0.8 + 0.3*0.6 + 0.2*0.4 = 0.4 + 0.18 + 0.08 = 0.66
        result = calculate_confidence(similarity=0.8, outcome=0.6, metadata=0.4)
        assert result == pytest.approx(0.66)


class TestGenerateExplanation:
    def test_empty_cases(self):
        explanation = generate_explanation([], confidence=0.3)
        assert "No similar" in explanation
        assert "0.30" in explanation

    def test_with_cases(self):
        cases = [{"outcome": "success"}, {"outcome": "failure"}]
        explanation = generate_explanation(cases, confidence=0.75)
        assert "2" in explanation
        assert "0.75" in explanation

    def test_outcome_summary_included(self):
        cases = [{"outcome": "success"}]
        explanation = generate_explanation(cases, confidence=0.9)
        assert "success" in explanation


# ── Finance agent output parser ────────────────────────────────────────────────

from app.agents.finance_agent import parse_finance_output


class TestParseFinanceOutput:
    def test_full_valid_output(self):
        text = (
            "Response:\nProceed with investment.\n\n"
            "Reasoning:\nROI is strong.\n\n"
            "Confidence:\n0.85"
        )
        result = parse_finance_output(text)
        assert "Proceed" in result["response"]
        assert result["confidence"] == pytest.approx(0.85)
        assert "ROI" in result["reasoning"]

    def test_invalid_confidence_defaults(self):
        text = "Response:\nok\nReasoning:\nok\nConfidence:\nnot_a_number"
        result = parse_finance_output(text)
        assert result["confidence"] == pytest.approx(0.5)

    def test_empty_string_returns_defaults(self):
        result = parse_finance_output("")
        assert result["confidence"] == pytest.approx(0.5)


# ── Case retrieval service ─────────────────────────────────────────────────────

from app.services.case_retrieval_service import get_similar_cases


class TestGetSimilarCases:
    @patch("app.services.case_retrieval_service.retrieve_cases")
    def test_returns_normalised_list(self, mock_retrieve):
        mock_retrieve.return_value = {
            "documents": [["Doc A", "Doc B"]],
            "metadatas": [[{"department": "Finance"}, {"department": "Legal"}]],
            "distances": [[0.1, 0.3]],
        }
        cases = get_similar_cases("test query", domain="finance", k=2)
        assert len(cases) == 2
        assert cases[0]["document"] == "Doc A"
        assert cases[0]["distance"] == pytest.approx(0.1)

    @patch("app.services.case_retrieval_service.retrieve_cases")
    def test_empty_results_returns_empty_list(self, mock_retrieve):
        mock_retrieve.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        cases = get_similar_cases("query")
        assert cases == []

    @patch("app.services.case_retrieval_service.retrieve_cases")
    def test_retrieval_exception_propagates(self, mock_retrieve):
        mock_retrieve.side_effect = RuntimeError("DB unavailable")
        with pytest.raises(RuntimeError):
            get_similar_cases("query")


# ── FastAPI route ──────────────────────────────────────────────────────────────

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
