"""Business logic and external service clients."""

# NOTE: get_similar_cases is intentionally NOT re-exported here to avoid a
# circular import:  storage.__init__ → retriever → supabase_client →
# services.__init__ → case_retrieval_service → retriever  (cycle).
# Import it directly:  from app.services.case_retrieval_service import get_similar_cases
from app.services.supabase_client import get_supabase_client

__all__ = ["get_supabase_client"]
