import pytest

from app.reasoning.confidence import calculate_confidence
from app.reasoning.explainability import generate_explanation
from app.reasoning.outcome_analysis import analyze_outcomes
from app.reasoning.similarity import compute_similarity


class TestComputeSimilarity:
    def test_empty_list_returns_zero(self):
        assert compute_similarity([]) == 0.0

    def test_single_case(self):
        cases = [{"distance": 0.2}]
        assert compute_similarity(cases) == pytest.approx(0.8)

    def test_multiple_cases(self):
        cases = [{"distance": 0.0}, {"distance": 0.5}, {"distance": 1.0}]
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
