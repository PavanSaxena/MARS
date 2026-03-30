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


def finance_agent(state: State) -> Dict[str, Any]:
    """
    Finance Agent:
    - Retrieves similar financial cases from ChromaDB
    - Performs financial reasoning using an LLM
    - Outputs a structured recommendation
    """
    messages, query = extract_messages_and_query(state)
    if not messages:
        return empty_agent_result("finance_output", messages)

    _, case_text, warnings = retrieve_case_context(query=query, domain="finance", k=5)

    prompt = build_json_prompt(
        agent_title="Finance Department",
        role_points=[
            "Analyze financial aspects of the problem",
            "Use past similar cases to guide decisions",
            "Recommend a financially sound plan",
        ],
        rules=[
            "Analyze risks, costs, ROI, and feasibility",
            "Use retrieved cases as supporting evidence",
            "Confidence must be a number in [0, 1]",
        ],
        query=query,
        case_text=case_text,
    )

    response = _get_llm().invoke(prompt)
    parsed_output = parse_finance_output(getattr(response, "content", str(response)))
    if warnings:
        parsed_output["warnings"] = warnings

    return {
        "finance_output": parsed_output,
        "messages": messages + [response],
    }


def parse_finance_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from Finance LLM output."""
    return parse_structured_output(text)
