from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    user_prompt: str


class LLMClient(Protocol):
    def complete(self, prompt: PromptBundle, *, response_format: str = "text") -> str:
        raise NotImplementedError
