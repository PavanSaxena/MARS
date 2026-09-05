"""Source-first contracts for the MARS verified corpora on Supabase.

Reference: MARS_DATA_AND_SUCCESS_PLAN.md (Phases 1 & 3)
Clean schema without reviewer/annotator IDs.
"""
from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ActionType = Literal["approve", "expand", "reduce", "defer", "revise", "investigate", "reject"]
DepartmentBasis = Literal["reported", "inferred"]
OutcomeLabel = Literal["success", "failure", "unresolved"]


class QuantitativeSignal(BaseModel):
    """A source-stated measurement; annotations retain units and date."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    observed_on: date


class VerifiedDecisionCase(BaseModel):
    """A documented action available for retrieval at decision time."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    decision_date: date
    source_document_id: Optional[str] = None
    source_url: str = Field(min_length=1)
    source_page_or_section: str = Field(min_length=1)
    source_excerpt: str = Field(min_length=1)
    decision_title: str = Field(min_length=1)
    decision_description: str = Field(min_length=1)
    documented_action: str = Field(min_length=1)
    action_type: ActionType
    decision_rationale: Optional[str] = None
    quantitative_signals: List[QuantitativeSignal] = Field(default_factory=list)
    department: str = Field(min_length=1)
    department_basis: DepartmentBasis
    tags: List[str] = Field(default_factory=list)

    @field_validator("source_url")
    @classmethod
    def source_url_must_be_durable(cls, value: str) -> str:
        if not value.startswith(("https://", "http://", "file://")):
            raise ValueError("source_url must be an http(s) URL or a durable file URI")
        return value


class VerifiedOutcomeRecord(BaseModel):
    """Later evidence linked to, but never embedded in, a decision case."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    outcome_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    observation_date: date
    source_document_id: Optional[str] = None
    source_url: str = Field(min_length=1)
    source_page_or_section: str = Field(min_length=1)
    source_excerpt: str = Field(min_length=1)
    success_criterion: str = Field(min_length=1)
    success_time_window: str = Field(min_length=1)
    observed_result: str = Field(min_length=1)
    outcome_label: OutcomeLabel

    @field_validator("source_url")
    @classmethod
    def source_url_must_be_durable(cls, value: str) -> str:
        if not value.startswith(("https://", "http://", "file://")):
            raise ValueError("source_url must be an http(s) URL or a durable file URI")
        return value
