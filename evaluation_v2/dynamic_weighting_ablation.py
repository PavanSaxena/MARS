"""Leakage-safe ablation for query-adaptive dynamic confidence weighting.

Compares three confidence policies on the same historical replay cases:

1. static_default: fixed global CBR weights.
2. registry_prior: department/action weights from the existing registry.
3. query_adaptive_dynamic: query-conditioned dynamic weights.

This evaluates the confidence score as an outcome probability proxy. It does
not by itself prove advisory quality; it tells us whether the weighting policy
improves calibration metrics under a temporal information boundary.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from evaluation_v2.dataset import REPO_ROOT, CaseRecord, load_cases, replay_query_text, split_cases, visible_corpus
from evaluation_v2.metrics import calibration_curve
from evaluation_v2.retrieval import BM25Index, tokenize


STATIC_DEFAULT = (0.45, 0.20, 0.35)


def run_dynamic_weighting_ablation(
    *,
    split_name: str = "test",
    max_cases: int | None = None,
    k: int = 10,
    dynamic_gain: float = 0.50,
) -> Dict[str, Any]:
    # Prevent slow network retries when the embedding model is not fully cached.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    from backend.app.reasoning.dynamic_weighting import QueryAdaptiveWeightEngine
    from backend.app.reasoning.weight_registry import weight_registry
    dynamic_weight_engine = QueryAdaptiveWeightEngine(modulation_gain=dynamic_gain)

    all_cases = load_cases()
    splits = split_cases(all_cases)
    targets = splits[split_name]
    if max_cases is not None:
        targets = targets[:max_cases]

    labels = [case.outcome_binary for case in targets]
    predictions: Dict[str, List[float]] = {
        "static_default": [],
        "registry_prior": [],
        "query_adaptive_dynamic": [],
    }
    per_case = []

    for target in targets:
        query = replay_query_text(target)
        corpus = visible_corpus(
            all_cases,
            as_of_date=target.decision_date,
            target_case_id=target.case_id,
            include_visible_outcomes=True,
        )
        retrieved_pairs = BM25Index(corpus).retrieve(query, k=k)
        retrieved_docs = [doc for doc, _ in retrieved_pairs]
        features = _feature_tuple(target, query, retrieved_docs)

        registry_weights = weight_registry.get_weights(
            department=_dept_key(target.department),
            action_type=target.action_type,
        )
        dynamic_result = dynamic_weight_engine.compute_weights(
            query=query,
            department=_dept_key(target.department),
            action_type=target.action_type,
        )
        policies = {
            "static_default": STATIC_DEFAULT,
            "registry_prior": registry_weights,
            "query_adaptive_dynamic": dynamic_result.weights,
        }
        case_predictions = {
            name: _weighted_confidence(features, weights)
            for name, weights in policies.items()
        }
        for name, pred in case_predictions.items():
            predictions[name].append(pred)

        per_case.append(
            {
                "case_id": target.case_id,
                "decision_date": target.decision_date,
                "department": target.department,
                "action_type": target.action_type,
                "label": target.outcome_binary,
                "features": {
                    "similarity": round(features[0], 6),
                    "recency": round(features[1], 6),
                    "past_success": round(features[2], 6),
                    "visible_outcome_count": features[3],
                },
                "weights": {
                    "static_default": list(STATIC_DEFAULT),
                    "registry_prior": [round(x, 6) for x in registry_weights],
                    "query_adaptive_dynamic": list(dynamic_result.weights),
                },
                "dynamic_query_signals": dynamic_result.query_signals,
                "dynamic_rationale": dynamic_result.rationale,
                "predictions": {name: round(pred, 6) for name, pred in case_predictions.items()},
                "retrieved_ids": [doc["case_id"] for doc in retrieved_docs],
            }
        )

    metrics = {
        name: calibration_curve(preds, labels)
        for name, preds in predictions.items()
    }

    return {
        "protocol": "evaluation_v2 query-adaptive dynamic weighting ablation",
        "split": split_name,
        "cases": len(targets),
        "k": k,
        "dynamic_gain": dynamic_gain,
        "policies": {
            "static_default": "Fixed global weights [0.45, 0.20, 0.35].",
            "registry_prior": "Existing department/action registry weights.",
            "query_adaptive_dynamic": "Runtime query-conditioned dynamic weights.",
        },
        "metrics": metrics,
        "winner_by_brier": min(metrics, key=lambda name: metrics[name]["brier"]) if metrics else None,
        "winner_by_nll": min(metrics, key=lambda name: metrics[name]["nll"]) if metrics else None,
        "interpretation_guardrail": (
            "This ablation evaluates confidence calibration only. Advisory quality still requires "
            "decision replay scoring and human/expert evaluation."
        ),
        "per_case": per_case,
    }


def _feature_tuple(target: CaseRecord, query: str, docs: Sequence[Dict[str, Any]]) -> Tuple[float, float, float, int]:
    if not docs:
        return (0.0, 0.0, 0.5, 0)

    similarity = _mean(_lexical_similarity(query, doc) for doc in docs)
    recency = _mean(_recency_score(target, doc) for doc in docs)
    visible = [
        doc for doc in docs
        if doc.get("outcome_visible") and doc.get("outcome_label") in {"success", "failure"}
    ]
    if visible:
        past_success = sum(1.0 for doc in visible if doc.get("outcome_label") == "success") / len(visible)
    else:
        past_success = 0.5
    return (
        _clamp01(similarity),
        _clamp01(recency),
        _clamp01(past_success),
        len(visible),
    )


def _lexical_similarity(query: str, doc: Dict[str, Any]) -> float:
    q_tokens = set(tokenize(query))
    d_tokens = set(tokenize(str(doc.get("decision_text") or "")))
    if not q_tokens or not d_tokens:
        return 0.0
    # Recall-oriented overlap: how much of the query is explained by this precedent.
    return len(q_tokens & d_tokens) / len(q_tokens)


def _recency_score(target: CaseRecord, doc: Dict[str, Any], decay_lambda: float = 0.05) -> float:
    try:
        elapsed_quarters = max(
            0.0,
            (target.decision_dt - target.decision_dt.fromisoformat(str(doc["decision_date"]))).days / 91.25,
        )
    except Exception:
        return 0.5
    return math.exp(-decay_lambda * elapsed_quarters)


def _weighted_confidence(features: Tuple[float, float, float, int], weights: Tuple[float, float, float]) -> float:
    sim, rec, succ, _ = features
    if sim <= 0.0:
        return 0.0
    total = sum(weights)
    if total <= 0:
        weights = STATIC_DEFAULT
        total = 1.0
    w1, w2, w3 = [w / total for w in weights]
    return round(_clamp01((w1 * sim) + (w2 * rec) + (w3 * succ)), 6)


def _dept_key(department: str) -> str:
    lowered = (department or "").lower().strip()
    return "rd" if lowered in {"r&d", "r_d"} else lowered


def _mean(values) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run query-adaptive dynamic weighting ablation.")
    parser.add_argument("--split", default="validation", choices=["train", "validation", "test"])
    parser.add_argument("--max-cases", type=int, default=50)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--dynamic-gain", type=float, default=0.50)
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "evaluation_v2" / "artifacts" / "dynamic_weighting_ablation.json"),
    )
    args = parser.parse_args()
    result = run_dynamic_weighting_ablation(
        split_name=args.split,
        max_cases=args.max_cases,
        k=args.k,
        dynamic_gain=args.dynamic_gain,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "cases": result["cases"],
        "dynamic_gain": result["dynamic_gain"],
        "winner_by_brier": result["winner_by_brier"],
        "winner_by_nll": result["winner_by_nll"],
        "metrics": {
            name: {
                "brier": scores["brier"],
                "nll": scores["nll"],
                "ece": scores["ece"],
                "mce": scores["mce"],
            }
            for name, scores in result["metrics"].items()
        },
    }, indent=2))


if __name__ == "__main__":
    main()
