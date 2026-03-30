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

def rd_agent(state: State) -> Dict[str, Any]:
    """
    R&D Agent:
    - Retrieves similar R&D cases from ChromaDB
    - Evaluates technical feasibility, innovation potential, and timelines
    - Outputs a structured recommendation
    """
    messages, query = extract_messages_and_query(state)
    if not messages:
        return empty_agent_result("rd_output", messages)

    _, case_text, warnings = retrieve_case_context(query=query, domain="rd", k=5)

    prompt = build_json_prompt(
        agent_title="R&D Department",
        role_points=[
            "Evaluate technical feasibility of the proposed initiative",
            "Assess innovation potential, research timeline, and delivery risk",
            "Use past similar R&D cases to guide decisions",
        ],
        rules=[
            "Assess technical complexity and readiness level (TRL)",
            "Estimate time-to-value and resource investment",
            "Highlight technology risks and dependencies",
            "Confidence must be a number in [0, 1]",
        ],
        query=query,
        case_text=case_text,
    )

    response = _get_llm().invoke(prompt)
    parsed_output = parse_rd_output(getattr(response, "content", str(response)))
    if warnings:
        parsed_output["warnings"] = warnings

    return {
        "rd_output": parsed_output,
        "messages": messages + [response],
    }

def parse_rd_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from R&D LLM output."""
    return parse_structured_output(text)
