from typing import List

# `outcome` on each case is the free-text `outcome_summary` field pulled
# straight from Supabase (see app.services.case_retrieval_service) — it's a
# prose sentence like "Successful rollout, 20% cost savings" or "Delayed six
# months, project cancelled", not a fixed success/failure enum. An exact
# comparison against the literal string "success" essentially never matches
# real data, so this classifies each summary via keyword matching instead.
_SUCCESS_KEYWORDS = (
    "success",
    "succeeded",
    "successful",
    "achieved",
    "exceeded",
    "growth",
    "grew",
    "expanded",
    "expansion",
    "on track",
    "on-track",
    "profitable",
    "effective",
    "favorable",
    "favourable",
    "approved",
    "complied",
    "compliance",
    "mitigated",
    "resolved",
    "cleared",
    "clearance",
    "completed",
    "positive",
)
_FAILURE_KEYWORDS = (
    "fail",
    "failed",
    "failure",
    "unsuccessful",
    "missed",
    "delayed",
    "delay",
    "over budget",
    "loss",
    "losses",
    "abandoned",
    "cancelled",
    "canceled",
    "ineffective",
    "unfavorable",
    "unfavourable",
    "penalty",
    "penalties",
    "violation",
    "breach",
    "rejection",
    "declined",
    "non-compliance",
    "non-compliant",
    "non compliance",
)


_NEGATED_FAILURE_PATTERNS = (
    "zero penalties",
    "no penalties",
    "zero fines",
    "no fines",
    "zero loss",
    "no loss",
    "no violation",
    "zero violation",
    "without violation",
    "without penalty",
    "without fine",
    "without delay",
)

_NEGATED_SUCCESS_PATTERNS = (
    "non-compliance",
    "non compliance",
    "non-compliant",
    "non compliant",
    "not compliant",
    "not approved",
    "unresolved",
)


def _classify(outcome_text: str) -> str:
    """Classify a free-text outcome summary as 'success', 'failure', or
    'unknown' (ambiguous / no recognizable keywords)."""
    text = (outcome_text or "").lower()

    # Pre-check negated failure phrases (e.g. "zero penalties" -> positive outcome)
    has_negated_failure = any(p in text for p in _NEGATED_FAILURE_PATTERNS)
    # Pre-check negated success phrases (e.g. "non-compliance" -> negative outcome, not positive)
    has_negated_success = any(p in text for p in _NEGATED_SUCCESS_PATTERNS)

    clean_success_text = text
    if has_negated_success:
        for p in _NEGATED_SUCCESS_PATTERNS:
            clean_success_text = clean_success_text.replace(p, " ")

    is_success = any(keyword in clean_success_text for keyword in _SUCCESS_KEYWORDS) or has_negated_failure

    # If failure keyword is only part of a negated phrase, don't flag as failure
    is_failure = any(keyword in text for keyword in _FAILURE_KEYWORDS) or has_negated_success
    if has_negated_failure:
        # Strip negated phrases to re-evaluate remaining text for actual failure keywords
        clean_text = text
        for p in _NEGATED_FAILURE_PATTERNS:
            clean_text = clean_text.replace(p, " ")
        is_failure = any(keyword in clean_text for keyword in _FAILURE_KEYWORDS)

    if is_success and not is_failure:
        return "success"
    if is_failure and not is_success:
        return "failure"
    return "unknown"


def analyze_outcomes(cases: List[dict]) -> float:
    """
    Calculate the empirical success rate from a list of retrieved cases.

    Prioritizes the structured `outcome_label` field whenever present.
    Falls back to keyword matching on free-text outcome summaries.
    If classified outcomes exist, returns the success ratio in [0.0, 1.0].
    If cases exist but none contain explicit polarity keywords, returns a
    neutral baseline prior of 0.5.
    Returns 0.0 only if the case list is empty.
    """
    if not cases:
        return 0.0

    classifications: List[str] = []
    for case in cases:
        meta = case.get("metadata") or {}
        label = case.get("outcome_label")
        if label is None:
            label = meta.get("outcome_label")

        if label is not None:
            if isinstance(label, bool):
                classifications.append("success" if label else "failure")
                continue
            if isinstance(label, (int, float)):
                classifications.append("success" if label >= 0.5 else "failure")
                continue
            lbl_str = str(label).lower().strip()
            if lbl_str in ("success", "positive", "1", "true", "pass"):
                classifications.append("success")
                continue
            elif lbl_str in ("failure", "negative", "0", "false", "fail"):
                classifications.append("failure")
                continue

        # Fallback to free-text keyword classification
        text = case.get("outcome") or meta.get("outcome") or ""
        classifications.append(_classify(text))

    known = [c for c in classifications if c != "unknown"]

    if not known:
        return 0.5

    success = sum(1 for c in known if c == "success")
    return success / len(known)
