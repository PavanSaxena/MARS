from __future__ import annotations

import logging
from difflib import SequenceMatcher
from statistics import mean

from langsmith import traceable
from app.llm.local_client import LocalLLMClient
from app.llm.client import LLMClient
from app.models.decision_case import DecisionCase
from app.models.pipeline import ValidationResult
from app.prompts.builder import PromptBuilder
from app.validation.business_rules import validate_business_rules


logger = logging.getLogger(__name__)


class DecisionValidationAgent:
    def __init__(self, llm_client: LLMClient, prompt_builder: PromptBuilder) -> None:
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        self._validation_prompt_metadata = prompt_builder.get_prompt_metadata("validation")

    def _is_duplicate(self, candidate: DecisionCase, accepted_cases: list[DecisionCase], threshold: float = 0.9) -> bool:
        candidate_title = candidate.decision_title.strip().lower()
        for existing_case in accepted_cases:
            existing_title = existing_case.decision_title.strip().lower()
            if SequenceMatcher(None, candidate_title, existing_title).ratio() >= threshold:
                return True
        return False

    def _looks_placeholder(self, value: str) -> bool:
        lower_value = value.lower()
        return any(
            phrase in lower_value
            for phrase in (
                "potential positive impact if executed",
                "potential downside avoided by delaying or revising",
                "extracted from filing language and financial context",
                "derived from uploaded source material",
                "no explicit conflict identified in the source excerpt",
                "source language suggests tradeoffs across functions",
                "synthesized from enterprise context patterns",
                "generated as a synthetic follow-on case",
            )
        )

    def _parse_options(self, options_text: str) -> list[str]:
        labels = []
        for option in options_text.split(";"):
            cleaned = option.strip()
            if not cleaned:
                continue
            labels.append(cleaned.split(":", 1)[0].strip())
        return labels

    def _confidence_gaps(self, case: DecisionCase) -> list[str]:
        confidences = [case.finance_agent_conf, case.r_and_d_agent_conf, case.ops_agent_conf, case.legal_agent_conf]
        gap = max(confidences) - min(confidences)
        if gap > 0.4:
            return [f"Case {case.case_id} has an unrealistic confidence spread"]
        if abs(case.master_agent_confidence - mean(confidences)) > 0.25:
            return [f"Case {case.case_id} master confidence is not aligned with sub-agent confidence"]
        return []

    def _deterministic_check(
        self,
        cases: list[DecisionCase],
        previous_cases: list[DecisionCase],
    ) -> tuple[list[str], dict[int, list[str]]]:
        feedback: list[str] = []
        per_case: dict[int, list[str]] = {}
        seen_titles: set[str] = set()

        def record(case_id: int, message: str) -> None:
            feedback.append(message)
            per_case.setdefault(case_id, []).append(message)

        for case in cases:
            if not validate_business_rules(case.model_dump()):
                record(case.case_id, f"Case {case.case_id} failed business rules")
            if (
                self._looks_placeholder(case.expected_profit_impact)
                or self._looks_placeholder(case.outcome_summary)
                or self._looks_placeholder(case.conflicting_perspectives)
            ):
                record(case.case_id, f"Case {case.case_id} contains placeholder language")
            if len(case.decision_title.split()) < 5 or len(case.decision_title) > 120:
                record(case.case_id, f"Case {case.case_id} title is not enterprise-quality")
            if case.decision_description.strip() == case.source_excerpt.strip():
                record(case.case_id, f"Case {case.case_id} description duplicates the source excerpt")
            if len(case.decision_tags.split(",")) < 3:
                record(case.case_id, f"Case {case.case_id} needs richer tags")
            for gap_msg in self._confidence_gaps(case):
                record(case.case_id, gap_msg)
            title_key = case.decision_title.strip().lower()
            if title_key in seen_titles:
                record(case.case_id, f"Duplicate title inside batch: {case.decision_title}")
            seen_titles.add(title_key)
            if self._is_duplicate(case, previous_cases):
                record(case.case_id, f"Duplicate against case memory: {case.decision_title}")
            if case.chosen_option not in self._parse_options(case.options_considered):
                record(case.case_id, f"Chosen option not in options_considered for case {case.case_id}")
            if not case.source_excerpt.strip() or len(case.source_excerpt.strip()) < 40:
                record(case.case_id, f"Missing source excerpt for case {case.case_id}")
            if case.source_excerpt.strip() and len(case.source_excerpt.split()) < 8:
                record(case.case_id, f"Case {case.case_id} source excerpt is too thin for synthetic realism")

        if len({case.case_id for case in cases}) != len(cases):
            feedback.append("Duplicate case_id values detected")

        return feedback, per_case

    @traceable(name="Validation Agent")
    def validate(self, cases: list[DecisionCase], previous_cases: list[DecisionCase]) -> ValidationResult:
        feedback, feedback_by_case = self._deterministic_check(cases, previous_cases)

        if not feedback and not isinstance(self.llm_client, LocalLLMClient):
            prompt = self.prompt_builder.build_validation_prompt(cases=cases, feedback=[])
            response_text = self.llm_client.complete(prompt, response_format="text").strip()
            if response_text:
                response_upper = response_text.upper()
                if response_upper.startswith("FAIL"):
                    feedback.append(response_text)
                    # Semantic-level FAIL: attach to all cases so they get repaired.
                    for case in cases:
                        feedback_by_case.setdefault(case.case_id, []).append(response_text)
                elif not response_upper.startswith("PASS"):
                    feedback.append(f"Unexpected validator response: {response_text}")

        if feedback:
            logger.info("validation_failed feedback=%s", feedback)
            return ValidationResult(
                status="FAIL",
                feedback=feedback,
                feedback_by_case=feedback_by_case,
                accepted_cases=[],
            )

        return ValidationResult(status="PASS", feedback=[], feedback_by_case={}, accepted_cases=cases)
