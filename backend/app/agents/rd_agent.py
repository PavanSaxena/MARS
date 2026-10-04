from typing import Any, Dict

from app.agents.common import execute_department_agent, parse_structured_output
from app.state import State


def rd_agent(state: State) -> Dict[str, Any]:
    """R&D Agent: Evaluates technical feasibility, innovation potential, and timelines."""
    return execute_department_agent(
        state=state,
        department="rd",
        agent_title="R&D Department",
        output_key="rd_output",
        role_points=[
            "Evaluate technical feasibility based strictly on retrieved historical evidence",
            "Assess innovation potential and delivery risk using past case precedents",
            "Refuse to fabricate or speculate if no historical cases exist",
        ],
        rules=[
            "Ground all R&D and technical analysis strictly in the retrieved historical cases",
            "Do NOT fabricate technical readiness levels (TRL), firmware schedules, or specs without dataset evidence",
            "If no relevant cases were retrieved, return 'No historical evidences/decisions found.' and set confidence to 0.0",
            "Confidence must reflect the empirical grounding from the retrieved cases [0.0 to 1.0]",
        ],
    )


def parse_rd_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from R&D LLM output."""
    return parse_structured_output(text)
