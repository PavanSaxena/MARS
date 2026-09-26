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

def operations_agent(state: State) -> Dict[str, Any]:
    """
    Operations Agent:
    - Retrieves similar operations cases from Supabase (pgvector)
    - Evaluates execution feasibility, resourcing, and delivery risk
    - Outputs a structured recommendation
    """
    logger.info("agent_started agent=operations")
    messages, query = extract_messages_and_query(state)
    if not messages:
        return empty_agent_result("operations_output", messages)

    cases, case_text, warnings = retrieve_case_context(query=query, domain="operations")
    tools = get_tool_objects_for_agent("operations_agent")

    prompt = build_json_prompt(
        agent_title="Operations Department",
        role_points=[
            "Evaluate operational feasibility and supply chain impact based strictly on retrieved historical evidence",
            "Assess capacity, inventory, and logistics using past case precedents",
            "Refuse to fabricate or speculate if no historical cases exist",
        ],
        rules=[
            "Ground all operational assessments strictly in the retrieved historical cases",
            "Do NOT fabricate logistics plans, warehouse locations, buffer stocks, or supplier allocations without dataset evidence",
            "If no relevant cases were retrieved, return 'No historical evidences/decisions found.' and set confidence to 0.0",
            "Confidence must reflect the empirical grounding from the retrieved cases [0.0 to 1.0]",
        ],
        query=query,
        case_text=case_text,
        tool_names=[t.name for t in tools],
    )
    logger.info("llm_started agent=operations")
    content, tools_used, final_message = run_llm_with_tools(
        get_llm(state.get("model")), prompt, tools, agent_name="operations_agent"
    )
    logger.info("llm_finished agent=operations tools_used=%s", tools_used)
    parsed_output = parse_operations_output(content)
    parsed_output.update(build_case_evidence(cases, tools_used, reported_confidence=parsed_output.get("confidence")))
    if warnings:
        parsed_output["warnings"] = warnings
    logger.info("agent_finished agent=operations")
    return {
        "operations_output": parsed_output,
        "messages": messages + [final_message],
    }


def parse_operations_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from Operations LLM output."""
    return parse_structured_output(text)
