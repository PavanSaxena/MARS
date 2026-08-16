from typing import List, Optional


def generate_explanation(
    cases: List[dict],
    confidence: Optional[float],
    tools_used: Optional[List[str]] = None,
) -> str:
    """
    Generate a human-readable explanation of the retrieval, tool-use, and
    confidence result.

    Args:
        cases:      List of retrieved similar cases.
        confidence: The computed multi-factor confidence score (0-1), or None
                    if it hasn't been computed yet (the scoring formula is
                    still being researched — see app.reasoning.confidence).
        tools_used: Names of any tools the agent called (via the MCP-style
                    tool layer in app.tools) while producing its answer.

    Returns:
        A formatted explanation string.
    """
    confidence_text = (
        f"{confidence:.2f}" if confidence is not None else "not yet available (scoring formula still in progress)"
    )
    tools_text = f"Tools consulted: {', '.join(tools_used)}." if tools_used else "No tools were called."

    if not cases:
        return (
            "No similar historical cases were found.\n"
            f"Case-based confidence: {confidence_text}.\n"
            f"{tools_text}"
        )

    outcomes = [c.get("outcome", "unknown") for c in cases]
    outcome_summary = ", ".join(set(outcomes))

    return (
        f"Found {len(cases)} similar historical case(s).\n"
        f"Historical outcomes observed: {outcome_summary}.\n"
        f"Case-based confidence: {confidence_text}.\n"
        f"{tools_text}"
    )
