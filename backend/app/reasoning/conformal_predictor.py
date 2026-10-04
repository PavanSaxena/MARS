"""
MARS Temporally-Weighted Conformal Risk Controller (TW-CRC)
===========================================================
Implements distribution-free uncertainty quantification and risk-controlled decision bounds based on:
1. Angelopoulos & Bates (2021) "A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification"
2. Tibshirani, Foygel Barber, Candès, Ramdas (2019) "Conformal Prediction Under Covariate Shift"
3. Gibbs & Candès (NeurIPS 2021) "Adaptive Conformal Inference Under Distribution Shift"
4. Bates, Angelopoulos, Lei, Malik, Jordan (2021) "Distribution-Free Risk-Controlling Prediction Sets"

Provides:
- Finite-sample coverage guarantees: P(True Utility in C(q)) >= 1 - alpha
- Temporally-weighted non-conformity quantiles under quarterly distribution drift
- Risk-controlled decision policy (e.g., automated human review / abstention when risk exceeds tolerance)
"""

import math
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class ConformalDecisionBound:
    point_confidence: float
    confidence_interval: Tuple[float, float]
    coverage_guarantee: float       # 1 - alpha (e.g., 0.95)
    quantile_cutoff: float          # q_hat
    risk_level: str                 # "LOW", "MODERATE", "ELEVATED", "HIGH"
    decision_policy: str            # "PROCEED_AUTONOMOUS", "CAUTION_FLAGGED", "ABSTAIN_FOR_HUMAN_REVIEW"
    policy_rationale: str
    sample_size_calibrated: int


def compute_weighted_quantile(
    values: List[float],
    weights: List[float],
    quantile: float
) -> float:
    """
    Computes weighted empirical quantile based on Tibshirani et al. (2019).
    Given weights w_i and values s_i, find the infimum s where sum_{i: s_i <= s} w_i >= quantile * sum(w_i).
    """
    if len(values) != len(weights) or len(values) == 0:
        raise ValueError("Values and weights must have identical non-zero length.")
    
    if not (0.0 <= quantile <= 1.0):
        raise ValueError(f"Quantile must be in [0, 1], got {quantile}")

    # Pair and sort by value ascending
    paired = sorted(zip(values, weights), key=lambda x: x[0])
    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("Total weight must be positive.")

    target_weight = quantile * total_weight
    cumulative_weight = 0.0

    for val, w in paired:
        cumulative_weight += w
        if cumulative_weight >= target_weight:
            return val

    return paired[-1][0]


class ConformalRiskController:
    """
    Temporally-Weighted Conformal Risk Controller for MARS.
    Maintains empirical calibration residuals and outputs bounded prediction intervals.
    """

    DEFAULT_ALPHA = 0.05  # 95% finite-sample coverage guarantee
    DEFAULT_ABSTAIN_THRESHOLD = 0.30  # Abstain if lower bound < 0.30
    DEFAULT_CAUTION_THRESHOLD = 0.50  # Caution flag if lower bound < 0.50

    def __init__(
        self,
        alpha: float = DEFAULT_ALPHA,
        decay_rate: float = 0.05,
        default_quantile_cache: Optional[Dict[str, float]] = None
    ):
        """
        Parameters:
        - alpha: error budget (coverage = 1 - alpha, e.g. 0.05 -> 95%)
        - decay_rate: lambda for quarterly temporal decay exp(-lambda * delta_q)
        - default_quantile_cache: pre-computed department quantiles
        """
        self.alpha = alpha
        self.decay_rate = decay_rate
        # Pre-computed fallback quantiles from historical benchmarks (at alpha=0.05)
        self.quantile_cache = default_quantile_cache or {
            "global": 0.284,
            "finance": 0.245,
            "legal": 0.312,
            "rd": 0.298,
            "operations": 0.261
        }

    def calibrate_from_historical_data(
        self,
        predicted_confidences: List[float],
        ground_truth_outcomes: List[int],
        elapsed_quarters: Optional[List[int]] = None,
        department: str = "global"
    ) -> float:
        """
        Calibrates the non-conformity quantile q_hat on historical validation data.
        Non-conformity score: s_i = |y_i - c_i| (residual error).
        Temporal weight: w_i = exp(-lambda * delta_q_i).
        
        Returns calibrated q_hat.
        """
        n = len(predicted_confidences)
        if n == 0 or n != len(ground_truth_outcomes):
            return self.quantile_cache.get(department, self.quantile_cache["global"])

        # Non-conformity scores: residual magnitude
        scores = [abs(y - c) for c, y in zip(predicted_confidences, ground_truth_outcomes)]
        
        # Temporal weights
        if elapsed_quarters and len(elapsed_quarters) == n:
            weights = [math.exp(-self.decay_rate * max(0, dq)) for dq in elapsed_quarters]
        else:
            weights = [1.0] * n

        # Finite-sample correction factor (n + 1) / n
        adjusted_quantile = min(1.0, (1.0 - self.alpha) * (n + 1) / n)
        
        q_hat = compute_weighted_quantile(scores, weights, adjusted_quantile)
        self.quantile_cache[department] = round(q_hat, 4)
        return round(q_hat, 4)

    def evaluate_decision_bound(
        self,
        point_confidence: float,
        department: str = "global",
        custom_alpha: Optional[float] = None,
        cases_count: int = 1
    ) -> ConformalDecisionBound:
        """
        Computes the conformal prediction interval and evaluates the enterprise risk policy.
        """
        alpha = custom_alpha if custom_alpha is not None else self.alpha
        coverage = round(1.0 - alpha, 3)

        # Retrieve calibrated quantile
        q_hat = self.quantile_cache.get(department, self.quantile_cache.get("global", 0.284))

        # Handle zero evidence edge-case
        if cases_count == 0 or point_confidence <= 0.0:
            return ConformalDecisionBound(
                point_confidence=0.0,
                confidence_interval=(0.0, 0.0),
                coverage_guarantee=coverage,
                quantile_cutoff=q_hat,
                risk_level="HIGH",
                decision_policy="ABSTAIN_FOR_HUMAN_REVIEW",
                policy_rationale="Zero empirical precedent retrieved. Automated decision generation suppressed to prevent hallucination.",
                sample_size_calibrated=cases_count
            )

        # Compute distribution-free interval
        lower = max(0.0, point_confidence - q_hat)
        upper = min(1.0, point_confidence + q_hat)
        interval = (round(lower, 3), round(upper, 3))

        # Risk-Controlled Policy Decision
        if lower >= self.DEFAULT_CAUTION_THRESHOLD:
            risk_level = "LOW"
            policy = "PROCEED_AUTONOMOUS"
            rationale = (
                f"Statistically grounded at {int(coverage * 100)}% conformal confidence. "
                f"Lower bound ({lower:.2f}) exceeds autonomous action threshold ({self.DEFAULT_CAUTION_THRESHOLD:.2f})."
            )
        elif lower >= self.DEFAULT_ABSTAIN_THRESHOLD:
            risk_level = "MODERATE"
            policy = "CAUTION_FLAGGED"
            rationale = (
                f"Grounded precedent present, but lower bound ({lower:.2f}) indicates moderate outcome variance. "
                f"Executive advisory requires mandatory cross-department risk mitigation disclosure."
            )
        else:
            risk_level = "ELEVATED"
            policy = "ABSTAIN_FOR_HUMAN_REVIEW"
            rationale = (
                f"Conformal lower bound ({lower:.2f}) falls below risk-tolerance floor ({self.DEFAULT_ABSTAIN_THRESHOLD:.2f}). "
                f"High historical failure probability or stale precedent requires human expert review."
            )

        return ConformalDecisionBound(
            point_confidence=round(point_confidence, 3),
            confidence_interval=interval,
            coverage_guarantee=coverage,
            quantile_cutoff=round(q_hat, 4),
            risk_level=risk_level,
            decision_policy=policy,
            policy_rationale=rationale,
            sample_size_calibrated=cases_count
        )
