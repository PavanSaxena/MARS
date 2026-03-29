def calculate_confidence(similarity: float, outcome: float, metadata: float) -> float:
    """
    Compute a weighted confidence score.

    Args:
        similarity: Average vector similarity of retrieved cases (0–1).
        outcome:    Historical success rate of retrieved cases (0–1).
        metadata:   Metadata quality/relevance score (0–1).

    Returns:
        Weighted confidence score in [0, 1].
    """
    return 0.5 * similarity + 0.3 * outcome + 0.2 * metadata
