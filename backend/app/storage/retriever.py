from typing import List, Optional

from app.services.supabase_client import get_supabase_client
from app.storage.embedder import get_embedding

# Map friendly agent-facing names to the department values stored in Supabase
_DOMAIN_MAP = {
    "rd": "R&D",
    "r&d": "R&D",
    "finance": "Finance",
    "legal": "Legal",
    "operations": "Operations",
}


def retrieve_cases(
    query: str,
    k: int = 5,
    domain: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> List[dict]:
    """
    Query Supabase (pgvector) for the k most similar historical decisions to
    `query`, via the `match_decisions` RPC (backend/sql/001_setup.sql).

    Embeds the query with all-MiniLM-L6-v2, optionally filters by
    department, and optionally excludes decisions made after `as_of_date`.
    Each returned row already includes its outcome (joined server-side in
    the RPC), so callers get precedent + what happened next in one call.

    Returns a list of row dicts (case_id, decision_title, ..., similarity),
    ordered by similarity descending.
    """
    vector = get_embedding(query)
    mapped_domain = _DOMAIN_MAP.get(domain.lower(), domain) if domain else None

    supabase = get_supabase_client()
    response = supabase.rpc(
        "match_decisions",
        {
            "query_embedding": vector,
            "match_count": k,
            "filter_department": mapped_domain,
            "as_of_date": as_of_date,
        },
    ).execute()

    return response.data or []
