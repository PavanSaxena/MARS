from __future__ import annotations

from collections import Counter, defaultdict

import re

from app.models.context import EnterpriseContext
from app.models.document import ParsedDocument


KEYWORD_GROUPS = {
    "financial_metrics": ("revenue", "cash", "liquidity", "profit", "margin", "earnings", "guidance", "forecast", "expense", "debt", "capex", "cost", "eps", "buyback", "dividend"),
    "governance": ("board", "governance", "committee", "proxy", "director", "vote", "shareholder"),
    "board_actions": ("approved", "authorized", "elected", "appointed", "adopted", "ratified", "recommended"),
    "legal_updates": ("legal", "litigation", "lawsuit", "settlement", "compliance", "regulatory", "investigation", "contract"),
    "operational_updates": ("operations", "supply", "inventory", "manufacturing", "logistics", "procurement", "capacity", "system outage"),
    "products": ("product", "launch", "release", "platform", "prototype", "roadmap", "service"),
    "risks": ("risk", "uncertain", "volatility", "impairment", "breach", "default", "slowdown"),
    "management_outlook": ("outlook", "expects", "expects to", "anticipates", "guidance", "forecast"),
    "strategy": ("strategy", "invest", "expand", "restructure", "transformation", "optimization", "market share", "acquisition", "acquire"),
    "business_guidance": ("guidance", "forecast", "projection", "range", "expect", "revised"),
}

THEME_GROUPS = {
    "capital_allocation": ("buyback", "dividend", "share repurchase", "cash", "liquidity", "debt", "capital return", "treasury"),
    "guidance_revision": ("guidance", "forecast", "reforecast", "projection", "margin", "revenue", "outlook"),
    "product_roadmap": ("product", "launch", "roadmap", "feature", "platform", "device", "service", "release"),
    "supply_chain": ("supply", "inventory", "manufacturing", "logistics", "capacity", "vendor", "procurement", "fulfillment"),
    "legal_compliance": ("legal", "litigation", "lawsuit", "settlement", "compliance", "regulatory", "investigation", "contract"),
    "governance": ("board", "committee", "proxy", "director", "vote", "shareholder", "governance"),
    "r_and_d_prioritization": ("research", "development", "engineering", "innovation", "prototype", "trial", "platform"),
    "operating_model": ("operations", "cost", "expense", "vendor", "productivity", "efficiency", "restructure"),
}

ACTIONABLE_VERBS = (
    "approve",
    "revise",
    "delay",
    "defer",
    "pause",
    "expand",
    "reduce",
    "reallocate",
    "increase",
    "launch",
    "prioritize",
    "renegotiate",
    "restructure",
    "authorize",
    "acquire",
)

# Bucket priorities for evidence ranking (higher = more important)
BUCKET_PRIORITY = {
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


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    return [part.strip() for part in parts if part.strip()]


def _detect_company_name(text: str, fallback: str) -> str:
    match = re.search(r"([A-Z][A-Za-z0-9&.,\- ]{2,}?(?:Inc\.|Corporation|Corp\.|Company|PLC|Ltd\.|LLC))", text)
    if match:
        return match.group(1).strip().rstrip(".,")
    return fallback


def _theme_for_sentence(sentence: str) -> str | None:
    lowered = sentence.lower()
    for theme, keywords in THEME_GROUPS.items():
        if any(keyword in lowered for keyword in keywords):
            return theme
    return None


def _is_explicit_decision_sentence(sentence: str) -> bool:
    lowered = sentence.lower()
    return len(sentence) >= 55 and any(verb in lowered for verb in ACTIONABLE_VERBS)


def _has_number(sentence: str) -> bool:
    return bool(re.search(r"\$\d|\d+(?:\.\d+)?%|\d{2,}", sentence))


def _shorten(sentence: str, max_chars: int = 220) -> str:
    cleaned = " ".join(sentence.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rsplit(" ", 1)[0] + "…"


class EnterpriseContextBuilder:
    def build(self, documents: list[ParsedDocument], quarter: str) -> EnterpriseContext:
        buckets: dict[str, list[str]] = {name: [] for name in KEYWORD_GROUPS}
        evidence_by_theme: dict[str, list[str]] = defaultdict(list)
        explicit_case_candidates: list[str] = []
        theme_counter: Counter[str] = Counter()
        source_documents: list[str] = []
        document_types: list[str] = []
        combined_text_parts: list[str] = []

        for document in documents:
            source_documents.append(document.file_name)
            document_types.append(document.document_type)
            text = " ".join(document.pages or [chunk.text for chunk in document.chunks])
            combined_text_parts.append(text)
            for sentence in _sentences(text):
                lowered = sentence.lower()
                for bucket_name, keywords in KEYWORD_GROUPS.items():
                    if any(keyword in lowered for keyword in keywords):
                        if sentence not in buckets[bucket_name]:
                            buckets[bucket_name].append(sentence)

                theme = _theme_for_sentence(sentence)
                if theme:
                    theme_counter[theme] += 1
                    if sentence not in evidence_by_theme[theme]:
                        evidence_by_theme[theme].append(sentence)

                if _is_explicit_decision_sentence(sentence) and sentence not in explicit_case_candidates:
                    explicit_case_candidates.append(sentence)

        combined_text = "\n".join(combined_text_parts)
        company_name = _detect_company_name(
            combined_text,
            source_documents[0].rsplit(".", 1)[0] if source_documents else "",
        )

        ordered_themes = [theme for theme, _ in theme_counter.most_common()]
        if not ordered_themes:
            ordered_themes = ["guidance_revision", "capital_allocation", "operating_model"]

        # Rank each bucket: keep short, numeric, or explicit-decision-heavy sentences first.
        def _score(sentence: str) -> tuple[int, int]:
            score = 0
            if _has_number(sentence):
                score += 3
            lowered = sentence.lower()
            if any(verb in lowered for verb in ACTIONABLE_VERBS):
                score += 2
            # Prefer moderately-sized sentences over walls of text.
            length_penalty = 0 if 60 <= len(sentence) <= 240 else 1
            return (score, -length_penalty)

        ranked_buckets = {
            name: sorted(items, key=_score, reverse=True)
            for name, items in buckets.items()
        }

        # Compact evidence: 3-5 shortened sentences per bucket.
        def _top(items: list[str], limit: int) -> list[str]:
            return [_shorten(item) for item in items[:limit]]

        financial_metrics = _top(ranked_buckets["financial_metrics"], 5)
        governance = _top(ranked_buckets["governance"], 3)
        board_actions = _top(ranked_buckets["board_actions"], 4)
        legal_updates = _top(ranked_buckets["legal_updates"], 3)
        operational_updates = _top(ranked_buckets["operational_updates"], 3)
        products = _top(ranked_buckets["products"], 3)
        risks = _top(ranked_buckets["risks"], 3)
        management_outlook = _top(ranked_buckets["management_outlook"], 3)
        strategy = _top(ranked_buckets["strategy"], 4)
        business_guidance = _top(ranked_buckets["business_guidance"], 3)

        # Explicit case candidates: rank and cap tighter than before.
        explicit_case_candidates_sorted = sorted(explicit_case_candidates, key=_score, reverse=True)
        explicit_case_candidates_compact = [_shorten(item) for item in explicit_case_candidates_sorted[:10]]

        # evidence_by_theme: keep only top 3 short sentences per theme, at most 6 themes.
        top_themes = ordered_themes[:6]
        evidence_by_theme_compact: dict[str, list[str]] = {}
        for theme in top_themes:
            sentences = sorted(evidence_by_theme.get(theme, []), key=_score, reverse=True)[:3]
            if sentences:
                evidence_by_theme_compact[theme] = [_shorten(s) for s in sentences]

        summary_parts = [f"{name}: {len(items)}" for name, items in buckets.items() if items]

        return EnterpriseContext(
            company_name=company_name,
            quarter=quarter,
            source_documents=source_documents,
            document_types=sorted(set(document_types)),
            decision_themes=ordered_themes[:6],
            financial_metrics=financial_metrics,
            governance=governance,
            board_actions=board_actions,
            legal_updates=legal_updates,
            operational_updates=operational_updates,
            products=products,
            risks=risks,
            management_outlook=management_outlook,
            strategy=strategy,
            business_guidance=business_guidance,
            explicit_case_candidates=explicit_case_candidates_compact,
            evidence_by_theme=evidence_by_theme_compact,
            summary="; ".join(summary_parts),
        )