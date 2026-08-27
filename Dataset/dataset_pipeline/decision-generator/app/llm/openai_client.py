from __future__ import annotations

import logging
import time
import re

from app.config import MODEL, LLM_API_KEY, TEMPERATURE, LLM_BASE_URL
from app.llm.client import PromptBundle
from openai import OpenAI
from langsmith.wrappers import wrap_openai


logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self) -> None:
        self._client = None
        self.max_retries = 5
        self.retry_base_delay = 1.0
        self.retry_buffer = 2.0
        self.request_throttle_delay = 0.5
        
        if LLM_API_KEY:
            try:
                self._client = wrap_openai(OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL))
            except Exception as exc:
                logger.warning("openai_client_unavailable %s", exc)

    def is_configured(self) -> bool:
        return self._client is not None

    def _extract_retry_delay(self, error: Exception) -> float | None:
        """Extract suggested retry delay from rate limit error."""
        try:
            error_str = str(error)
            
            # Look for "retry after X seconds" pattern
            if "retry after" in error_str.lower():
                match = re.search(r'retry after (\d+\.?\d*)', error_str.lower())
                if match:
                    return float(match.group(1))
            
            # Check error response headers if available
            if hasattr(error, 'response') and error.response:
                headers = getattr(error.response, 'headers', {})
                if 'retry-after' in headers:
                    return float(headers['retry-after'])
            
            return None
            
        except Exception as e:
            logger.debug(f"Could not extract retry delay from error: {e}")
            return None

    def complete(self, prompt: PromptBundle, *, response_format: str = "text") -> str:
        """Complete with automatic rate limit retry handling."""
        if self._client is None:
            raise RuntimeError("OpenAI client is not configured")

        request_kwargs = {
            "model": MODEL,
            "temperature": TEMPERATURE,
            "messages": [
                {"role": "system", "content": prompt.system_prompt},
                {"role": "user", "content": prompt.user_prompt},
            ],
        }
        if response_format == "json":
            request_kwargs["response_format"] = {"type": "json_object"}
        
        # Log sanitized prompt for debugging
        logger.debug(f"LLM Request - Format: {response_format}, System prompt length: {len(prompt.system_prompt)}, User prompt length: {len(prompt.user_prompt)}")

        # Retry loop with rate limit handling
        for attempt in range(self.max_retries + 1):
            try:
                # Add throttle delay between requests (except on retries)
                if attempt == 0:
                    time.sleep(self.request_throttle_delay)
                
                completion = self._client.chat.completions.create(**request_kwargs)
                response_content = completion.choices[0].message.content or ""
                
                # Log response for debugging JSON issues
                if response_format == "json":
                    logger.debug(f"LLM Response length: {len(response_content)}, First 200 chars: {response_content[:200]}")
                
                return response_content
                
            except Exception as e:
                # Check if it's a rate limit error
                error_str = str(e).lower()
                is_rate_limit = "rate" in error_str and "limit" in error_str
                
                if not is_rate_limit or attempt >= self.max_retries:
                    # Not a rate limit error, or max retries exceeded
                    if is_rate_limit:
                        logger.error(
                            f"Rate limit exceeded after {self.max_retries} retries. Error: {e}"
                        )
                    raise
                
                # Extract retry delay from error
                retry_delay = self._extract_retry_delay(e)
                if retry_delay is None:
                    # Use exponential backoff if no delay suggested
                    retry_delay = self.retry_base_delay * (2 ** attempt)
                
                # Add buffer to suggested delay
                total_delay = retry_delay + self.retry_buffer
                
                logger.warning(
                    f"Rate limit hit (attempt {attempt + 1}/{self.max_retries}). "
                    f"Waiting {total_delay:.2f}s before retry. Error: {e}"
                )
                
                time.sleep(total_delay)
        
        # Should never reach here, but just in case
        raise RuntimeError("Unexpected error in retry loop")