import logging
from typing import Any, Dict

from app.agents.common import get_llm
from app.state import State

logger = logging.getLogger(__name__)

_CHAT_SYSTEM = """You are the conversational voice of a multi-department business \
decision assistant (Legal, Finance, Operations, R&D). A full department analysis \
already ran earlier in this conversation when it was warranted — do not re-run it, \
repeat its process, or ask again for information that was already given, unless the \
user is now proposing something genuinely new. Just answer the user's message \
directly and conversationally, using the prior conversation (including any earlier \
"Final Decision" you produced) as context. If they ask you to elaborate, elaborate \
on what was already said. If they're just chatting, testing, or asking a quick \
question, respond naturally and briefly like a normal assistant would.
Only answer to business-related questions, and do not answer personal questions or irrelevant topics.
"""


def _to_chat_message(m) -> Dict[str, str] | None:
    role = getattr(m, "type", None)
    if role == "ai":
        role = "assistant"
    elif role == "human":
        role = "user"
    elif isinstance(m, dict):
        role = "assistant" if m.get("role") == "assistant" else "user"
    else:
        role = "user"

    content = getattr(m, "content", None)
    if content is None and isinstance(m, dict):
        content = m.get("content", "")
    content = content or ""
    if not content:
        return None
    return {"role": role, "content": content}


def chat_agent(state: State) -> Dict[str, Any]:
    """
    Handles turns the router classified as "chat": ordinary conversation,
    follow-ups, and requests to elaborate on a decision already produced.
    Answers directly with the LLM using full conversation history instead of
    re-running the four department agents + aggregator.
    """
    messages = state.get("messages", [])
    logger.info("chat_started message_count=%d", len(messages))
    llm = get_llm(state.get("model"))

    convo = [{"role": "system", "content": _CHAT_SYSTEM}]
    for m in messages:
        chat_msg = _to_chat_message(m)
        if chat_msg:
            convo.append(chat_msg)

    try:
        response = llm.invoke(convo)
    except Exception:
        logger.exception("chat_failed")
        raise

    logger.info("chat_finished")

    return {
        "final_output": getattr(response, "content", str(response)),
        "messages": messages + [response],
    }
