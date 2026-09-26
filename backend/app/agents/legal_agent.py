import logging
from typing import Any, Dict

from app.agents.common import (
    build_case_evidence,
    build_json_prompt,
    empty_agent_result,
    extract_messages_and_query,
    parse_structured_output,
    retrieve_case_context,
    run_llm_with_tools,
    get_llm,
)
from app.state import State
from app.tools.tool_registry import get_tool_objects_for_agent

logger = logging.getLogger(__name__)

def legal_agent(state: State) -> Dict[str, Any]:
    """Legal Agent: Analyze legal implications and provide recommendations.
    - Retrieves similar legal cases from Supabase (pgvector)
    - Evaluates legal risks, compliance issues, and regulatory constraints
    - Outputs a structured recommendation
    """
    logger.info("agent_started agent=legal")
    messages, query = extract_messages_and_query(state)
    if not messages:
        return empty_agent_result("legal_output", messages)

    cases, case_text, warnings = retrieve_case_context(query=query, domain="legal")
    tools = get_tool_objects_for_agent("legal_agent")

    prompt = build_json_prompt(
        agent_title="Legal Department",
        role_points=[
            "Analyze legal implications and compliance based strictly on retrieved historical evidence",
            "Assess legal risks and regulatory constraints using past case precedents",
            "Refuse to fabricate or speculate if no historical cases exist",
        ],
        rules=[
            "Ground all legal risk and compliance assessments strictly in the retrieved historical cases",
            "Do NOT fabricate regulatory guidance, Directives, or compliance steps without dataset evidence",
            "If no relevant cases were retrieved, return 'No historical evidences/decisions found.' and set confidence to 0.0",
            "Confidence must reflect the empirical grounding from the retrieved cases [0.0 to 1.0]",
        ],
        query=query,
        case_text=case_text,
        tool_names=[t.name for t in tools],
    )
    logger.info("llm_started agent=legal")
    content, tools_used, final_message = run_llm_with_tools(
        get_llm(state.get("model")), prompt, tools, agent_name="legal_agent"
    )
    logger.info("llm_finished agent=legal tools_used=%s", tools_used)
    parsed_output = parse_structured_output(content)
    parsed_output.update(build_case_evidence(cases, tools_used, reported_confidence=parsed_output.get("confidence")))
    if warnings:
        parsed_output["warnings"] = warnings
    logger.info("agent_finished agent=legal")
    return {
        "legal_output": parsed_output,
        "messages": messages + [final_message],
    }


def parse_legal_output(output_str: str) -> Dict[str, Any]:
    """Parse the structured output from the legal agent."""
    return parse_structured_output(output_str)
