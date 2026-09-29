"""
MARS Statistical Significance & Inter-Annotator Agreement Engine
================================================================
Implements rigorous statistical hypothesis testing and human-expert agreement metrics based on:
1. Fleiss, J. L. (1971) "Measuring nominal scale agreement among many raters"
2. Efron & Tibshirani (1993) "An Introduction to the Bootstrap"
3. Koehn, P. (EMNLP 2004) "Statistical Significance Tests for Machine Translation Evaluation"
4. Dror et al. (ACL 2018) "The Hitchhiker's Guide to Testing Statistical Significance in Natural Language Processing"

Provides:
- Fleiss' Kappa (multi-rater inter-annotator reliability)
- Paired Non-Parametric Bootstrap Test (empirical p-value & 95% CI)
- Permutation / Randomization Test
"""

import math
import random
from typing import Dict, List, Tuple, Any, Optional


def compute_fleiss_kappa(ratings_matrix: List[List[int]]) -> Dict[str, Any]:
    """
    Computes Fleiss' Kappa for inter-rater reliability across N subjects and k categories.
    ratings_matrix: N x k table where cell (i, j) is the number of raters who assigned subject i to category j.
    All rows must sum to n (fixed number of raters per subject).
    
    Returns:
    - Dict with 'kappa', 'observed_agreement', 'expected_agreement', and 'interpretation'.
    """
    N = len(ratings_matrix)
    if N == 0:
        raise ValueError("Ratings matrix cannot be empty.")
    
    k = len(ratings_matrix[0])
    n = sum(ratings_matrix[0])
    
    if n <= 1:
        raise ValueError("Must have at least 2 raters per subject.")
    
    # Verify row sums
    for row in ratings_matrix:
        if sum(row) != n:
            raise ValueError(f"Inconsistent number of raters across rows: expected {n}, got {sum(row)}")

    # 1. Compute p_j (proportion of all assignments to category j)
    total_ratings = N * n
    p_j = [sum(ratings_matrix[i][j] for i in range(N)) / total_ratings for j in range(k)]

    # 2. Compute P_i (extent to which raters agree for subject i)
    P_i = []
    for i in range(N):
        row_sum_sq = sum(ratings_matrix[i][j] ** 2 for j in range(k))
        pi = (row_sum_sq - n) / (n * (n - 1))
        P_i.append(pi)

    # 3. Compute mean observed agreement P_bar and expected agreement P_e_bar
    P_bar = sum(P_i) / N
    P_e_bar = sum(pj ** 2 for pj in p_j)

    # 4. Compute Fleiss' Kappa
    if math.isclose(1.0, P_e_bar):
        kappa = 1.0
    else:
        kappa = (P_bar - P_e_bar) / (1.0 - P_e_bar)

    kappa = round(kappa, 4)

    # Landis & Koch (1977) interpretation
    if kappa < 0.0:
        interpretation = "Poor agreement (less than chance)"
    elif kappa <= 0.20:
        interpretation = "Slight agreement"
    elif kappa <= 0.40:
        interpretation = "Fair agreement"
    elif kappa <= 0.60:
        interpretation = "Moderate agreement"
    elif kappa <= 0.80:
        interpretation = "Substantial agreement"
    else:
        interpretation = "Almost perfect agreement"

    return {
        "kappa": kappa,
        "observed_agreement_P_bar": round(P_bar, 4),
        "expected_agreement_P_e_bar": round(P_e_bar, 4),
        "raters_per_subject": n,
        "total_subjects": N,
        "total_categories": k,
        "interpretation": interpretation
    }


def paired_bootstrap_test(
    baseline_scores: List[float],
    system_scores: List[float],
    n_bootstraps: int = 2000,
    alpha: float = 0.05,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Computes Non-Parametric Paired Bootstrap Test based on Koehn (EMNLP 2004).
    Tests null hypothesis H0: mean(system) <= mean(baseline) vs H1: mean(system) > mean(baseline).
    
    Returns:
    - empirical p-value
    - observed score difference
    - 95% bootstrap confidence interval [ci_lower, ci_upper]
    - statistical significance flag
    """
    if len(baseline_scores) != len(system_scores) or len(baseline_scores) == 0:
        raise ValueError("Baseline and system scores must have identical non-zero length.")

    n = len(baseline_scores)
    observed_diff = sum(s - b for s, b in zip(system_scores, baseline_scores)) / n

    rng = random.Random(seed)
    bootstrap_diffs = []
    wins = 0

    for _ in range(n_bootstraps):
        sample_indices = [rng.randint(0, n - 1) for _ in range(n)]
        b_mean = sum(baseline_scores[i] for i in sample_indices) / n
        s_mean = sum(system_scores[i] for i in sample_indices) / n
        diff = s_mean - b_mean
        bootstrap_diffs.append(diff)
        if diff <= 0.0:
            wins += 1

    # Empirical one-sided p-value
    p_value = round(wins / n_bootstraps, 5)

    # 95% Confidence Interval (percentile bootstrap)
    sorted_diffs = sorted(bootstrap_diffs)
    low_idx = int((alpha / 2.0) * n_bootstraps)
    high_idx = int((1.0 - alpha / 2.0) * n_bootstraps)

    ci_lower = round(sorted_diffs[low_idx], 4)
    ci_upper = round(sorted_diffs[high_idx], 4)

    is_significant = (p_value < alpha) and (ci_lower > 0.0)

    return {
        "observed_mean_baseline": round(sum(baseline_scores) / n, 4),
        "observed_mean_system": round(sum(system_scores) / n, 4),
        "observed_difference": round(observed_diff, 4),
        "bootstrap_iterations": n_bootstraps,
        "empirical_p_value": p_value,
        "confidence_interval_95": (ci_lower, ci_upper),
        "statistically_significant": is_significant,
        "significance_level": alpha,
        "summary": (
            f"Statistically significant improvement (p = {p_value:.4f} < {alpha}, "
            f"95% CI: [{ci_lower:+.4f}, {ci_upper:+.4f}])"
            if is_significant else
            f"Difference not statistically significant (p = {p_value:.4f} >= {alpha})"
        )
    }


if __name__ == "__main__":
    # Test Kappa with simulated 5 raters on 10 strategic dilemma evaluations (3 categories: Accept, Revise, Reject)
    simulated_ratings = [
        [4, 1, 0],
        [5, 0, 0],
        [0, 5, 0],
        [0, 1, 4],
        [3, 2, 0],
        [0, 4, 1],
        [4, 1, 0],
        [5, 0, 0],
        [1, 3, 1],
        [0, 0, 5]
    ]
    kappa_res = compute_fleiss_kappa(simulated_ratings)
    print("Fleiss Kappa:", kappa_res)

    # Test Bootstrap with 40 paired evaluations
    b_scores = [2.4, 2.5, 2.0, 3.1, 2.2, 2.8, 1.9, 2.3, 2.7, 2.4] * 4
    s_scores = [3.2, 3.4, 2.8, 3.5, 3.1, 3.4, 2.7, 3.0, 3.3, 3.2] * 4
    boot_res = paired_bootstrap_test(b_scores, s_scores)
    print("Paired Bootstrap:", boot_res)
