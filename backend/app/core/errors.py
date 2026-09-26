from typing import Optional


def is_rate_limit_error(exc: Exception) -> bool:
    """Check whether an exception represents a rate limit / quota exhaustion (HTTP 429)."""
    exc_type = type(exc).__name__.lower()
    if "ratelimit" in exc_type:
        return True

    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True

    response = getattr(exc, "response", None)
    if response is not None and getattr(response, "status_code", None) == 429:
        return True

    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error", {})
        if isinstance(err, dict) and err.get("code") in ("rate_limit_exceeded", "insufficient_quota"):
            return True

    msg = str(exc).lower()
    rate_phrases = (
        "rate limit",
        "rate_limit",
        "429",
        "too many requests",
        "tpm",
        "rpm",
        "tokens per minute",
        "requests per minute",
        "quota exceeded",
        "insufficient_quota",
        "resource_exhausted",
    )
    return any(p in msg for p in rate_phrases)


def format_rate_limit_error(exc: Exception, model_name: Optional[str] = None) -> str:
    """Format a user-friendly Markdown message explaining the rate limit to display in the UI."""
    msg = str(exc)
    body = getattr(exc, "body", None)
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        msg = body["error"].get("message") or msg

    model_info = f" for model `{model_name}`" if model_name else ""

    return (
        "### ⚠️ Provider Rate Limit Reached (HTTP 429)\n\n"
        f"The AI model provider rate limit has been reached{model_info}.\n\n"
        f"> **Provider Message:** {msg}\n\n"
        "**What you can do:**\n"
        "- **Wait a few moments (10–30 seconds)** for your rate limit window to reset, then send your query again.\n"
        "- **Switch models** using the model selector dropdown in the top-right corner (e.g., choose `groq:openai/gpt-oss-20b` or `groq:qwen/qwen3.6-27b`)."
    )
