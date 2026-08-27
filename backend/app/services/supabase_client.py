from supabase import Client, create_client

from app.core.config import settings

_client: Client = None


def get_supabase_client() -> Client:
    """Return a shared Supabase client, created once and reused."""
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _client
