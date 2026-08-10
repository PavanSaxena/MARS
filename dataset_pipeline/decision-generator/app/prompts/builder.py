from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from app.config import MAX_EVIDENCE_ITEMS, MAX_PREVIOUS_CASE_SUMMARIES, MAX_PROMPT_TOKENS
from app.llm.client import PromptBundle
from app.models.context import EnterpriseContext
from app.models.decision_case import DecisionCase


logger = logging.getLogger(__name__)


# Prompt version tracking for LangSmith observability
GENERATION_PROMPT_VERSION = "v1.0"
VALIDATION_PROMPT_VERSION = "v1.0"
REPAIR_PROMPT_VERSION = "v1.0"
SYSTEM_PROMPT_VERSION = "v1.0"


# Rough estimator: ~4 characters per token for English text/JSON.
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass(frozen=True)
class PromptTemplates:
    system: str
    generation: str
    validation: str
    repair: str


# Evidence priority: higher rank = more important. Used for ordered ranking + adaptive reduction.
EVIDENCE_RANK = {
    "financial_metrics": 10,
    "board_actions": 9,
    "strategy": 8,
    "business_guidance": 8,
    "management_outlook": 7,
    "operational_updates": 6,
    "products": 6,
    "risks": 5,
    "governance": 5,
    "legal_updates": 4,
}


class PromptBuilder:
    def __init__(self, templates_dir: Path) -> None:
        self.templates_dir = templates_dir
        self._prompt_hashes: dict[str, str] = {}
        self._compute_prompt_hashes()
    
    def _compute_prompt_hash(self, content: str) -> str:
        """Compute SHA-256 hash of prompt template content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def _compute_prompt_hashes(self) -> None:
        """Pre-compute hashes for all prompt templates."""
        templates = self.load_templates()
        self._prompt_hashes = {
            "system": self._compute_prompt_hash(templates.system),
            "generation": self._compute_prompt_hash(templates.generation),
            "validation": self._compute_prompt_hash(templates.validation),
            "repair": self._compute_prompt_hash(templates.repair),
        }
    
    def get_prompt_metadata(self, prompt_type: str) -> dict[str, str]:
        """Get version and hash metadata for a specific prompt type."""
        version_map = {
            "system": SYSTEM_PROMPT_VERSION,
            "generation": GENERATION_PROMPT_VERSION,
            "validation": VALIDATION_PROMPT_VERSION,
            "repair": REPAIR_PROMPT_VERSION,
        }
        return {
            "prompt_version": version_map.get(prompt_type, "unknown"),
            "prompt_hash": self._prompt_hashes.get(prompt_type, "unknown"),
        }

    def _read(self, name: str, default_text: str) -> str:
        path = self.templates_dir / name
        return path.read_text(encoding="utf-8") if path.exists() else default_text

    def load_templates(self) -> PromptTemplates:
        return PromptTemplates(
            system=self._read("system.md", "You are a senior enterprise case writer for the MARS pipeline."),
            generation=self._read("generation.md", "Generate valid JSON decision cases only."),
            validation=self._read("validation.md", "Return PASS or FAIL with concise feedback only."),
            repair=self._read("repair.md", "Repair invalid candidate cases using the validation feedback."),
        )

    # ---------------- Compact case summaries (previous accepted cases) ----------------

    @staticmethod
    def _compact_previous_cases(cases: list[DecisionCase], limit: int) -> list[dict]:
        """Return minimal duplicate-avoidance signatures for previous accepted cases.

        Keeps only: title, trigger, chosen_option, profit_impact_pathway, department.
        """
        if not cases:
            return []
        # Prefer the most recent (last N) accepted cases as duplicate-avoidance signal.
        tail = cases[-limit:]
        return [
            {
                "title": case.decision_title,
                "trigger": case.trigger,
                "chosen_option": case.chosen_option,
                "profit_impact_pathway": case.profit_impact_pathway,
                "department": case.department,
            }
            for case in tail
        ]

    # ---------------- Ranked evidence extraction from context -------------------------

    @staticmethod
    def _ranked_evidence(context: EnterpriseContext) -> list[tuple[str, str]]:
        """Return a ranked list of (bucket_name, sentence) evidence tuples."""
        buckets = {
            "financial_metrics": context.financial_metrics,
            "board_actions": context.board_actions,
            "strategy": context.strategy,
            "business_guidance": context.business_guidance,
            "management_outlook": context.management_outlook,
            "operational_updates": context.operational_updates,
            "products": context.products,
            "risks": context.risks,
            "governance": context.governance,
            "legal_updates": context.legal_updates,
        }
        # Round-robin so we don't spend the entire budget on one bucket.
        ordered_names = sorted(buckets.keys(), key=lambda n: EVIDENCE_RANK.get(n, 0), reverse=True)
        indexed = {name: list(buckets[name]) for name in ordered_names}
        result: list[tuple[str, str]] = []
        while any(indexed[name] for name in ordered_names):
            for name in ordered_names:
                if indexed[name]:
                    sentence = indexed[name].pop(0)
                    result.append((name, sentence))
        return result

    # ---------------- Compact structured enterprise context ---------------------------

    @staticmethod
    def _build_compact_context(
        context: EnterpriseContext,
        *,
        max_evidence: int,
        include_explicit: bool = True,
        include_themes: bool = True,
        include_secondary: bool = True,
    ) -> dict:
        """Build a compact dict representation of the enterprise context.

        `max_evidence` caps the total evidence bullet count in the mid-priority buckets.
        Core (company, quarter, financial metrics, governance, board_actions, strategy)
        are never removed.
        """
        ranked = PromptBuilder._ranked_evidence(context)
        # Core buckets always preserved.
        core_buckets = {"financial_metrics", "board_actions", "governance", "strategy"}
        core_items = [(b, s) for (b, s) in ranked if b in core_buckets]
        secondary_items = [(b, s) for (b, s) in ranked if b not in core_buckets]

        # Take at most max_evidence secondary items.
        secondary_budget = max(0, max_evidence - len(core_items))
        if not include_secondary:
            secondary_budget = 0
        selected = core_items + secondary_items[:secondary_budget]

        # Regroup by bucket in a compact structure.
        grouped: dict[str, list[str]] = {}
        for bucket, sentence in selected:
            grouped.setdefault(bucket, []).append(sentence)

        compact: dict = {
            "company": context.company_name,
            "quarter": context.quarter,
            "documents": context.source_documents,
            "financials": grouped.get("financial_metrics", []),
            "governance": grouped.get("governance", []),
            "board_actions": grouped.get("board_actions", []),
            "strategy": grouped.get("strategy", []),
        }
        if include_secondary:
            compact.update(
                {
                    "products": grouped.get("products", []),
                    "operations": grouped.get("operational_updates", []),
                    "legal": grouped.get("legal_updates", []),
                    "risks": grouped.get("risks", []),
                    "guidance": grouped.get("business_guidance", []),
                    "outlook": grouped.get("management_outlook", []),
                }
            )
        if include_themes and context.decision_themes:
            compact["themes"] = context.decision_themes[:6]
        if include_explicit and context.explicit_case_candidates:
            # Cap explicit candidates - they are usually already high-value.
            compact["explicit_decisions"] = context.explicit_case_candidates[: max(3, max_evidence // 2)]
        return compact

    @staticmethod
    def _render_context_markdown(compact: dict) -> str:
        """Render the compact context as a lightweight bullet-list Markdown block.

        Bullet lists are cheaper than indented JSON (fewer quotes/braces/whitespace).
        """
        lines: list[str] = []
        lines.append(f"Company: {compact.get('company', '')}")
        lines.append(f"Quarter: {compact.get('quarter', '')}")
        docs = compact.get("documents") or []
        if docs:
            lines.append(f"Documents: {', '.join(docs)}")
        themes = compact.get("themes") or []
        if themes:
            lines.append(f"Themes: {', '.join(themes)}")

        section_order = [
            ("Financial Metrics", "financials"),
            ("Governance", "governance"),
            ("Board Actions", "board_actions"),
            ("Strategy", "strategy"),
            ("Products", "products"),
            ("Operations", "operations"),
            ("Legal", "legal"),
            ("Risks", "risks"),
            ("Management Guidance", "guidance"),
            ("Business Outlook", "outlook"),
            ("Explicit Decisions", "explicit_decisions"),
        ]
        for label, key in section_order:
            items = compact.get(key) or []
            if not items:
                continue
            lines.append(f"{label}:")
            for item in items:
                lines.append(f"- {item}")
        return "\n".join(lines)

    # ---------------- Adaptive prompt building ---------------------------------------

    def _assemble_user_prompt(
        self,
        *,
        instructions: str,
        context_md: str,
        previous_summaries: list[dict],
        requested_cases: int,
        feedback: list[str] | None,
        tail_instruction: str,
    ) -> str:
        parts = [
            instructions,
            f"Enterprise Context:\n{context_md}",
        ]
        if previous_summaries:
            # Compact JSON without indent for smaller footprint.
            parts.append(f"Previous accepted cases (avoid duplicates): {previous_summaries}")
        parts.append(f"Requested cases in this batch: {requested_cases}")
        if feedback:
            parts.append(f"Validation feedback to address: {feedback}")
        parts.append(tail_instruction)
        return "\n\n".join(parts)

    def _build_user_prompt_adaptive(
        self,
        *,
        instructions: str,
        context: EnterpriseContext,
        previous_cases: list[DecisionCase],
        requested_cases: int,
        feedback: list[str] | None,
        tail_instruction: str,
        system_prompt: str,
    ) -> tuple[str, dict]:
        """Adaptive reduction loop:
        1. Trim lowest-ranked evidence
        2. Reduce previous case summaries
        3. Drop secondary buckets entirely
        Never removes company, quarter, core financials, governance, board actions, strategy.
        """
        max_evidence = MAX_EVIDENCE_ITEMS
        prev_limit = MAX_PREVIOUS_CASE_SUMMARIES
        include_themes = True
        include_secondary = True
        include_explicit = True

        stats: dict = {}
        for iteration in range(6):
            compact = self._build_compact_context(
                context,
                max_evidence=max_evidence,
                include_explicit=include_explicit,
                include_themes=include_themes,
                include_secondary=include_secondary,
            )
            context_md = self._render_context_markdown(compact)
            previous_summaries = self._compact_previous_cases(previous_cases, prev_limit)
            user_prompt = self._assemble_user_prompt(
                instructions=instructions,
                context_md=context_md,
                previous_summaries=previous_summaries,
                requested_cases=requested_cases,
                feedback=feedback,
                tail_instruction=tail_instruction,
            )
            total_chars = len(system_prompt) + len(user_prompt)
            est_tokens = estimate_tokens(system_prompt + user_prompt)

            evidence_count = sum(
                1
                for key in (
                    "financials",
                    "governance",
                    "board_actions",
                    "strategy",
                    "products",
                    "operations",
                    "legal",
                    "risks",
                    "guidance",
                    "outlook",
                    "explicit_decisions",
                )
                for _ in compact.get(key, [])
            )

            stats = {
                "estimated_tokens": est_tokens,
                "prompt_characters": total_chars,
                "evidence_items": evidence_count,
                "previous_cases": len(previous_summaries),
                "requested_cases": requested_cases,
                "reduction_step": iteration,
            }

            if est_tokens <= MAX_PROMPT_TOKENS:
                return user_prompt, stats

            # Adaptive reduction, in priority order.
            if max_evidence > 8:
                max_evidence -= 3
                continue
            if prev_limit > 5:
                prev_limit = max(3, prev_limit - 3)
                continue
            if include_secondary:
                include_secondary = False
                continue
            if include_explicit:
                # keep only if we have room, otherwise drop
                include_explicit = False
                continue
            if include_themes:
                include_themes = False
                continue
            break

        return user_prompt, stats

    # ---------------- Public API ------------------------------------------------------

    def build_generation_prompt(
        self,
        *,
        context: EnterpriseContext,
        previous_cases: list[DecisionCase],
        requested_cases: int,
        feedback: list[str] | None = None,
    ) -> PromptBundle:
        templates = self.load_templates()
        tail = (
            "Return a JSON object of the form {\"cases\": [ ... ]}. "
            "Emit explicit cases first (drawn from Explicit Decisions or Financial/Board evidence), "
            "then synthetic cases that extend the enterprise themes. "
            "Ensure department diversity (Finance, Legal, Operations, R&D) and materially distinct decisions. "
            "Ground every case in evidence above; do not duplicate previous titles/triggers."
        )
        user_prompt, stats = self._build_user_prompt_adaptive(
            instructions=templates.generation,
            context=context,
            previous_cases=previous_cases,
            requested_cases=requested_cases,
            feedback=feedback,
            tail_instruction=tail,
            system_prompt=templates.system,
        )
        logger.info(
            "prompt_size stage=generation estimated_tokens=%s prompt_characters=%s evidence_items=%s previous_cases=%s batch_size=%s reduction_step=%s",
            stats.get("estimated_tokens"),
            stats.get("prompt_characters"),
            stats.get("evidence_items"),
            stats.get("previous_cases"),
            requested_cases,
            stats.get("reduction_step"),
        )
        return PromptBundle(system_prompt=templates.system, user_prompt=user_prompt)

    def build_repair_prompt(
        self,
        *,
        context: EnterpriseContext,
        previous_cases: list[DecisionCase],
        requested_cases: int,
        feedback: list[str],
        current_intermediates: list[dict] | None = None,
        feedback_by_case: dict[int, list[str]] | None = None,
    ) -> PromptBundle:
        """Build a targeted repair prompt.

        Instead of asking the LLM to regenerate the full batch, we send only
        the flagged cases (as compact intermediate dicts) together with the
        specific feedback per case. The LLM must return a list of patches
        {"patches":[{"case_id": int, "fields": {...}}, ...]} that Python then
        merges into the intermediates before re-mapping to DecisionCase.
        """
        templates = self.load_templates()

        flagged_cases_payload: list[dict] = []
        if current_intermediates and feedback_by_case:
            for intermediate in current_intermediates:
                case_id = intermediate.get("case_id")
                case_feedback = feedback_by_case.get(case_id, [])
                if not case_feedback:
                    continue
                flagged_cases_payload.append(
                    {
                        "case_id": case_id,
                        "current": intermediate,
                        "feedback": case_feedback,
                    }
                )

        tail = (
            "Return a JSON object {\"patches\":[{\"case_id\":<int>,\"fields\":{...}}, ...]} "
            "containing ONE entry per flagged case. Only include field names in \"fields\" "
            "that must change to address the feedback for that case. Do NOT return full cases. "
            "Do NOT regenerate cases that are not in the flagged list."
        )

        # Compact context (small) — repair rarely needs the full enterprise dump.
        compact = self._build_compact_context(
            context,
            max_evidence=6,
            include_explicit=True,
            include_themes=True,
            include_secondary=False,
        )
        context_md = self._render_context_markdown(compact)

        parts = [
            templates.repair,
            f"Enterprise Context (for grounding, do not re-summarize):\n{context_md}",
            f"Flagged cases with per-case feedback: {flagged_cases_payload}",
        ]
        if not flagged_cases_payload and feedback:
            # Fallback: no per-case mapping available — still surface generic feedback.
            parts.append(f"General validation feedback to address: {feedback}")
        parts.append(tail)
        user_prompt = "\n\n".join(parts)

        est_tokens = estimate_tokens(templates.system + user_prompt)
        logger.info(
            "prompt_size stage=repair estimated_tokens=%s prompt_characters=%s flagged_cases=%s",
            est_tokens,
            len(templates.system) + len(user_prompt),
            len(flagged_cases_payload),
        )
        return PromptBundle(system_prompt=templates.system, user_prompt=user_prompt)

    def build_validation_prompt(self, *, cases: list[DecisionCase], feedback: list[str]) -> PromptBundle:
        """Semantic-only LLM validation. Deterministic checks live in Python.

        Sends compact case signatures so the LLM only reviews realism/coherence.
        """
        templates = self.load_templates()
        compact_cases = [
            {
                "case_id": case.case_id,
                "title": case.decision_title,
                "department": case.department,
                "archetype": case.decision_archetype,
                "chosen_option": case.chosen_option,
                "risk_level": case.risk_level,
                "profit_impact_pathway": case.profit_impact_pathway,
            }
            for case in cases
        ]
        instructions = (
            "Review the candidate cases for enterprise realism and semantic coherence only. "
            "Schema, confidence bounds, duplicate detection, and business rules are already enforced in code. "
            "Reply with 'PASS' if all cases read as realistic enterprise decisions, otherwise 'FAIL: <brief reasons>'."
        )
        user_prompt = "\n\n".join(
            [
                templates.validation,
                instructions,
                f"Cases: {compact_cases}",
            ]
        )
        return PromptBundle(system_prompt=templates.system, user_prompt=user_prompt)