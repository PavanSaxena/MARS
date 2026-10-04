import logging
from typing import List, Optional

from app.services.supabase_client import get_supabase_client
from app.storage.embedder import get_embedding

logger = logging.getLogger(__name__)

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
    mapped_domain = _DOMAIN_MAP.get(domain.lower(), domain) if domain else None
    logger.info("embedding_requested domain=%s", mapped_domain)
    vector = get_embedding(query)

    supabase = get_supabase_client()
    logger.info("case_retrieval_started domain=%s k=%d", mapped_domain, k)
    try:
        response = supabase.rpc(
            "match_decisions",
            {
                "query_embedding": vector,
                "match_count": k,
                "filter_department": mapped_domain,
                "as_of_date": as_of_date,
            },
        ).execute()
    except Exception:
        logger.exception("case_retrieval_failed domain=%s", mapped_domain)
        raise

    logger.info("case_retrieval_finished domain=%s results=%d", mapped_domain, len(response.data or []))
    return response.data or []
