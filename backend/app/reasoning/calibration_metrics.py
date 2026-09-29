"""
MARS Calibration Metrics Engine
================================
Implements research-backed uncertainty calibration metrics based on:
1. Guo et al. (ICML 2017) "On Calibration of Modern Neural Networks"
2. Naeini, Cooper, Hauskrecht (AAAI 2015) "Obtaining Well-Calibrated Probabilities Using Bayesian Binning into Quantiles"
3. Brier, G. W. (1950) "Verification of forecasts expressed in terms of probability"
4. Murphy, A. H. (1973) "A New Vector Partition of the Probability Score"

Provides:
- Expected Calibration Error (ECE)
- Maximum Calibration Error (MCE)
- Brier Score (BS)
- Negative Log-Likelihood (NLL)
- Reliability Diagram Data Generator
"""

import math
from typing import Dict, List, Tuple, Any, Optional


def compute_brier_score(confidences: List[float], outcomes: List[int]) -> float:
    """
    Computes Brier Score: (1 / N) * sum((conf_i - outcome_i)^2)
    Brier (1950). Strictly proper scoring rule for binary probabilities in [0, 1].
    Lower is better (0.0 = perfect deterministic forecast).
    """
    if not confidences or len(confidences) != len(outcomes):
        raise ValueError("Confidences and outcomes must be non-empty and of equal length.")
    
    n = len(confidences)
    total_sq_error = sum((c - y) ** 2 for c, y in zip(confidences, outcomes))
    return round(total_sq_error / n, 6)


def compute_nll(confidences: List[float], outcomes: List[int], eps: float = 1e-12) -> float:
    """
    Computes Negative Log-Likelihood (Binary Cross-Entropy):
    -(1 / N) * sum(y_i * log(p_i) + (1 - y_i) * log(1 - p_i))
    Guo et al. (ICML 2017).
    """
    if not confidences or len(confidences) != len(outcomes):
        raise ValueError("Confidences and outcomes must be non-empty and of equal length.")
    
    n = len(confidences)
    total_loss = 0.0
    for p, y in zip(confidences, outcomes):
        p_clamped = max(eps, min(1.0 - eps, p))
        if y == 1:
            total_loss -= math.log(p_clamped)
        else:
            total_loss -= math.log(1.0 - p_clamped)
    return round(total_loss / n, 6)


def compute_calibration_curve(
    confidences: List[float],
    outcomes: List[int],
    n_bins: int = 10,
    strategy: str = "uniform"
) -> Dict[str, Any]:
    """
    Partitions predictions into M bins and evaluates accuracy vs confidence per bin.
    Reference: Naeini et al. (AAAI 2015), Guo et al. (ICML 2017).
    
    Parameters:
    - confidences: predicted probability scores in [0, 1]
    - outcomes: ground-truth binary labels in {0, 1}
    - n_bins: number of discretization bins (default: 10)
    - strategy: 'uniform' (equal width [0, 0.1), [0.1, 0.2), ...) or 'quantile' (equal sample count)
    
    Returns:
    - Dict containing:
      - 'ece': Expected Calibration Error
      - 'mce': Maximum Calibration Error
      - 'brier_score': Brier Score
      - 'nll': Negative Log-Likelihood
      - 'bins': List of bin dictionaries with bin_edge, avg_conf, avg_acc, count
    """
    if len(confidences) != len(outcomes) or len(confidences) == 0:
        raise ValueError("Inputs must have identical non-zero length.")
    
    n = len(confidences)
    
    # Define bin thresholds
    if strategy == "uniform":
        bin_edges = [i / n_bins for i in range(n_bins + 1)]
    elif strategy == "quantile":
        sorted_conf = sorted(confidences)
        bin_edges = [sorted_conf[int(i * (n - 1) / n_bins)] for i in range(n_bins)]
        bin_edges.append(1.0001)
    else:
        raise ValueError(f"Unknown binning strategy: {strategy}")

    bins_data = []
    ece = 0.0
    mce = 0.0
    
    for i in range(n_bins):
        low = bin_edges[i]
        high = bin_edges[i + 1]
        
        # Collect samples belonging to bin [low, high) (inclusive of 1.0 for the last bin)
        bin_indices = [
            idx for idx, c in enumerate(confidences)
            if (low <= c < high) or (i == n_bins - 1 and low <= c <= high)
        ]
        
        count = len(bin_indices)
        if count > 0:
            bin_conf = sum(confidences[idx] for idx in bin_indices) / count
            bin_acc = sum(outcomes[idx] for idx in bin_indices) / count
            abs_diff = abs(bin_acc - bin_conf)
            
            ece += (count / n) * abs_diff
            if abs_diff > mce:
                mce = abs_diff
        else:
            bin_conf = (low + high) / 2.0
            bin_acc = 0.0
            abs_diff = 0.0

        bins_data.append({
            "bin_index": i,
            "bin_lower": round(low, 3),
            "bin_upper": round(high, 3),
            "sample_count": count,
            "bin_confidence": round(bin_conf, 4),
            "bin_accuracy": round(bin_acc, 4),
            "calibration_gap": round(bin_acc - bin_conf, 4)
        })

    brier = compute_brier_score(confidences, outcomes)
    nll = compute_nll(confidences, outcomes)

    return {
        "ece": round(ece, 6),
        "mce": round(mce, 6),
        "brier_score": brier,
        "nll": nll,
        "total_samples": n,
        "n_bins": n_bins,
        "strategy": strategy,
        "bins": bins_data
    }
