from typing import List, Optional


def generate_explanation(
    cases: List[dict],
    confidence: Optional[float],
    tools_used: Optional[List[str]] = None,
    reported_confidence: Optional[float] = None,
    weight_rationale: Optional[str] = None,
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
        if isinstance(confidence, (int, float))
        else "0.00"
    )
    tools_text = (
        f"Tools consulted: {', '.join(tools_used)}."
        if tools_used
        else "No tools were called."
    )
    weights_line = f"\nWeight Allocation: {weight_rationale}" if weight_rationale else ""

    # Situation 1 — the retriever found nothing at all or confidence is 0.
    if not cases or (confidence is not None and confidence <= 0.0):
        return (
            "No relevant historical cases found in the dataset for this query.\n"
            f"Case-based confidence: {confidence_text}.\n"
            f"{tools_text}{weights_line}"
        )

    # Situation 2 — normal grounded path.
    outcomes = [c.get("outcome", "unknown") for c in cases if c.get("outcome")]
    outcome_summary = ", ".join(set(outcomes)) if outcomes else "None recorded"

    return (
        f"Found {len(cases)} relevant historical case(s).\n"
        f"Historical outcomes observed: {outcome_summary}.\n"
        f"Case-based confidence: {confidence_text}.\n"
        f"{tools_text}{weights_line}"
    )

