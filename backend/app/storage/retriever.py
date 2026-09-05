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


def retrieve_cases(query: str, k: int = 5, domain: Optional[str] = None) -> List[dict]:
    """
    Query Supabase (pgvector) for the k most similar cases via the
    `match_decision_cases` RPC function.

    Requires the one-time SQL setup in backend/sql/001_pgvector_setup.sql to
    have been run in Supabase, and backend/app/storage/index_cases.py to have
    been run at least once to populate the `embedding` column.

    Returns a list of row dicts (case_id, decision_title, ..., similarity).
    """
    vector = get_embedding(query)
    mapped_domain = _DOMAIN_MAP.get(domain.lower(), domain) if domain else None

    supabase = get_supabase_client()
    response = supabase.rpc(
        "match_decision_cases",
        {
            "query_embedding": vector,
            "match_count": k,
            "filter_department": mapped_domain,
        },
    ).execute()

    return response.data or []


def retrieve_verified_cases(
    query: str,
    as_of_date: Optional[str] = None,
    k: int = 5,
    domain: Optional[str] = None,
) -> List[dict]:
    """
    Query Supabase (pgvector) for the k most similar verified decision cases
    via the `match_verified_decisions` RPC function.

    Guarantees:
      - Uses embeddings generated strictly from decision-time facts (no outcome leakage).
      - Applies `as_of_date` cutoff so decisions after that date are excluded.
      - Never returns future outcome fields.
    """
    vector = get_embedding(query)
    mapped_domain = _DOMAIN_MAP.get(domain.lower(), domain) if domain else None

    supabase = get_supabase_client()
    response = supabase.rpc(
        "match_verified_decisions",
        {
            "query_embedding": vector,
            "as_of_date": as_of_date,
            "match_count": k,
            "filter_department": mapped_domain,
        },
    ).execute()

    return response.data or []

