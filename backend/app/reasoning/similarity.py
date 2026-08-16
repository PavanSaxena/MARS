from typing import List


def compute_similarity(cases: List[dict]) -> float:
    """
    Compute the average similarity score across retrieved cases.
    Similarity = 1 - distance (cosine distance from pgvector, in [0, 1] for normalized embeddings).

    Returns a float in [0, 1], or 0.0 if no cases are provided.
    """
    if not cases:
        return 0.0

    scores = [1 - case.get("distance", 1.0) for case in cases]
    return sum(scores) / len(scores)
