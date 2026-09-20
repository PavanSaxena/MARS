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


def retrieve_cases(query: str, k: int = 5, domain: Optional[str] = None) -> List[dict]:
    """
    Query Supabase (pgvector) for the k most similar cases via the
    `match_decision_cases` RPC function.

    Requires the one-time SQL setup in backend/sql/001_pgvector_setup.sql to
    have been run in Supabase, and backend/app/storage/index_cases.py to have
    been run at least once to populate the `embedding` column.

    Returns a list of row dicts (case_id, decision_title, ..., similarity).
    """
    mapped_domain = _DOMAIN_MAP.get(domain.lower(), domain) if domain else None
    logger.info("embedding_requested domain=%s", mapped_domain)
    vector = get_embedding(query)
    logger.info(
        "case_retrieval_started domain=%s k=%d",
        mapped_domain,
        k,
    )
    supabase = get_supabase_client()
    try:
        response = supabase.rpc(
            "match_decision_cases",
            {
                "query_embedding": vector,
                "match_count": k,
                "filter_department": mapped_domain,
            },
        ).execute()
    except Exception:
        logger.exception("case_retrieval_failed domain=%s", mapped_domain)
        raise
    logger.info(
        "case_retrieval_finished domain=%s results=%d",
        mapped_domain,
        len(response.data or []),
    )
    return response.data or []
