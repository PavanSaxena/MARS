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

def rd_agent(state: State) -> Dict[str, Any]:
    """
    R&D Agent:
    - Retrieves similar R&D cases from Supabase (pgvector)
    - Evaluates technical feasibility, innovation potential, and timelines
    - Outputs a structured recommendation
    """
    messages, query = extract_messages_and_query(state)
    if not messages:
        return empty_agent_result("rd_output", messages)

    cases, case_text, warnings = retrieve_case_context(query=query, domain="rd", k=5)
    tools = get_tool_objects_for_agent("rd_agent")

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
        tool_names=[t.name for t in tools],
    )

    content, tools_used, final_message = run_llm_with_tools(
        get_llm(state.get("model")), prompt, tools, agent_name="rd_agent"
    )
    parsed_output = parse_rd_output(content)
    parsed_output.update(build_case_evidence(cases, tools_used))
    if warnings:
        parsed_output["warnings"] = warnings

    return {
        "rd_output": parsed_output,
        "messages": messages + [final_message],
    }

def parse_rd_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from R&D LLM output."""
    return parse_structured_output(text)
