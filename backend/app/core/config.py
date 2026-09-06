"""
Centralized application configuration.

Loads once from the project's .env file (backend/.env) and exposes a single
`settings` object. Import this instead of scattering os.getenv() /
load_dotenv() calls across modules.
"""
from pathlib import Path
from typing import List, Optional
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider keys — set whichever ones correspond to the models you
    # enable in AVAILABLE_MODELS below. Only the provider(s) actually used
    # need a key.
    GROQ_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Models selectable at request time (see QueryRequest.model in
    # app/api/routes.py). Each entry is "<provider>:<model>", matching
    # langchain's init_chat_model() convention — this is exactly what's
    # passed to init_chat_model, so adding a new option is a one-line change
    # here, nothing else in the codebase needs to know about it.
    #
    # NOTE: as of Aug 2026 Groq is retiring llama-3.3-70b-versatile /
    # llama-3.1-8b-instant; use the openai/gpt-oss-* models below instead.
    DEFAULT_MODEL: str = "groq:openai/gpt-oss-120b"
    AVAILABLE_MODELS: List[str] = [
        "groq:openai/gpt-oss-120b",
        "groq:openai/gpt-oss-20b",
        "groq:qwen/qwen3.6-27b",
    ]

    # Supabase (source data + vector store via pgvector)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_DECISIONS_TABLE: str = "decisions"
    SUPABASE_OUTCOMES_TABLE: str = "outcomes"

    # Optional search tool
    TAVILY_API_KEY: Optional[str] = None

    # Retrieval & Contextual Reranking
    RETRIEVAL_CANDIDATE_COUNT: int = 25  # Top 20-30 candidates fetched from vector search
    RETRIEVAL_MIN_CASES: int = 3         # Minimum number of target cases to return (if relevant)
    RETRIEVAL_MAX_CASES: int = 10        # Maximum number of final diverse cases to return
    RETRIEVAL_SIMILARITY_FLOOR: float = 0.25  # Soft floor to eliminate zero/unrelated noise
    RETRIEVAL_MMR_LAMBDA: float = 0.65   # Balance between relevance (1.0) and diversity (0.0)

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    def api_key_for_model(self, model_id: str) -> Optional[str]:
        """Return the configured API key for a model's provider, or None."""
        provider = model_id.split(":", 1)[0] if ":" in model_id else ""
        return {
            "groq": self.GROQ_API_KEY,
            "openai": self.OPENAI_API_KEY,
            "anthropic": self.ANTHROPIC_API_KEY,
        }.get(provider)


settings = Settings()

# pydantic-settings' env_file loading only populates this Settings object —
# it does NOT set real process environment variables. But the LLM provider
# SDKs invoked via langchain's init_chat_model() (groq, openai, anthropic)
# read their API key straight from os.environ, not from this settings
# object. Without this sync, get_llm() (app/agents/common.py) fails with
# e.g. "GROQ_API_KEY environment variable" even though settings.GROQ_API_KEY
# — and therefore GET /api/models' availability check — is correctly set.
for _env_key in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "TAVILY_API_KEY"):
    _value = getattr(settings, _env_key, None)
    if _value and not os.environ.get(_env_key):
        os.environ[_env_key] = _value
