from typing import List, Optional
from app.storage.retriever import retrieve_cases


def get_similar_cases(
    query: str, domain: Optional[str] = None, k: int = 5
) -> List[dict]:
    """
    Retrieve the top-k most similar cases for a given query.

    Args:
        query:  The natural language query to search for.
        domain: Optional department filter (e.g. 'finance', 'legal', 'rd', 'operations').
        k:      Number of results to return.

    Returns:
        A list of matching case documents (as dicts) with keys:
        document, metadata, distance, outcome.
    """
    rows = retrieve_cases(query=query, k=k, domain=domain)

    cases = []
    for row in rows:
        document = (
            f"Decision Title: {row.get('decision_title', '')}\n"
            f"Trigger: {row.get('trigger', '')}\n"
            f"Decision Description: {row.get('decision_description', '')}\n"
            f"Reasoning Summary: {row.get('reasoning_summary', '')}\n"
            f"Risk Level: {row.get('risk_level', '')}\n"
            f"Outcome Summary: {row.get('outcome_summary', '')}"
        )

        similarity = row.get("similarity")
        distance = max(0.0, 1 - similarity) if isinstance(similarity, (int, float)) else 1.0

        cases.append(
            {
                "document": document,
                "metadata": {
                    "case_id": row.get("case_id"),
                    "quarter": row.get("quarter", ""),
                    "department": row.get("department", ""),
                    "risk_level": row.get("risk_level", ""),
                    "outcome": row.get("outcome_summary", "unknown"),
                },
                "distance": distance,
                "outcome": row.get("outcome_summary", "unknown"),
            }
        )

    return cases


class CaseRetrievalService:
    """Thin wrapper class for dependency-injection use cases."""

    def retrieve(
        self, query: str, domain: Optional[str] = None, k: int = 5
    ) -> List[dict]:
        return get_similar_cases(query=query, domain=domain, k=k)
