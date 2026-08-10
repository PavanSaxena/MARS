from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.context import EnterpriseContext
from app.models.decision_case import DecisionCase
from app.models.document import ParsedDocument


class GenerationRequest(BaseModel):
    max_cases: int = Field(default=50, ge=1, le=50)
    quarter: str | None = None


class GenerationResponse(BaseModel):
    run_id: str
    quarter: str
    requested_cases: int
    accepted_cases: int
    output_file: str
    pipeline_artifacts: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    status: Literal["PASS", "FAIL"]
    feedback: list[str] = Field(default_factory=list)
    feedback_by_case: dict[int, list[str]] = Field(default_factory=dict)
    accepted_cases: list[DecisionCase] = Field(default_factory=list)


class PipelineArtifacts(BaseModel):
    parsed_documents: list[ParsedDocument] = Field(default_factory=list)
    enterprise_context: EnterpriseContext | None = None
    generated_cases: list[DecisionCase] = Field(default_factory=list)
    validated_cases: list[DecisionCase] = Field(default_factory=list)
