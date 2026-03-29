from typing import List


def analyze_outcomes(cases: List[dict]) -> float:
    """
    Calculate the success rate from a list of retrieved cases.

    Returns a float in [0, 1], or 0.0 if no cases are provided.
    """
    if not cases:
        return 0.0

    success = sum(1 for case in cases if case.get("outcome") == "success")
    return success / len(cases)
