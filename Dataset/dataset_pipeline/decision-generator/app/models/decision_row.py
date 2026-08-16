from pydantic import BaseModel
from typing import Literal

class DecisionRow(BaseModel):

    case_id: int

    quarter: str

    department: Literal[
        "Finance",
        "Legal",
        "Operations",
        "R&D"
    ]

    decision_title: str

    decision_archetype: str

    trigger: str

    decision_description: str

    options_considered: str

    chosen_option: str

    reasoning_summary: str

    quantitative_signals: str

    risk_level: Literal[
        "Low",
        "Medium",
        "High"
    ]

    cross_dept_impact: str

    expected_profit_impact: str

    profit_confidence: float

    profit_impact_pathway: str

    outcome_status: str

    outcome_summary: str

    decision_tags: str

    finance_agent_conf: float

    r_and_d_agent_conf: float

    ops_agent_conf: float

    legal_agent_conf: float

    conflicting_perspectives: str

    master_agent_decision: str

    master_agent_confidence: float