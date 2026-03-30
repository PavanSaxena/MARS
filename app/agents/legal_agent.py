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


def legal_agent(state: State) -> Dict[str, Any]:
    """Legal Agent: Analyze legal implications and provide recommendations.
    - Retrieves similar legal cases from ChromaDB
    - Evaluates legal risks, compliance issues, and regulatory constraints
    - Outputs a structured recommendation
    """
    messages, query = extract_messages_and_query(state)
    if not messages:
        return empty_agent_result("legal_output", messages)

    _, case_text, warnings = retrieve_case_context(query=query, domain="legal", k=5)

    prompt = build_json_prompt(
        agent_title="Legal Department",
        role_points=[
            "Analyze legal implications of the proposed initiative",
            "Assess compliance with relevant laws and regulations",
            "Use past similar legal cases to guide decisions",
        ],
        rules=[
            "Identify potential legal risks and liabilities",
            "Evaluate regulatory constraints and compliance requirements",
            "Recommend risk mitigation strategies",
            "Confidence must be a number in [0, 1]",
        ],
        query=query,
        case_text=case_text,
    )

    response = _get_llm().invoke(prompt)
    parsed_output = parse_structured_output(getattr(response, "content", str(response)))
    if warnings:
        parsed_output["warnings"] = warnings

    return {
        "legal_output": parsed_output,
        "messages": messages + [response],
    }


def parse_legal_output(output_str: str) -> Dict[str, Any]:
    """Parse the structured output from the legal agent."""
    return parse_structured_output(output_str)
