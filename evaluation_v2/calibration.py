"""Leakage-safe confidence, recency, and conformal evaluation."""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

from evaluation_v2.dataset import REPO_ROOT, CaseRecord, load_cases, replay_query_text, split_cases, visible_corpus
from evaluation_v2.metrics import calibration_curve
from evaluation_v2.retrieval import BM25Index


DEFAULT_LAMBDAS = [0.0, 0.01, 0.03, 0.05, 0.08, 0.13]


def run_calibration_evaluation(
    *,
    k: int = 10,
    lambdas: Sequence[float] = DEFAULT_LAMBDAS,
    max_validation_cases: int | None = None,
    max_test_cases: int | None = None,
) -> Dict[str, Any]:
    cases = load_cases()
    splits = split_cases(cases)
    validation_cases = splits["validation"][:max_validation_cases] if max_validation_cases else splits["validation"]
    test_cases = splits["test"][:max_test_cases] if max_test_cases else splits["test"]
    train_base_rate = _base_rate(splits["train"])

    validation_predictions = {
        str(lam): _predict_many(cases, validation_cases, k=k, train_base_rate=train_base_rate, recency_lambda=lam)
        for lam in lambdas
    }
    validation_labels = [case.outcome_binary for case in validation_cases]
    validation_scores = {
        lam: calibration_curve([row["prediction"] for row in rows], validation_labels)
        for lam, rows in validation_predictions.items()
    }
    selected_lambda = min(validation_scores, key=lambda lam: validation_scores[lam]["brier"])

    test_labels = [case.outcome_binary for case in test_cases]
    base_probs = [train_base_rate for _ in test_cases]
    rag_rows = _predict_many(cases, test_cases, k=k, train_base_rate=train_base_rate, recency_lambda=0.0)
    recency_rows = _predict_many(cases, test_cases, k=k, train_base_rate=train_base_rate, recency_lambda=float(selected_lambda))

    rag_probs = [row["prediction"] for row in rag_rows]
    recency_probs = [row["prediction"] for row in recency_rows]
    qhat = _conformal_qhat(
        [row["prediction"] for row in validation_predictions[selected_lambda]],
        validation_labels,
        alpha=0.05,
    )
    conformal = _evaluate_conformal(recency_probs, test_labels, qhat=qhat)

    return {
        "protocol": "evaluation_v2 temporal outcome calibration",
        "rules": [
            "Predictions for each target use only prior decisions.",
            "Precedent outcomes are used only when observation_date <= target decision_date.",
            "Recency lambda is selected on validation and evaluated once on test.",
        ],
        "k": k,
        "train_cases": len(splits["train"]),
        "validation_cases": len(validation_cases),
        "test_cases": len(test_cases),
        "train_base_rate": round(train_base_rate, 6),
        "lambda_grid": list(lambdas),
        "selected_lambda": float(selected_lambda),
        "validation": validation_scores,
        "test": {
            "base_rate": calibration_curve(base_probs, test_labels),
            "rag_precedent_success_rate": calibration_curve(rag_probs, test_labels),
            "recency_weighted_precedent_success_rate": calibration_curve(recency_probs, test_labels),
        },
        "conformal": conformal,
        "per_case": [
            {
                "case_id": case.case_id,
                "decision_date": case.decision_date,
                "department": case.department,
                "action_type": case.action_type,
                "label": case.outcome_binary,
                "rag_prediction": round(rag["prediction"], 6),
                "recency_prediction": round(rec["prediction"], 6),
                "visible_precedent_outcomes": rec["visible_outcome_count"],
                "retrieved_ids": rec["retrieved_ids"],
            }
            for case, rag, rec in zip(test_cases, rag_rows, recency_rows)
        ],
    }


def _predict_many(
    all_cases: Sequence[CaseRecord],
    targets: Sequence[CaseRecord],
    *,
    k: int,
    train_base_rate: float,
    recency_lambda: float,
) -> List[Dict[str, Any]]:
    return [
        _predict_case(all_cases, target, k=k, fallback=train_base_rate, recency_lambda=recency_lambda)
        for target in targets
    ]


def _predict_case(
    all_cases: Sequence[CaseRecord],
    target: CaseRecord,
    *,
    k: int,
    fallback: float,
    recency_lambda: float,
) -> Dict[str, Any]:
    corpus = visible_corpus(
        all_cases,
        as_of_date=target.decision_date,
        target_case_id=target.case_id,
        include_visible_outcomes=True,
    )
    index = BM25Index(corpus)
    retrieved = index.retrieve(replay_query_text(target), k=k)
    usable = [doc for doc, _ in retrieved if doc.get("outcome_visible") and doc.get("outcome_label") in {"success", "failure"}]
    if not usable:
        return {
            "prediction": fallback,
            "visible_outcome_count": 0,
            "retrieved_ids": [doc["case_id"] for doc, _ in retrieved],
        }

    weighted_success = 0.0
    total_weight = 0.0
    target_date = target.decision_dt
    for doc in usable:
        label = 1.0 if doc["outcome_label"] == "success" else 0.0
        quarters = _elapsed_quarters(doc["decision_date"], target_date)
        weight = math.exp(-recency_lambda * max(0.0, quarters))
        weighted_success += weight * label
        total_weight += weight
    pred = weighted_success / total_weight if total_weight > 0 else fallback
    return {
        "prediction": min(1.0, max(0.0, pred)),
        "visible_outcome_count": len(usable),
        "retrieved_ids": [doc["case_id"] for doc, _ in retrieved],
    }


def _base_rate(cases: Sequence[CaseRecord]) -> float:
    return sum(case.outcome_binary for case in cases) / len(cases)


def _elapsed_quarters(decision_date: str, target_date: date) -> float:
    past = date.fromisoformat(decision_date)
    return max(0.0, (target_date - past).days / 91.25)


def _conformal_qhat(predictions: Sequence[float], labels: Sequence[int], alpha: float = 0.05) -> float:
    residuals = sorted(abs(float(p) - int(y)) for p, y in zip(predictions, labels))
    if not residuals:
        return 1.0
    n = len(residuals)
    rank = min(n, math.ceil((n + 1) * (1 - alpha)))
    return residuals[rank - 1]


def _evaluate_conformal(predictions: Sequence[float], labels: Sequence[int], *, qhat: float) -> Dict[str, Any]:
    intervals = [(max(0.0, p - qhat), min(1.0, p + qhat)) for p in predictions]
    coverage = sum(1 for (lo, hi), y in zip(intervals, labels) if lo <= y <= hi) / len(labels)
    widths = [hi - lo for lo, hi in intervals]
    abstain = [lo < 0.30 for lo, _ in intervals]
    non_abstained = [i for i, flag in enumerate(abstain) if not flag]
    if non_abstained:
        selective_errors = [
            int((predictions[i] >= 0.5) != bool(labels[i]))
            for i in non_abstained
        ]
        selective_risk = sum(selective_errors) / len(selective_errors)
    else:
        selective_risk = None
    return {
        "alpha": 0.05,
        "qhat": round(qhat, 6),
        "coverage": round(coverage, 6),
        "mean_width": round(float(np.mean(widths)), 6),
        "median_width": round(float(np.median(widths)), 6),
        "abstention_rate_lower_bound_lt_0_30": round(sum(abstain) / len(abstain), 6),
        "selective_risk_non_abstained": None if selective_risk is None else round(selective_risk, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run leakage-safe calibration evaluation.")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--max-validation-cases", type=int, default=None)
    parser.add_argument("--max-test-cases", type=int, default=None)
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "evaluation_v2" / "artifacts" / "calibration_results.json"),
    )
    args = parser.parse_args()
    result = run_calibration_evaluation(
        k=args.k,
        max_validation_cases=args.max_validation_cases,
        max_test_cases=args.max_test_cases,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "selected_lambda": result["selected_lambda"],
        "test": result["test"],
        "conformal": result["conformal"],
    }, indent=2))


if __name__ == "__main__":
    main()
