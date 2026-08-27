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


def operations_agent(state: State) -> Dict[str, Any]:
    """
    Operations Agent:
    - Retrieves similar operations cases from Supabase (pgvector)
    - Evaluates execution feasibility, resourcing, and delivery risk
    - Outputs a structured recommendation
    """
    messages, query = extract_messages_and_query(state)
    if not messages:
        return empty_agent_result("operations_output", messages)

    cases, case_text, warnings = retrieve_case_context(query=query, domain="operations", k=5)
    tools = get_tool_objects_for_agent("operations_agent")

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
        tool_names=[t.name for t in tools],
    )

    content, tools_used, final_message = run_llm_with_tools(
        get_llm(state.get("model")), prompt, tools, agent_name="operations_agent"
    )
    parsed_output = parse_operations_output(content)
    parsed_output.update(build_case_evidence(cases, tools_used))
    if warnings:
        parsed_output["warnings"] = warnings

    return {
        "operations_output": parsed_output,
        "messages": messages + [final_message],
    }


def parse_operations_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from Operations LLM output."""
    return parse_structured_output(text)
