from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DecisionCase(BaseModel):
    case_id: int = Field(ge=1)
    source_file_name: str
    source_excerpt: str
    quarter: str
    department: Literal["Finance", "Legal", "Operations", "R&D"]
    decision_title: str
    decision_archetype: str
    trigger: str
    decision_description: str
    options_considered: str
    chosen_option: str
    reasoning_summary: str
    quantitative_signals: str
    risk_level: Literal["Low", "Medium", "High"]
    cross_dept_impact: str
    expected_profit_impact: str
    profit_confidence: float = Field(ge=0.0, le=1.0)
    profit_impact_pathway: str
    outcome_status: str
    outcome_summary: str
    decision_tags: str
    finance_agent_conf: float = Field(ge=0.0, le=1.0)
    r_and_d_agent_conf: float = Field(ge=0.0, le=1.0)
    ops_agent_conf: float = Field(ge=0.0, le=1.0)
    legal_agent_conf: float = Field(ge=0.0, le=1.0)
    conflicting_perspectives: str
    master_agent_decision: str
    master_agent_confidence: float = Field(ge=0.0, le=1.0)


DecisionRow = DecisionCase