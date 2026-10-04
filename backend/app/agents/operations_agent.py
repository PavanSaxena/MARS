from typing import Any, Dict

from app.agents.common import execute_department_agent, parse_structured_output
from app.state import State


def operations_agent(state: State) -> Dict[str, Any]:
    """Operations Agent: Evaluates execution feasibility, resourcing, and supply chain."""
    return execute_department_agent(
        state=state,
        department="operations",
        agent_title="Operations Department",
        output_key="operations_output",
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
    )


def parse_operations_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from Operations LLM output."""
    return parse_structured_output(text)
