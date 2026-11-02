"""MARS Case-Based Reasoning and Confidence Stack."""

# NOTE: aggregator_agent is intentionally NOT re-exported here to avoid a
# circular import:  agents.common → reasoning.__init__ → aggregator → agents.common (get_llm).
# Import it directly:  from app.reasoning.aggregator import aggregator_agent
from app.reasoning.calibration_metrics import compute_calibration_curve, compute_nll
from app.reasoning.confidence import (
    calculate_confidence,
    compute_recency,
    compute_similarity,
    generate_explanation,
    optimize_weights_from_outcomes,
)
from app.reasoning.conformal_predictor import ConformalRiskController
from app.reasoning.semantic_router import route_departments_semantically
from app.reasoning.weight_registry import WeightRegistry, weight_registry

__all__ = [
    "ConformalRiskController",
    "WeightRegistry",
    "calculate_confidence",
    "compute_calibration_curve",
    "compute_nll",
    "compute_recency",
    "compute_similarity",
    "generate_explanation",
    "optimize_weights_from_outcomes",
    "route_departments_semantically",
    "weight_registry",
]
