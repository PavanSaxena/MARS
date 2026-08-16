from typing import Optional


def calculate_confidence(
    similarity: Optional[float] = None,
    recency: Optional[float] = None,
    past_success: Optional[float] = None,
) -> Optional[float]:
    """
    PLACEHOLDER — multi-factor confidence scoring.

    Target formula (per capstone report §8.2): a weighted combination of
        - similarity:    average vector similarity of retrieved cases (0-1)
        - recency:       how recent the retrieved cases are (0-1)
        - past_success:  historical success rate of retrieved cases (0-1)
    i.e. confidence = w1*similarity + w2*recency + w3*past_success

    The weights (w1, w2, w3) and the exact recency decay function are still
    being researched and are NOT finalized. Do not treat this as a real score
    yet — it intentionally returns None until the formula is decided.

    Once finalized, this should:
      1. Compute recency from each case's `quarter` metadata field.
      2. Compute past_success via app.reasoning.outcome_analysis.analyze_outcomes().
      3. Compute similarity via app.reasoning.similarity.compute_similarity().
      4. Combine with the agreed-upon weights and return a float in [0, 1].
    """
    return None
