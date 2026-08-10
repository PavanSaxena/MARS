from __future__ import annotations

from pydantic import BaseModel, Field


class EnterpriseContext(BaseModel):
    company_name: str = ""
    quarter: str
    source_documents: list[str] = Field(default_factory=list)
    document_types: list[str] = Field(default_factory=list)
    decision_themes: list[str] = Field(default_factory=list)
    financial_metrics: list[str] = Field(default_factory=list)
    governance: list[str] = Field(default_factory=list)
    board_actions: list[str] = Field(default_factory=list)
    legal_updates: list[str] = Field(default_factory=list)
    operational_updates: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    management_outlook: list[str] = Field(default_factory=list)
    strategy: list[str] = Field(default_factory=list)
    business_guidance: list[str] = Field(default_factory=list)
    explicit_case_candidates: list[str] = Field(default_factory=list)
    evidence_by_theme: dict[str, list[str]] = Field(default_factory=dict)
    summary: str = ""

