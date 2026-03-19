def calculate_confidence(similarity, outcome, metadata):

    return (
        0.5 * similarity +
        0.3 * outcome +
        0.2 * metadata
    )