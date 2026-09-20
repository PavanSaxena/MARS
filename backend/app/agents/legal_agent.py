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
    logger.info("retrieval_started agent=legal")
    cases, case_text, warnings = retrieve_case_context(query=query, domain="legal", k=5)
    logger.info(
        "retrieval_finished agent=legal cases=%d warnings=%s",
        len(cases),
        warnings,
    )
    tools = get_tool_objects_for_agent("legal_agent")

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
        tool_names=[t.name for t in tools],
    )
    logger.info("llm_started agent=legal")
    content, tools_used, final_message = run_llm_with_tools(
        get_llm(state.get("model")), prompt, tools, agent_name="legal_agent"
    )
    logger.info("llm_finished agent=legal tools_used=%s", tools_used)
    parsed_output = parse_structured_output(content)
    parsed_output.update(build_case_evidence(cases, tools_used))
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
