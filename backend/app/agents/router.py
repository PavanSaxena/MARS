from typing import Any, Dict

from app.agents.common import get_llm
from app.state import State

_ROUTER_PROMPT = """You are the entry-point router for a multi-department business \
decision system (Legal, Finance, Operations, R&D). Every user message currently \
triggers a full four-department analysis, which is expensive and makes the system \
feel broken for ordinary conversation (greetings, "test", follow-up questions, \
"go into more detail", etc.). Your job is to decide, for the LATEST user message \
only, whether it actually needs that full analysis to run again.

Route to "pipeline" when the message:
- Proposes or describes a new project, investment, or business decision to evaluate.
- Adds new decision-relevant facts (budget, scope, jurisdiction, timeline, etc.) to a
  proposal that hasn't been fully analyzed yet.
- Explicitly asks for a fresh/updated department-by-department assessment.

Route to "chat" when the message:
- Is a greeting, small talk, or an obvious test message (e.g. "test", "hi", "ping").
- Asks to elaborate, clarify, summarize, rephrase, or answer a question about a
  decision that was ALREADY produced earlier in this conversation.
- Is a general follow-up question that doesn't introduce new decision-relevant
  information.

Conversation so far (most recent last):
{history}

Latest user message:
{query}

Respond with exactly one word, either: pipeline or chat
"""


def _render_history(messages) -> str:
    lines = []
    for m in messages[:-1][-10:]:
        role = getattr(m, "type", None)
        if role == "ai":
            role = "assistant"
        elif role == "human":
            role = "user"
        elif isinstance(m, dict):
            role = m.get("role", "user")
        else:
            role = "user"
        content = getattr(m, "content", None)
        if content is None and isinstance(m, dict):
            content = m.get("content", "")
        content = (content or "").strip()
        if content:
            lines.append(f"{role}: {content[:500]}")
    return "\n".join(lines) if lines else "(no prior messages)"


def classify_intent(state: State) -> Dict[str, Any]:
    """
    Entry node: decides whether this turn needs the full Legal/Finance/
    Operations/R&D pipeline, or should just be answered conversationally
    (see chat_agent). Classifies every message, including the first one in
    a thread — an opening "hi" or "test" is just as much a chat turn as a
    later one.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"route": "chat"}

    last = messages[-1]
    query = getattr(last, "content", None)
    if query is None and isinstance(last, dict):
        query = last.get("content", "")
    query = (query or "").strip()

    if not query:
        return {"route": "chat"}

    prompt = _ROUTER_PROMPT.format(history=_render_history(messages), query=query)

    try:
        response = get_llm(state.get("model")).invoke(prompt)
        text = (getattr(response, "content", "") or "").strip().lower()
    except Exception:
        # If classification itself fails, default to the safer/heavier path
        # rather than silently skipping analysis.
        return {"route": "pipeline"}

    route = "chat" if text.startswith("chat") else "pipeline"
    return {"route": route}
