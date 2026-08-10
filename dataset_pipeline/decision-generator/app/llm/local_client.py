from __future__ import annotations

import json

from app.llm.client import PromptBundle


class LocalLLMClient:
    def complete(self, prompt: PromptBundle, *, response_format: str = "text") -> str:
        if response_format == "json":
            payload = {
                "system_prompt": prompt.system_prompt,
                "user_prompt": prompt.user_prompt,
                "status": "local_fallback",
            }
            return json.dumps(payload)
        return f"{prompt.system_prompt}\n\n{prompt.user_prompt}"
