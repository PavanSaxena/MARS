from __future__ import annotations

import json
import logging
from itertools import cycle
from typing import Any

from langsmith import traceable
from app.generation.agent_reasoning import (
    _role_confidence,
    build_case_row,
    clean_text,
    infer_archetype,
    infer_department,
    infer_risk_level,
    split_sentences,
)
from app.llm.client import LLMClient
from app.models.context import EnterpriseContext
from app.models.decision_case import DecisionCase
from app.prompts.builder import PromptBuilder


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intermediate schema helpers
# ---------------------------------------------------------------------------

_ALLOWED_DEPARTMENTS = {"Finance", "Legal", "Operations", "R&D"}
_ALLOWED_RISK = {"Low", "Medium", "High"}
_ALLOWED_CHOSEN = {"Proceed", "Pause", "Revise"}


# All fields that the LLM is allowed to populate/patch in the intermediate.
INTERMEDIATE_FIELDS: tuple[str, ...] = (
    "source_excerpt",
    "department",
    "decision_title",
    "decision_archetype",
    "trigger",
    "decision_description",
    "options",
    "chosen_option",
    "reasoning_summary",
    "quantitative_signals",
    "risk_level",
    "cross_dept_impact",
    "expected_profit_impact",
    "profit_impact_pathway",
    "outcome_status",
    "outcome_summary",
    "decision_tags",
    "conflicting_perspectives",
    "master_agent_decision",
)


def _coerce_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return clean_text(value)
    return clean_text(str(value))


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [clean_text(str(item)) for item in value if str(item).strip()]
    # Sometimes LLMs return semi-colon or comma-separated strings.
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(";", ",").split(",") if p.strip()]
        return parts
    return [clean_text(str(value))]


def _coerce_options(value: Any) -> list[dict[str, str]]:
    """Normalize the options list. Each option must have {label, summary}."""
    result: list[dict[str, str]] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                label = clean_text(str(item.get("label", ""))).title()
                summary = clean_text(str(item.get("summary", "")))
                if label:
                    result.append({"label": label, "summary": summary or label})
            elif isinstance(item, str):
                # "Proceed:Approve the plan"
                if ":" in item:
                    label, _, summary = item.partition(":")
                else:
                    label, summary = item, item
                label = clean_text(label).title()
                if label:
                    result.append({"label": label, "summary": clean_text(summary) or label})
    return result


def _ensure_three_options(
    options: list[dict[str, str]],
    department: str,
    chosen_option: str,
) -> list[dict[str, str]]:
    """Guarantee at least three canonical options and that chosen_option is in the list."""
    canonical_summaries = {
        "Finance": {
            "Proceed": "Approve the current financial plan",
            "Pause": "Hold pending more visibility",
            "Revise": "Rebalance the financial plan",
        },
        "Legal": {
            "Proceed": "Advance with legal controls",
            "Pause": "Wait for legal clarity",
            "Revise": "Adjust the remediation plan",
        },
        "Operations": {
            "Proceed": "Execute operations as planned",
            "Pause": "Defer until capacity stabilizes",
            "Revise": "Re-sequence supply and cost actions",
        },
        "R&D": {
            "Proceed": "Fund the current roadmap",
            "Pause": "Delay lower-priority R&D work",
            "Revise": "Reallocate to strategic initiatives",
        },
    }
    fallback = canonical_summaries.get(department, canonical_summaries["Operations"])

    seen_labels = {opt["label"] for opt in options}
    for label in ("Proceed", "Pause", "Revise"):
        if label not in seen_labels:
            options.append({"label": label, "summary": fallback[label]})
            seen_labels.add(label)

    # Ensure chosen_option is in options; if not, append/replace.
    labels = {opt["label"] for opt in options}
    if chosen_option not in labels:
        # Add it with a reasonable summary.
        options.append(
            {"label": chosen_option, "summary": fallback.get(chosen_option, chosen_option)}
        )
    return options


def _serialize_options(options: list[dict[str, str]]) -> str:
    return ";".join(f"{opt['label']}:{opt['summary']}" for opt in options)


def _normalize_department(value: Any, fallback_source: str) -> str:
    dept = _coerce_string(value)
    if dept in _ALLOWED_DEPARTMENTS:
        return dept
    # Try to map common variants.
    mapping = {
        "finance": "Finance",
        "legal": "Legal",
        "ops": "Operations",
        "operations": "Operations",
        "r&d": "R&D",
        "rnd": "R&D",
        "research": "R&D",
        "r and d": "R&D",
    }
    key = dept.lower().strip()
    if key in mapping:
        return mapping[key]
    return infer_department(fallback_source or dept)


def _normalize_risk(value: Any, fallback_source: str) -> str:
    risk = _coerce_string(value).title()
    if risk in _ALLOWED_RISK:
        return risk
    return infer_risk_level(fallback_source)


def _normalize_chosen(value: Any, options: list[dict[str, str]]) -> str:
    chosen = _coerce_string(value).title()
    labels = {opt["label"] for opt in options}
    if chosen in labels:
        return chosen
    if chosen in _ALLOWED_CHOSEN:
        return chosen
    # Prefer the first canonical label available.
    for candidate in ("Proceed", "Revise", "Pause"):
        if candidate in labels:
            return candidate
    return "Proceed"


def _default_cross_dept(department: str) -> list[str]:
    if department == "Legal":
        return ["Legal", "Finance", "Operations"]
    return ["Finance", "Operations", "Legal", "R&D"]


def _default_tags(department: str, risk_level: str, grounded: bool) -> list[str]:
    return [
        department.lower(),
        risk_level.lower(),
        "source-grounded" if grounded else "context-derived",
        "enterprise-decision",
    ]


def _normalize_intermediate(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw LLM case dict into a well-formed intermediate dict.

    Fills any missing/malformed fields with safe defaults so mapping never fails.
    """
    source_excerpt = _coerce_string(raw.get("source_excerpt"))
    department = _normalize_department(raw.get("department"), source_excerpt)
    risk_level = _normalize_risk(raw.get("risk_level"), source_excerpt)

    options = _coerce_options(raw.get("options"))
    chosen_option = _normalize_chosen(raw.get("chosen_option"), options)
    options = _ensure_three_options(options, department, chosen_option)

    decision_title = _coerce_string(raw.get("decision_title"))
    if not decision_title:
        decision_title = f"{department} decision on evolving enterprise signal"
    decision_archetype = _coerce_string(raw.get("decision_archetype"))
    if not decision_archetype:
        decision_archetype = infer_archetype(source_excerpt or decision_title)

    trigger = _coerce_string(raw.get("trigger")) or decision_title
    decision_description = _coerce_string(raw.get("decision_description"))
    if not decision_description or decision_description == source_excerpt:
        decision_description = (
            f"{department} evaluates whether to {chosen_option.lower()} in response to the reported enterprise signal."
        )

    reasoning_summary = _coerce_string(raw.get("reasoning_summary"))
    if not reasoning_summary:
        reasoning_summary = (
            f"{department} should act on the reported signal because it points to a material decision point."
        )

    quantitative_signals = _coerce_string(raw.get("quantitative_signals"))
    if not quantitative_signals:
        quantitative_signals = "No explicit numeric metric surfaced in the source excerpt"

    cross_dept_impact = _coerce_string_list(raw.get("cross_dept_impact"))
    if not cross_dept_impact:
        cross_dept_impact = _default_cross_dept(department)

    expected_profit_impact = _coerce_string(raw.get("expected_profit_impact"))
    if not expected_profit_impact:
        expected_profit_impact = (
            "Potential uplift from disciplined execution and capital efficiency"
            if chosen_option == "Proceed"
            else "Potential downside reduction through timing, re-scoping, or remediation"
        )

    profit_impact_pathway = _coerce_string(raw.get("profit_impact_pathway"))
    if not profit_impact_pathway:
        profit_impact_pathway = f"{department.lower()} signal -> execution choices -> financial impact"

    outcome_status = _coerce_string(raw.get("outcome_status")) or "proposed"
    outcome_summary = _coerce_string(raw.get("outcome_summary"))
    if not outcome_summary:
        outcome_summary = (
            f"If the decision proceeds, {department.lower()} actions should improve execution clarity next quarter."
        )

    tags = _coerce_string_list(raw.get("decision_tags"))
    if len(tags) < 3:
        tags = _default_tags(department, risk_level, bool(source_excerpt))

    conflicting_perspectives = _coerce_string(raw.get("conflicting_perspectives"))
    if not conflicting_perspectives:
        conflicting_perspectives = (
            f"Finance sees the strongest linkage to capital deployment while {department.lower()} emphasizes execution risk."
        )

    master_agent_decision = _coerce_string(raw.get("master_agent_decision")) or chosen_option

    return {
        "source_excerpt": source_excerpt,
        "department": department,
        "decision_title": decision_title,
        "decision_archetype": decision_archetype,
        "trigger": trigger,
        "decision_description": decision_description,
        "options": options,
        "chosen_option": chosen_option,
        "reasoning_summary": reasoning_summary,
        "quantitative_signals": quantitative_signals,
        "risk_level": risk_level,
        "cross_dept_impact": cross_dept_impact,
        "expected_profit_impact": expected_profit_impact,
        "profit_impact_pathway": profit_impact_pathway,
        "outcome_status": outcome_status,
        "outcome_summary": outcome_summary,
        "decision_tags": tags,
        "conflicting_perspectives": conflicting_perspectives,
        "master_agent_decision": master_agent_decision,
    }


def _intermediate_to_decision_case(
    intermediate: dict[str, Any],
    *,
    case_id: int,
    quarter: str,
    source_file_name: str,
) -> DecisionCase:
    """Map a normalized intermediate to the full DecisionCase model.

    Deterministic fields (case_id, quarter, source_file_name, confidences,
    options_considered string, joined lists) are populated here.
    """
    department = intermediate["department"]
    risk_level = intermediate["risk_level"]
    chosen_option = intermediate["chosen_option"]

    base_confidence = 0.66 if risk_level == "Low" else 0.58 if risk_level == "Medium" else 0.49
    profit_confidence = round(base_confidence, 2)
    master_confidence = round(
        max(0.45, min(0.9, base_confidence + (0.08 if department == "Finance" else 0.05))),
        2,
    )

    finance_conf = _role_confidence(profit_confidence, department, "finance", risk_level)
    rnd_conf = _role_confidence(profit_confidence - 0.04, department, "r_and_d", risk_level)
    ops_conf = _role_confidence(profit_confidence - 0.02, department, "ops", risk_level)
    legal_conf = _role_confidence(profit_confidence - 0.03, department, "legal", risk_level)

    payload = {
        "case_id": case_id,
        "source_file_name": source_file_name,
        "source_excerpt": intermediate["source_excerpt"],
        "quarter": quarter,
        "department": department,
        "decision_title": intermediate["decision_title"],
        "decision_archetype": intermediate["decision_archetype"],
        "trigger": intermediate["trigger"],
        "decision_description": intermediate["decision_description"],
        "options_considered": _serialize_options(intermediate["options"]),
        "chosen_option": chosen_option,
        "reasoning_summary": intermediate["reasoning_summary"],
        "quantitative_signals": intermediate["quantitative_signals"],
        "risk_level": risk_level,
        "cross_dept_impact": ";".join(intermediate["cross_dept_impact"]),
        "expected_profit_impact": intermediate["expected_profit_impact"],
        "profit_confidence": profit_confidence,
        "profit_impact_pathway": intermediate["profit_impact_pathway"],
        "outcome_status": intermediate["outcome_status"],
        "outcome_summary": intermediate["outcome_summary"],
        "decision_tags": ",".join(intermediate["decision_tags"]),
        "finance_agent_conf": finance_conf,
        "r_and_d_agent_conf": rnd_conf,
        "ops_agent_conf": ops_conf,
        "legal_agent_conf": legal_conf,
        "conflicting_perspectives": intermediate["conflicting_perspectives"],
        "master_agent_decision": intermediate["master_agent_decision"],
        "master_agent_confidence": master_confidence,
    }
    return DecisionCase.model_validate(payload)


def _decision_case_to_intermediate(case: DecisionCase) -> dict[str, Any]:
    """Reverse-map a DecisionCase back into the intermediate shape.

    Used by the repair flow so we can send the current state of each flagged case
    to the LLM in the same schema it originally produced.
    """
    options: list[dict[str, str]] = []
    for chunk in case.options_considered.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" in chunk:
            label, _, summary = chunk.partition(":")
        else:
            label, summary = chunk, chunk
        options.append({"label": label.strip().title(), "summary": summary.strip()})

    return {
        "source_excerpt": case.source_excerpt,
        "department": case.department,
        "decision_title": case.decision_title,
        "decision_archetype": case.decision_archetype,
        "trigger": case.trigger,
        "decision_description": case.decision_description,
        "options": options,
        "chosen_option": case.chosen_option,
        "reasoning_summary": case.reasoning_summary,
        "quantitative_signals": case.quantitative_signals,
        "risk_level": case.risk_level,
        "cross_dept_impact": [c for c in case.cross_dept_impact.split(";") if c.strip()],
        "expected_profit_impact": case.expected_profit_impact,
        "profit_impact_pathway": case.profit_impact_pathway,
        "outcome_status": case.outcome_status,
        "outcome_summary": case.outcome_summary,
        "decision_tags": [t for t in case.decision_tags.split(",") if t.strip()],
        "conflicting_perspectives": case.conflicting_perspectives,
        "master_agent_decision": case.master_agent_decision,
    }


# ---------------------------------------------------------------------------
# Generation Agent
# ---------------------------------------------------------------------------


class DecisionGenerationAgent:
    def __init__(self, llm_client: LLMClient, prompt_builder: PromptBuilder) -> None:
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        self._generation_prompt_metadata = prompt_builder.get_prompt_metadata("generation")
        self._repair_prompt_metadata = prompt_builder.get_prompt_metadata("repair")

    def _source_sentences(self, context: EnterpriseContext) -> list[str]:
        ordered_lists = [context.explicit_case_candidates]
        ordered_lists.extend(
            [
                context.board_actions,
                context.business_guidance,
                context.management_outlook,
                context.financial_metrics,
                context.operational_updates,
                context.legal_updates,
                context.products,
                context.risks,
                context.strategy,
                context.governance,
            ]
        )
        sentences: list[str] = []
        for items in ordered_lists:
            for item in items:
                for sentence in split_sentences(item):
                    cleaned = clean_text(sentence)
                    if len(cleaned) >= 40 and cleaned not in sentences:
                        sentences.append(cleaned)
        return sentences

    def _theme_seed(self, context: EnterpriseContext) -> list[tuple[str, str]]:
        seeds: list[tuple[str, str]] = []
        for theme in context.decision_themes:
            for sentence in context.evidence_by_theme.get(theme, []):
                seeds.append((theme, sentence))
        if not seeds:
            fallback_sentences = self._source_sentences(context)
            seeds.extend(("operating_model", sentence) for sentence in fallback_sentences)
        return seeds

    def _load_json_payload(self, response_text: str) -> dict[str, Any] | None:
        """Parse JSON with robust error handling and logging."""
        try:
            # Try direct parsing first
            payload = json.loads(response_text)
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode failed: {e}. Response preview: {response_text[:500]}")
            
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                try:
                    payload = json.loads(json_match.group(1))
                    logger.info("Successfully extracted JSON from markdown code block")
                    return payload if isinstance(payload, dict) else None
                except Exception:
                    pass
            
            # Try to find JSON object in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    payload = json.loads(json_match.group(0))
                    logger.info("Successfully extracted JSON object from response")
                    return payload if isinstance(payload, dict) else None
                except Exception:
                    pass
            
            logger.error(f"Could not parse JSON. Full response: {response_text[:1000]}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}")
            return None

    def _source_file_for_context(self, context: EnterpriseContext) -> str:
        if context.source_documents:
            return context.source_documents[0]
        return "enterprise_context.json"

    # ---------------- Heuristic fallback (intermediate shape) ------------------------

    def _heuristic_intermediates(
        self,
        *,
        context: EnterpriseContext,
        previous_cases: list[DecisionCase],
        requested_cases: int,
    ) -> list[dict[str, Any]]:
        """Produce well-formed intermediate dicts (not DecisionCase) as a fallback.

        Uses the existing rule-based `build_case_row` to keep behavior consistent
        with prior heuristics, then reshapes into the intermediate schema.
        """
        seen_titles = {case.decision_title.strip().lower() for case in previous_cases}
        intermediates: list[dict[str, Any]] = []
        quarter = context.quarter
        source_file = self._source_file_for_context(context)

        explicit_sentences = context.explicit_case_candidates or self._source_sentences(context)
        theme_seeds = self._theme_seed(context)

        def row_to_intermediate(row: dict[str, Any]) -> dict[str, Any]:
            options: list[dict[str, str]] = []
            for chunk in str(row.get("options_considered", "")).split(";"):
                chunk = chunk.strip()
                if not chunk:
                    continue
                label, _, summary = chunk.partition(":")
                options.append(
                    {
                        "label": label.strip().title() or "Proceed",
                        "summary": summary.strip() or label.strip(),
                    }
                )
            return {
                "source_excerpt": row["source_excerpt"],
                "department": row["department"],
                "decision_title": row["decision_title"],
                "decision_archetype": row["decision_archetype"],
                "trigger": row["trigger"],
                "decision_description": row["decision_description"],
                "options": options,
                "chosen_option": row["chosen_option"],
                "reasoning_summary": row["reasoning_summary"],
                "quantitative_signals": row["quantitative_signals"],
                "risk_level": row["risk_level"],
                "cross_dept_impact": [
                    part for part in str(row["cross_dept_impact"]).split(";") if part.strip()
                ],
                "expected_profit_impact": row["expected_profit_impact"],
                "profit_impact_pathway": row["profit_impact_pathway"],
                "outcome_status": row["outcome_status"],
                "outcome_summary": row["outcome_summary"],
                "decision_tags": [
                    part for part in str(row["decision_tags"]).split(",") if part.strip()
                ],
                "conflicting_perspectives": row["conflicting_perspectives"],
                "master_agent_decision": row["master_agent_decision"],
            }

        # Explicit-first
        for index, sentence in enumerate(explicit_sentences, start=1):
            row = build_case_row(
                case_id=index,
                source_file_name=source_file,
                source_excerpt=sentence,
                quarter=quarter,
                company_name=context.company_name,
            )
            title_key = row["decision_title"].strip().lower()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            intermediates.append(row_to_intermediate(row))
            if len(intermediates) >= requested_cases:
                return intermediates

        # Synthetic fill using theme seeds
        if not intermediates and theme_seeds:
            for index, (_, sentence) in enumerate(theme_seeds[: max(1, min(requested_cases, 3))]):
                row = build_case_row(
                    case_id=index + 1,
                    source_file_name=source_file,
                    source_excerpt=sentence,
                    quarter=quarter,
                    company_name=context.company_name,
                )
                intermediates.append(row_to_intermediate(row))

        base_pool = list(intermediates)
        if not base_pool:
            return intermediates

        for synthetic_index, (theme, sentence) in enumerate(
            cycle(theme_seeds or [("operating_model", "")]), start=1
        ):
            if len(intermediates) >= requested_cases:
                break
            base = base_pool[(synthetic_index - 1) % len(base_pool)]
            variant = dict(base)
            title = (
                f"{context.company_name + ': ' if context.company_name else ''}"
                f"{theme.replace('_', ' ').title()} decision {synthetic_index}"
            )
            variant["decision_title"] = title
            variant["trigger"] = title
            variant["source_excerpt"] = sentence or variant["source_excerpt"]
            variant["reasoning_summary"] = clean_text(
                f"Extends the validated enterprise themes by recombining {theme.replace('_', ' ')} signals with prior decisions."
            )
            variant["decision_description"] = clean_text(
                f"{variant['department']} is considering {theme.replace('_', ' ')} actions in response to updated enterprise context."
            )
            variant["outcome_summary"] = (
                "Synthetic follow-on case grounded in the validated enterprise themes."
            )
            variant["outcome_status"] = "proposed"

            title_key = title.strip().lower()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            intermediates.append(variant)

        return intermediates[:requested_cases]

    # ---------------- Parse LLM response ---------------------------------------------

    def _parse_generation_response(self, response_text: str) -> list[dict[str, Any]]:
        payload = self._load_json_payload(response_text)
        if not payload:
            return []
        raw_cases = payload.get("cases")
        if not isinstance(raw_cases, list):
            return []
        intermediates: list[dict[str, Any]] = []
        for raw in raw_cases:
            if not isinstance(raw, dict):
                continue
            try:
                intermediates.append(_normalize_intermediate(raw))
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("generation_normalize_failed=%s", exc)
        return intermediates

    def _map_intermediates_to_cases(
        self,
        intermediates: list[dict[str, Any]],
        *,
        context: EnterpriseContext,
        starting_case_id: int,
    ) -> list[DecisionCase]:
        source_file = self._source_file_for_context(context)
        cases: list[DecisionCase] = []
        for offset, intermediate in enumerate(intermediates):
            case_id = starting_case_id + offset
            try:
                case = _intermediate_to_decision_case(
                    intermediate,
                    case_id=case_id,
                    quarter=context.quarter,
                    source_file_name=source_file,
                )
            except Exception as exc:
                logger.warning("map_intermediate_to_case_failed=%s intermediate=%s", exc, intermediate)
                continue
            cases.append(case)
        return cases

    # ---------------- Public API -----------------------------------------------------

    # ``metadata`` accepts a dictionary, not a function that builds one from
    # method arguments.  Keep tracing enabled without passing an invalid value.
    @traceable(name="Generation Agent")
    def generate(
        self,
        *,
        context: EnterpriseContext,
        previous_cases: list[DecisionCase],
        requested_cases: int,
        feedback: list[str] | None = None,
        starting_case_id: int = 1,
    ) -> list[DecisionCase]:
        """Generate a batch of DecisionCases.

        When feedback is supplied this method still runs a *generation* prompt
        (fresh cases). Targeted repair (patching an existing batch) is handled
        by `repair()` instead. The orchestrator historically called `generate`
        with feedback, so we preserve that behavior: feedback influences the
        generation prompt, but the LLM contract remains the intermediate schema.
        """
        prompt = self.prompt_builder.build_generation_prompt(
            context=context,
            previous_cases=previous_cases,
            requested_cases=requested_cases,
            feedback=feedback,
        )
        if feedback:
            logger.info("generation_feedback=%s", feedback)

        # Try to get valid JSON response with retry
        max_json_retries = 2
        intermediates = []
        
        for json_attempt in range(max_json_retries):
            response_text = self.llm_client.complete(prompt, response_format="json")
            intermediates = self._parse_generation_response(response_text)
            
            if intermediates:
                break
            
            if json_attempt < max_json_retries - 1:
                logger.warning(f"JSON parsing failed (attempt {json_attempt + 1}/{max_json_retries}). Retrying with clearer instructions...")
                # Add explicit JSON-only instruction to feedback
                json_feedback = ["CRITICAL: Return ONLY valid JSON. No markdown, no explanatory text, just the JSON object."]
                if feedback:
                    json_feedback.extend(feedback)
                prompt = self.prompt_builder.build_generation_prompt(
                    context=context,
                    previous_cases=previous_cases,
                    requested_cases=requested_cases,
                    feedback=json_feedback,
                )
            else:
                logger.error(f"JSON parsing failed after {max_json_retries} attempts. Falling back to heuristics.")

        if not intermediates:
            logger.info("generation_falling_back_to_heuristics")
            intermediates = self._heuristic_intermediates(
                context=context,
                previous_cases=previous_cases,
                requested_cases=requested_cases,
            )

        intermediates = intermediates[:requested_cases]
        cases = self._map_intermediates_to_cases(
            intermediates,
            context=context,
            starting_case_id=starting_case_id,
        )

        if not cases:
            # Absolute last resort: heuristic intermediates → cases.
            fallback_intermediates = self._heuristic_intermediates(
                context=context,
                previous_cases=previous_cases,
                requested_cases=requested_cases,
            )
            cases = self._map_intermediates_to_cases(
                fallback_intermediates,
                context=context,
                starting_case_id=starting_case_id,
            )

        # Renumber case_ids to be globally unique across batches.
        for offset, case in enumerate(cases):
            case.case_id = starting_case_id + offset
        return cases

    @traceable(name="Repair Agent")
    def repair(
        self,
        *,
        context: EnterpriseContext,
        previous_cases: list[DecisionCase],
        current_cases: list[DecisionCase],
        feedback_by_case: dict[int, list[str]],
        general_feedback: list[str] | None = None,
    ) -> list[DecisionCase]:
        """Repair only the cases flagged by the Validation Agent.

        Steps:
        1. Convert current DecisionCases back into intermediate dicts.
        2. Ask the LLM for `patches` (case_id + partial field updates).
        3. Merge patches into the intermediates in Python.
        4. Re-normalize + re-map to DecisionCase, preserving deterministic fields.
        """
        if not current_cases:
            return []

        intermediates_by_id: dict[int, dict[str, Any]] = {}
        for case in current_cases:
            intermediates_by_id[case.case_id] = _decision_case_to_intermediate(case)

        # Attach case_id to the payload we send to the prompt builder.
        payload_intermediates = [
            {"case_id": case_id, **intermediate}
            for case_id, intermediate in intermediates_by_id.items()
        ]

        prompt = self.prompt_builder.build_repair_prompt(
            context=context,
            previous_cases=previous_cases,
            requested_cases=len(current_cases),
            feedback=general_feedback or [],
            current_intermediates=payload_intermediates,
            feedback_by_case=feedback_by_case,
        )

        # Try to get valid JSON response with retry
        max_json_retries = 2
        patches = None
        
        for json_attempt in range(max_json_retries):
            response_text = self.llm_client.complete(prompt, response_format="json")
            payload = self._load_json_payload(response_text)
            patches = payload.get("patches") if isinstance(payload, dict) else None
            
            if patches is not None:
                break
            
            if json_attempt < max_json_retries - 1:
                logger.warning(f"Repair JSON parsing failed (attempt {json_attempt + 1}/{max_json_retries}). Retrying...")

        if isinstance(patches, list):
            for patch in patches:
                if not isinstance(patch, dict):
                    continue
                case_id = patch.get("case_id")
                fields = patch.get("fields")
                if not isinstance(case_id, int) or not isinstance(fields, dict):
                    continue
                target = intermediates_by_id.get(case_id)
                if target is None:
                    continue
                for field_name, new_value in fields.items():
                    if field_name not in INTERMEDIATE_FIELDS:
                        continue
                    target[field_name] = new_value
        else:
            logger.warning("repair_patches_missing_or_malformed response=%s", response_text[:200])

        # Re-normalize each intermediate (patched or not) and remap to DecisionCase,
        # preserving the original case_id ordering.
        ordered_case_ids = [case.case_id for case in current_cases]
        repaired_cases: list[DecisionCase] = []
        source_file = self._source_file_for_context(context)
        for case_id in ordered_case_ids:
            intermediate = intermediates_by_id[case_id]
            normalized = _normalize_intermediate(intermediate)
            try:
                repaired = _intermediate_to_decision_case(
                    normalized,
                    case_id=case_id,
                    quarter=context.quarter,
                    source_file_name=source_file,
                )
            except Exception as exc:
                logger.warning("repair_map_failed case_id=%s error=%s", case_id, exc)
                # Fall back to the original case.
                repaired = next(c for c in current_cases if c.case_id == case_id)
            repaired_cases.append(repaired)
        return repaired_cases
