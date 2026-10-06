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
    - Checks if active in dynamically routed department mask
    - Retrieves similar R&D cases from Supabase (pgvector)
    - Evaluates technical feasibility, innovation potential, and timelines
    - Outputs a structured recommendation
    """
    active_depts = state.get("active_departments")
    if active_depts is not None and "rd" not in active_depts:
        return {"rd_output": None}

    messages, query = extract_messages_and_query(state)
    if not messages:
        return empty_agent_result("rd_output", messages)

    cases, case_text, warnings = retrieve_case_context(query=query, domain="rd")
    tools = get_tool_objects_for_agent("rd_agent")

    prompt = build_json_prompt(
        agent_title="R&D Department",
        role_points=[
            "Evaluate technical feasibility based strictly on retrieved historical evidence",
            "Assess innovation potential and delivery risk using past case precedents",
            "Refuse to fabricate or speculate if no historical cases exist",
        ],
        rules=[
            "Ground all R&D and technical analysis strictly in the retrieved historical cases",
            "Do NOT fabricate technical readiness levels (TRL), firmware schedules, or specs without dataset evidence",
            "If no relevant cases were retrieved, return 'No historical evidences/decisions found.'",
        ],
        query=query,
        case_text=case_text,
        tool_names=[t.name for t in tools],
    )

    content, tools_used, final_message = run_llm_with_tools(
        get_llm(state.get("model")), prompt, tools, agent_name="rd_agent"
    )
    parsed_output = parse_rd_output(content)
    parsed_output.update(build_case_evidence(cases, tools_used, query=query, department="rd"))
    if warnings:
        parsed_output["warnings"] = warnings

    return {
        "rd_output": parsed_output,
        "messages": messages + [final_message],
    }

def parse_rd_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from R&D LLM output."""
    return parse_structured_output(text)
