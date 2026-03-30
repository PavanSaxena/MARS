from typing import Any, Dict

from langchain.chat_models import init_chat_model

from app.agents.common import (
    build_json_prompt,
    empty_agent_result,
    extract_messages_and_query,
    parse_structured_output,
    retrieve_case_context,
)
from app.state import State

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = init_chat_model("groq:llama-3.3-70b-versatile")
    return _llm


def operations_agent(state: State) -> Dict[str, Any]:
    """
    Operations Agent:
    - Retrieves similar operations cases from ChromaDB
    - Evaluates execution feasibility, resourcing, and delivery risk
    - Outputs a structured recommendation
    """
    messages, query = extract_messages_and_query(state)
    if not messages:
        return empty_agent_result("operations_output", messages)

    _, case_text, warnings = retrieve_case_context(query=query, domain="operations", k=5)

    prompt = build_json_prompt(
        agent_title="Operations Department",
        role_points=[
            "Evaluate implementation feasibility and operational readiness",
            "Assess process constraints, staffing, and execution timelines",
            "Use past similar operations cases to guide decisions",
        ],
        rules=[
            "Evaluate capacity, process fit, and rollout practicality",
            "Identify operational risks and mitigation options",
            "Recommend an implementation approach",
            "Confidence must be a number in [0, 1]",
        ],
        query=query,
        case_text=case_text,
    )

    response = _get_llm().invoke(prompt)
    parsed_output = parse_operations_output(getattr(response, "content", str(response)))
    if warnings:
        parsed_output["warnings"] = warnings

    return {
        "operations_output": parsed_output,
        "messages": messages + [response],
    }


def parse_operations_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from Operations LLM output."""
    return parse_structured_output(text)
