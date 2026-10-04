import logging

from supabase import Client, create_client

from app.core.config import settings

_client: Client = None
logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    """Return a shared Supabase client, created once and reused."""
    global _client
    if _client is None:
        logger.info("supabase_client_initializing")
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info("supabase_client_ready")
    else:
        logger.info("supabase_client_reused")
    return _client
