from typing import Any, Dict

from app.agents.common import get_llm
from app.state import State
from app.core.logging_config import get_logger

logger = get_logger("agents.router")

_ROUTER_PROMPT = """You are the entry-point router for a multi-department strategic business \
decision system (Legal, Finance, Operations, R&D).

Your job is two-fold for the LATEST user message:
1. Decide whether this message needs the decision "pipeline" or is general "chat" (greeting, follow-up, clarification).
2. If "pipeline", determine which department specialists MUST be consulted based on query scope:
   - "finance": budgets, capital allocation, margins, ROI, pricing, revenue, cash reserves, tax.
   - "legal": regulatory compliance, antitrust, patents, litigation, labor laws, contracts.
   - "rd": software engineering, chip design, machine learning, hardware architecture, technical feasibility.
   - "operations": supply chain, manufacturing, Foxconn/TSMC assembly, logistics, procurement, inventory.
   (If the decision is broad, complex, cross-functional, or uncertain, include all 4).

Routing Rules:
- Output "chat" for greetings, test messages, or questions about previously generated decisions.
- Output "pipeline: [dept1, dept2, ...]" for new decisions or proposals.

Examples:
- "Hi" -> chat
- "Should we switch our silicon packaging from TSMC to Intel Foundry for M4 chip wafer binning?" -> pipeline: [rd, operations, finance]
- "What are the tax implications of shifting cash reserves to our European subsidiary?" -> pipeline: [finance, legal]
- "Evaluate our 2024 enterprise strategic expansion and product rollout plan." -> pipeline: [finance, rd, legal, operations]

Conversation so far (most recent last):
{history}

Latest user message:
{query}

Respond in exactly one line: either "chat" or "pipeline: [department_list]"
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


from app.reasoning.semantic_router import route_departments_semantically


def classify_intent(state: State) -> Dict[str, Any]:
    """
    Entry node:
    1. Distinguishes 'chat' vs 'pipeline' intent.
    2. If 'pipeline', executes Semantic Vector Gating (Embedding-Space MoE Router)
       to dynamically determine the exact active department specialists needed.
    """
    logger.info("router_started")
    messages = state.get("messages", [])
    if not messages:
        logger.info("router_selected route=chat")
        return {"route": "chat", "active_departments": None}

    last = messages[-1]
    query = getattr(last, "content", None)
    if query is None and isinstance(last, dict):
        query = last.get("content", "")
    query = (query or "").strip()

    if not query:
        logger.info("router_selected route=chat")
        return {"route": "chat", "active_departments": None}

    prompt = _ROUTER_PROMPT.format(history=_render_history(messages), query=query)

    try:
        response = get_llm(state.get("model")).invoke(prompt)
        text = (getattr(response, "content", "") or "").strip().lower()
    except Exception:
        logger.exception("router_failed default_route=pipeline")
        text = "pipeline"

    if text.startswith("chat"):
        logger.info("router_selected route=chat")
        return {"route": "chat", "active_departments": None}

    # Execute true Embedding-Space Semantic Vector Gating
    try:
        active_depts, scores = route_departments_semantically(query)
        logger.info("router_semantic_gating active_departments=%s scores=%s", active_depts, scores)
    except Exception:
        logger.exception("semantic_router_failed default_all_departments")
        active_depts = ["finance", "rd", "legal", "operations"]

    logger.info("router_selected route=pipeline active_departments=%s", active_depts)
    return {"route": "pipeline", "active_departments": active_depts}
