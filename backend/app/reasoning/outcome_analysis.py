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
    "on track",
    "on-track",
    "profitable",
    "effective",
    "favorable",
    "favourable",
)
_FAILURE_KEYWORDS = (
    "fail",
    "failed",
    "failure",
    "unsuccessful",
    "missed",
    "delayed",
    "over budget",
    "loss",
    "abandoned",
    "cancelled",
    "canceled",
    "ineffective",
    "unfavorable",
    "unfavourable",
)


def _classify(outcome_text: str) -> str:
    """Classify a free-text outcome summary as 'success', 'failure', or
    'unknown' (ambiguous / no recognizable keywords)."""
    text = (outcome_text or "").lower()
    is_success = any(keyword in text for keyword in _SUCCESS_KEYWORDS)
    is_failure = any(keyword in text for keyword in _FAILURE_KEYWORDS)

    if is_success and not is_failure:
        return "success"
    if is_failure and not is_success:
        return "failure"
    return "unknown"


def analyze_outcomes(cases: List[dict]) -> float:
    """
    Calculate the success rate from a list of retrieved cases.

    Each case's `outcome` (the Supabase `outcome_summary` text) is classified
    via keyword matching (see `_classify`), since it's free text rather than
    a fixed enum. The rate is computed over cases that could be classified
    as success or failure — cases with ambiguous/unrecognized outcome text
    are excluded from the denominator rather than silently counted as
    failures.

    Returns a float in [0, 1], or 0.0 if no cases are provided or none of
    them could be classified.
    """
    if not cases:
        return 0.0

    classifications = [_classify(case.get("outcome", "")) for case in cases]
    known = [c for c in classifications if c != "unknown"]

    if not known:
        return 0.0

    success = sum(1 for c in known if c == "success")
    return success / len(known)
