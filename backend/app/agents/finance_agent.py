from typing import Any, Dict
import logging

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

def finance_agent(state: State) -> Dict[str, Any]:
    """
    Finance Agent:
    - Retrieves similar financial cases from Supabase (pgvector)
    - Performs financial reasoning using an LLM
    - Outputs a structured recommendation
    """
    logger.info("agent_started agent=finance")
    messages, query = extract_messages_and_query(state)
    if not messages:
        return empty_agent_result("finance_output", messages)
    logger.info("retrieval_started agent=finance")
    cases, case_text, warnings = retrieve_case_context(query=query, domain="finance", k=5)
    logger.info(
        "retrieval_finished agent=finance cases=%d warnings=%s",
        len(cases),
        warnings,
    )
    tools = get_tool_objects_for_agent("finance_agent")

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
        tool_names=[t.name for t in tools],
    )
    logger.info("llm_started agent=finance")
    content, tools_used, final_message = run_llm_with_tools(
        get_llm(state.get("model")), prompt, tools, agent_name="finance_agent"
    )
    logger.info("llm_finished agent=finance tools_used=%s", tools_used)
    parsed_output = parse_finance_output(content)
    parsed_output.update(build_case_evidence(cases, tools_used))
    if warnings:
        parsed_output["warnings"] = warnings
    logger.info("agent_finished agent=finance")
    return {
        "finance_output": parsed_output,
        "messages": messages + [final_message],
    }


def parse_finance_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from Finance LLM output."""
    return parse_structured_output(text)
