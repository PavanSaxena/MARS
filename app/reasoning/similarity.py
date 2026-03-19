def compute_similarity(cases):

    scores = []

    for case in cases:
        scores.append(1 - case["distance"])

    return sum(scores) / len(scores)