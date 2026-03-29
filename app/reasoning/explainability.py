from typing import List


def generate_explanation(cases: List[dict], confidence: float) -> str:
    """
    Generate a human-readable explanation of the retrieval and confidence result.

    Args:
        cases:      List of retrieved similar cases.
        confidence: The computed confidence score (0–1).

    Returns:
        A formatted explanation string.
    """
    if not cases:
        return (
            "No similar historical cases were found.\n"
            f"Final confidence: {confidence:.2f} (low — based on model reasoning only)."
        )

    outcomes = [c.get("outcome", "unknown") for c in cases]
    outcome_summary = ", ".join(set(outcomes))

    return (
        f"Found {len(cases)} similar historical case(s).\n"
        f"Historical outcomes observed: {outcome_summary}.\n"
        f"Final confidence score: {confidence:.2f}."
    )
