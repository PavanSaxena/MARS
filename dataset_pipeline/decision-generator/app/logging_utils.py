from __future__ import annotations

import logging

from app.config import LOGS_DIR, ensure_directories


def configure_logging() -> None:
    ensure_directories()
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(LOGS_DIR / "pipeline.log")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    Uses rough approximation: 1 token ≈ 4 characters.
    """
    return len(text) // 4


def log_llm_request(
    estimated_input_tokens: int,
    requested_completion_tokens: int,
    prompt_char_count: int,
    batch_size: int = None,
    evidence_count: int = None,
    previous_case_count: int = None
):
    """Log LLM request statistics before making the call."""
    logger = logging.getLogger(__name__)
    log_data = {
        "event": "llm_request",
        "estimated_input_tokens": estimated_input_tokens,
        "requested_completion_tokens": requested_completion_tokens,
        "prompt_char_count": prompt_char_count,
    }
    
    if batch_size is not None:
        log_data["batch_size"] = batch_size
    if evidence_count is not None:
        log_data["evidence_count"] = evidence_count
    if previous_case_count is not None:
        log_data["previous_case_count"] = previous_case_count
    
    logger.info(f"LLM Request: {log_data}")


def log_llm_response(
    response_char_count: int,
    estimated_output_tokens: int,
    generated_cases_count: int = None,
    duration_seconds: float = None
):
    """Log LLM response statistics after receiving the response."""
    logger = logging.getLogger(__name__)
    log_data = {
        "event": "llm_response",
        "response_char_count": response_char_count,
        "estimated_output_tokens": estimated_output_tokens,
    }
    
    if generated_cases_count is not None:
        log_data["generated_cases_count"] = generated_cases_count
    if duration_seconds is not None:
        log_data["duration_seconds"] = round(duration_seconds, 2)
    
    logger.info(f"LLM Response: {log_data}")