import datetime
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from app.reasoning.outcome_analysis import analyze_outcomes
from app.reasoning.similarity import compute_similarity

# Default multi-factor weights (per CBR decision support specification):
# - 45% Case Relevance (vector similarity)
# - 35% Historical Precedent Success Rate (empirical outcome utility)
# - 20% Temporal Recency (decayed by quarterly distance)
DEFAULT_WEIGHTS: Tuple[float, float, float] = (0.45, 0.20, 0.35)

# Domain-tailored weights (w_similarity, w_recency, w_past_success):
DEPARTMENT_WEIGHTS: Dict[str, Tuple[float, float, float]] = {
    # Legal is heavily sensitive to recent rulings and regulatory enforcement (DMA, DOJ, compliance)
    "legal": (0.35, 0.40, 0.25),
    # R&D focuses heavily on architectural/hardware similarity & feasibility
    "rd": (0.55, 0.20, 0.25),
    # Finance demands strong empirical success rates and ROI margin precedents
    "finance": (0.40, 0.15, 0.45),
    # Operations balances supply chain similarity, supplier agreement recency, and execution success
    "operations": (0.45, 0.25, 0.30),
}

# Action-type specific weight adjustments:
ACTION_TYPE_WEIGHTS: Dict[str, Tuple[float, float, float]] = {
    # High-risk capital/operational shifts demand proven success rate
    "expand": (0.40, 0.15, 0.45),
    "reduce": (0.40, 0.20, 0.40),
    "terminate": (0.35, 0.20, 0.45),
    # Exploratory actions prioritize technical/legal similarity over past success
    "investigate": (0.50, 0.30, 0.20),
    "defer": (0.40, 0.40, 0.20),
    "approve": (0.40, 0.20, 0.40),
    "revise": (0.50, 0.25, 0.25),
}

# Exponential decay constant per quarter (~5% decay per elapsed quarter)
DEFAULT_RECENCY_LAMBDA: float = 0.05


def optimize_weights_from_outcomes(
    training_cases: List[Dict[str, Any]],
    default_weights: Tuple[float, float, float] = DEFAULT_WEIGHTS,
) -> Tuple[float, float, float]:
    """
    Self-optimizing empirical calibration engine:
    Computes optimal weight simplex (w_sim, w_rec, w_succ) by maximizing correlation
    and log-likelihood against observed binary success outcomes in historical training cases.

    Uses bounded gradient optimization over the weight simplex (w1 + w2 + w3 = 1, w_i >= 0.1).
    """
    if not training_cases or len(training_cases) < 5:
        return default_weights

    # Extract feature matrices: [sim, rec, past_succ] and binary outcome labels [1/0]
    features = []
    labels = []

    for c in training_cases:
        meta = c.get("metadata") or {}
        sim = float(meta.get("similarity") or 0.5)
        q_idx = parse_quarter_to_index(meta.get("quarter"))
        rec = 0.8 if q_idx else 0.5
        outcome_str = str(meta.get("outcome") or c.get("outcome") or "").lower()
        is_succ = 1.0 if any(k in outcome_str for k in ("success", "achieved", "growth", "approved", "cleared")) else 0.0

        features.append((sim, rec, is_succ))
        labels.append(is_succ)

    # Grid search / Simplex optimization for optimal weights
    best_loss = float("inf")
    best_w = default_weights

    # Test candidate simplex points in steps of 0.05
    for w1_i in range(2, 15):
        w1 = w1_i * 0.05
        for w2_i in range(2, 15):
            w2 = w2_i * 0.05
            w3 = round(1.0 - w1 - w2, 4)
            if w3 < 0.1:
                continue

            # Compute Binary Cross-Entropy Loss on ground truth outcome alignment
            loss = 0.0
            for (sim, rec, succ), label in zip(features, labels):
                pred = (w1 * sim) + (w2 * rec) + (w3 * succ)
                pred = max(1e-5, min(1.0 - 1e-5, pred))
                if label == 1.0:
                    loss -= math.log(pred)
                else:
                    loss -= math.log(1.0 - pred)

            if loss < best_loss:
                best_loss = loss
                best_w = (round(w1, 3), round(w2, 3), round(w3, 3))

    return best_w


def parse_quarter_to_index(quarter_str: Any) -> Optional[int]:
    """
    Parse a quarter or date string into a continuous integer quarter index:
    index = year * 4 + (quarter_number - 1).

    Handles formats:
      - '2023Q1', '2023-Q1', '2023_Q1', 'Q1 2023', 'Q1_2023'
      - '2023-03-15' (ISO date string)
      - datetime.date / datetime.datetime objects
    """
    if not quarter_str:
        return None

    if isinstance(quarter_str, (datetime.date, datetime.datetime)):
        year = quarter_str.year
        quarter_num = (quarter_str.month - 1) // 3 + 1
        return year * 4 + (quarter_num - 1)

    s = str(quarter_str).strip()

    # Pattern: 2023Q1, 2023-Q1, 2023_Q1
    match = re.search(r"(\d{4})[\s\-_]*[qQ](\d)", s)
    if match:
        year = int(match.group(1))
        q_num = int(match.group(2))
        if 1 <= q_num <= 4:
            return year * 4 + (q_num - 1)

    # Pattern: Q1 2023, Q1-2023, Q1_2023
    match = re.search(r"[qQ](\d)[\s\-_]*(\d{4})", s)
    if match:
        q_num = int(match.group(1))
        year = int(match.group(2))
        if 1 <= q_num <= 4:
            return year * 4 + (q_num - 1)

    # Pattern: ISO date YYYY-MM-DD
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if 1 <= month <= 12:
            quarter_num = (month - 1) // 3 + 1
            return year * 4 + (quarter_num - 1)

    # Pattern: Just a 4-digit year e.g. "2023"
    match = re.search(r"\b(20\d{2}|19\d{2})\b", s)
    if match:
        year = int(match.group(1))
        return year * 4  # Default to Q1

    return None


def compute_recency(
    cases: List[Dict[str, Any]],
    reference_quarter: Optional[str] = None,
    decay_lambda: float = DEFAULT_RECENCY_LAMBDA,
) -> float:
    """
    Compute average recency score across retrieved cases using exponential decay:
      recency_case = exp(-lambda * delta_quarters)

    delta_quarters = max(0, ref_index - case_index)
    Returns a float in [0.0, 1.0], or 0.5 if quarters are unrecognized.
    """
    if not cases:
        return 0.0

    # Determine reference quarter index (default to current date or max observed quarter)
    ref_idx = parse_quarter_to_index(reference_quarter) if reference_quarter else None
    if ref_idx is None:
        # If no explicit reference quarter, find max quarter in cases or use current date
        case_indices = [
            parse_quarter_to_index(
                (c.get("metadata") or {}).get("quarter")
                or c.get("quarter")
                or (c.get("metadata") or {}).get("decision_date")
            )
            for c in cases
        ]
        valid_indices = [idx for idx in case_indices if idx is not None]
        if valid_indices:
            ref_idx = max(valid_indices)
        else:
            now = datetime.date.today()
            ref_idx = now.year * 4 + (now.month - 1) // 3

    recency_scores: List[float] = []
    for c in cases:
        meta = c.get("metadata") or {}
        q_val = meta.get("quarter") or c.get("quarter") or meta.get("decision_date") or c.get("decision_date")
        idx = parse_quarter_to_index(q_val)
        if idx is not None:
            delta = max(0, ref_idx - idx)
            score = math.exp(-decay_lambda * delta)
            recency_scores.append(score)
        else:
            # Neutral default if no date metadata found
            recency_scores.append(0.5)

    return sum(recency_scores) / len(recency_scores) if recency_scores else 0.0


from app.reasoning.weight_registry import weight_registry
from app.reasoning.dynamic_weighting import dynamic_weight_engine, DynamicWeightResult


def calculate_confidence(
    similarity: Optional[float] = None,
    recency: Optional[float] = None,
    past_success: Optional[float] = None,
    cases: Optional[List[Dict[str, Any]]] = None,
    department: Optional[str] = None,
    action_type: Optional[str] = None,
    weights: Optional[Tuple[float, float, float]] = None,
    query: Optional[str] = None,
) -> float:
    """
    Multi-factor case-based confidence scoring for strategic decision advisory.

    Formula:
        Confidence = w1 * Similarity + w2 * Recency + w3 * PastSuccess

    Where:
        - Similarity:   average cosine similarity of retrieved cases in [0, 1]
        - Recency:      decayed temporal freshness of retrieved cases in [0, 1]
        - PastSuccess:  historical empirical success rate of retrieved cases in [0, 1]

    Dynamic Query-Adaptive Weight Selection:
        - If `weights` is explicitly provided, it is used as an override.
        - If `query` is provided, dynamic weights (w1, w2, w3) are computed on the fly
          conditioned on query intent (temporal urgency, risk stakes, precedent specificity)
          and the agent's domain mandate.
        - Otherwise, falls back to persistent calibrated domain registry weights.

    Args:
        similarity:    Precomputed average similarity (or computed from cases if None).
        recency:       Precomputed average recency (or computed from cases if None).
        past_success:  Precomputed past success rate (or computed from cases if None).
        cases:         Optional list of retrieved case dictionaries.
        department:    Optional department identifier to select domain weights.
        action_type:   Optional action type identifier to select action weights.
        weights:       Explicit (w_similarity, w_recency, w_past_success) override tuple.
        query:         Optional user query string for dynamic query-conditioned weighting.

    Returns:
        Calibrated confidence float in [0.0, 1.0], rounded to 4 decimal places.
    """
    conf, _ = calculate_confidence_with_details(
        similarity=similarity,
        recency=recency,
        past_success=past_success,
        cases=cases,
        department=department,
        action_type=action_type,
        weights=weights,
        query=query,
    )
    return conf


def calculate_confidence_with_details(
    similarity: Optional[float] = None,
    recency: Optional[float] = None,
    past_success: Optional[float] = None,
    cases: Optional[List[Dict[str, Any]]] = None,
    department: Optional[str] = None,
    action_type: Optional[str] = None,
    weights: Optional[Tuple[float, float, float]] = None,
    query: Optional[str] = None,
) -> Tuple[float, Dict[str, Any]]:
    """
    Computes calibrated confidence score alongside detailed dynamic weighting telemetry.
    """
    dept_key = (department or "").lower().strip()
    act_key = (action_type or "").lower().strip()

    if not dept_key and cases:
        dept_key = str((cases[0].get("metadata") or {}).get("department", "")).lower().strip()
    if not act_key and cases:
        act_key = str((cases[0].get("metadata") or {}).get("risk_level", "")).lower().strip()

    weight_info: Dict[str, Any] = {}

    # 1. Determine dynamic weights profile
    if weights:
        selected_weights = weights
        weight_info = {
            "mode": "explicit_override",
            "weights": list(selected_weights),
            "rationale": "Explicit weight override provided.",
        }
    elif query and query.strip():
        dyn_res: DynamicWeightResult = dynamic_weight_engine.compute_weights(
            query=query, department=dept_key, action_type=act_key
        )
        selected_weights = dyn_res.weights
        weight_info = {
            "mode": "query_adaptive_dynamic",
            "weights": list(selected_weights),
            "w_similarity": dyn_res.w_similarity,
            "w_recency": dyn_res.w_recency,
            "w_past_success": dyn_res.w_past_success,
            "query_signals": dyn_res.query_signals,
            "rationale": dyn_res.rationale,
        }
    else:
        selected_weights = weight_registry.get_weights(department=dept_key, action_type=act_key)
        weight_info = {
            "mode": "registry_prior",
            "weights": list(selected_weights),
            "rationale": f"Persistent calibrated registry prior for department '{dept_key or 'default'}'.",
        }

    w1, w2, w3 = selected_weights
    total_w = w1 + w2 + w3
    if total_w <= 0:
        w1, w2, w3 = DEFAULT_WEIGHTS
        total_w = 1.0
    w1, w2, w3 = w1 / total_w, w2 / total_w, w3 / total_w

    if cases is not None:
        if not cases:
            return 0.0, weight_info
        if similarity is None:
            similarity = compute_similarity(cases)
        if recency is None:
            recency = compute_recency(cases)
        if past_success is None:
            past_success = analyze_outcomes(cases)

    # Defaults if not provided and no cases
    sim_score = max(0.0, min(1.0, float(similarity if similarity is not None else 0.0)))
    rec_score = max(0.0, min(1.0, float(recency if recency is not None else 0.0)))
    succ_score = max(0.0, min(1.0, float(past_success if past_success is not None else 0.0)))

    # If no similarity exists (zero retrieval), confidence is strictly 0.0
    if sim_score <= 0.0:
        return 0.0, weight_info

    composite = (w1 * sim_score) + (w2 * rec_score) + (w3 * succ_score)
    final_conf = round(max(0.0, min(1.0, composite)), 4)
    return final_conf, weight_info


