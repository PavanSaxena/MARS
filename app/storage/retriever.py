from typing import Optional
from app.storage.chroma_client import get_collection
from app.storage.embedder import get_embedding


def retrieve_cases(query: str, k: int = 5, domain: Optional[str] = None) -> dict:
    """
    Query ChromaDB for the k most similar cases.

    Args:
        query:  Natural language query string.
        k:      Number of results to retrieve.
        domain: Optional department filter applied as a ChromaDB `where` clause.

    Returns:
        Raw ChromaDB query result dict.
    """
    collection = get_collection()
    vector = get_embedding(query)

    where_filter = None
    if domain:
        # Map friendly names to the department values stored in metadata
        domain_map = {
            "rd": "R&D",
            "r&d": "R&D",
            "finance": "Finance",
            "legal": "Legal",
            "operations": "Operations",
        }
        mapped = domain_map.get(domain.lower(), domain)
        where_filter = {"department": {"$eq": mapped}}

    query_kwargs = dict(
        query_embeddings=[vector],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    if where_filter:
        query_kwargs["where"] = where_filter

    results = collection.query(**query_kwargs)
    return results
