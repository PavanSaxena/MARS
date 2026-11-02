from typing import Any, Dict

from app.agents.common import execute_department_agent, parse_structured_output
from app.state import State


def finance_agent(state: State) -> Dict[str, Any]:
    """Finance Agent: Retrieves historical cases and evaluates financial feasibility."""
    return execute_department_agent(
        state=state,
        department="finance",
        agent_title="Finance Department",
        output_key="finance_output",
        role_points=[
            "Analyze financial aspects of the problem based strictly on retrieved historical evidence",
            "Use past similar cases from the dataset to guide financial decisions",
            "Refuse to fabricate or speculate if no historical cases exist",
        ],
        rules=[
            "Ground all financial analysis strictly in the retrieved historical cases",
            "Do NOT fabricate financial figures, budgets, VAT models, or ROI estimates without dataset evidence",
            "If no relevant cases were retrieved, return 'No historical evidences/decisions found.' and set confidence to 0.0",
            "Confidence must reflect the empirical grounding from the retrieved cases [0.0 to 1.0]",
        ],
    )


def parse_finance_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from Finance LLM output."""
    return parse_structured_output(text)
