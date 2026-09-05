from typing import List, Optional


def generate_explanation(
    cases: List[dict],
    confidence: Optional[float],
    tools_used: Optional[List[str]] = None,
    reported_confidence: Optional[float] = None,
) -> str:
    """
    Generate a human-readable explanation of the retrieval, tool-use, and
    confidence result.

    There are three distinct situations:
      1. DB returned nothing  → clearly no cases to work with.
      2. DB returned cases, agent used them (confidence > 0)  → normal path.
      3. DB returned cases, agent dismissed them (confidence = 0.0)
         → the agent found records but considered none relevant enough;
            those cases are NOT surfaced in the frontend (see build_case_evidence).
    """
    confidence_text = (
        f"{confidence:.2f}"
        if confidence is not None
        else "not yet available (scoring formula still in progress)"
    )
    tools_text = (
        f"Tools consulted: {', '.join(tools_used)}."
        if tools_used
        else "No tools were called."
    )

    # Situation 1 — the retriever found nothing at all.
    if not cases:
        return (
            "No relevant historical cases found in the dataset for this query.\n"
            f"Case-based confidence: {confidence_text}.\n"
            f"{tools_text}"
        )

    # Situation 3 — cases were retrieved but the agent judged none useful.
    # Don't surface the cases; just explain that no evidence was used.
    if reported_confidence == 0.0:
        return (
            "Historical cases were retrieved from the dataset but were not "
            "sufficiently relevant to this query to support a grounded recommendation. "
            "No evidence was used in this agent's output.\n"
            f"Case-based confidence: {confidence_text}.\n"
            f"{tools_text}"
        )

    # Situation 2 — normal grounded path.
    outcomes = [c.get("outcome", "unknown") for c in cases if c.get("outcome")]
    outcome_summary = ", ".join(set(outcomes)) if outcomes else "None recorded"

    return (
        f"Found {len(cases)} relevant historical case(s).\n"
        f"Historical outcomes observed: {outcome_summary}.\n"
        f"Case-based confidence: {confidence_text}.\n"
        f"{tools_text}"
    )
