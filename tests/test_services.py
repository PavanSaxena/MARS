import pytest
from unittest.mock import patch

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
