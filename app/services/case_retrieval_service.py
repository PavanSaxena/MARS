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
        A list of matching case documents (as dicts).
    """
    raw = retrieve_cases(query=query, k=k, domain=domain)

    # ChromaDB returns a dict with lists; normalise into a list of dicts
    cases = []
    if raw and "documents" in raw:
        documents = raw["documents"][0] if raw["documents"] else []
        metadatas = raw.get("metadatas", [[]])[0] or []
        distances = raw.get("distances", [[]])[0] or []

        for i, doc in enumerate(documents):
            cases.append(
                {
                    "document": doc,
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "distance": distances[i] if i < len(distances) else 1.0,
                    "outcome": (
                        (metadatas[i] or {}).get("outcome", "unknown")
                        if i < len(metadatas)
                        else "unknown"
                    ),
                }
            )

    return cases


class CaseRetrievalService:
    """Thin wrapper class for dependency-injection use cases."""

    def retrieve(
        self, query: str, domain: Optional[str] = None, k: int = 5
    ) -> List[dict]:
        return get_similar_cases(query=query, domain=domain, k=k)
