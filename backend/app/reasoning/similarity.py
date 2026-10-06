from typing import List


def compute_similarity(cases: List[dict]) -> float:
    """
    Compute the average similarity score across retrieved cases.
    Similarity = 1 - distance (cosine distance from pgvector, in [0, 1] for normalized embeddings),
    or uses explicit 'similarity' field if provided.

    Returns a float in [0, 1], or 0.0 if no cases are provided.
    """
    if not cases:
        return 0.0

    scores = []
    for case in cases:
        if "similarity" in case and case["similarity"] is not None:
            scores.append(float(case["similarity"]))
        elif "distance" in case and case["distance"] is not None:
            scores.append(1.0 - float(case["distance"]))
        elif "metadata" in case and isinstance(case["metadata"], dict) and "similarity" in case["metadata"]:
            scores.append(float(case["metadata"]["similarity"]))
        else:
            scores.append(1.0 - float(case.get("distance", 1.0)))

    return sum(scores) / len(scores)

