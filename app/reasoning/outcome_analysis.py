def analyze_outcomes(cases):

    success = 0

    for case in cases:
        if case["outcome"] == "success":
            success += 1

    return success / len(cases)