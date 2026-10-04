from typing import Any, Dict

from app.agents.common import execute_department_agent, parse_structured_output
from app.state import State


def legal_agent(state: State) -> Dict[str, Any]:
    """Legal Agent: Evaluates legal risks, regulatory constraints, and compliance."""
    return execute_department_agent(
        state=state,
        department="legal",
        agent_title="Legal Department",
        output_key="legal_output",
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
    )


def parse_legal_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from Legal LLM output."""
    return parse_structured_output(text)
