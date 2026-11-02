"""Confidence calibration, recency decay, and conformal risk evaluation for MARS."""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

from evaluation.dataset import REPO_ROOT, CaseRecord, load_cases, replay_query_text, split_cases, visible_corpus
from evaluation.eval_retrieval import BM25Index
from evaluation.metrics import calibration_curve


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
        "protocol": "MARS temporal outcome calibration",
        "validation_cases": len(validation_cases),
        "test_cases": len(test_cases),
        "train_base_rate": train_base_rate,
        "selected_lambda": float(selected_lambda),
        "validation_lambdas": validation_scores,
        "test": {
            "base_rate": calibration_curve(base_probs, test_labels),
            "rag_unweighted": calibration_curve(rag_probs, test_labels),
            "mars_recency_weighted": calibration_curve(recency_probs, test_labels),
        },
        "conformal": conformal,
    }


def _predict_many(
    all_cases: Sequence[CaseRecord],
    eval_cases: Sequence[CaseRecord],
    *,
    k: int,
    train_base_rate: float,
    recency_lambda: float,
) -> List[Dict[str, Any]]:
    rows = []
    for case in eval_cases:
        prob = _predict_case(all_cases, case, k=k, train_base_rate=train_base_rate, recency_lambda=recency_lambda)
        rows.append({"case_id": case.case_id, "prediction": prob, "label": case.outcome_binary})
    return rows


def _predict_case(
    all_cases: Sequence[CaseRecord],
    target: CaseRecord,
    *,
    k: int,
    train_base_rate: float,
    recency_lambda: float,
) -> float:
    corpus = visible_corpus(all_cases, as_of_date=target.decision_date, target_case_id=target.case_id)
    if not corpus:
        return train_base_rate

    query = replay_query_text(target)
    retrieved = BM25Index(corpus).retrieve(query, k=k)
    weights = []
    values = []

    target_dt = target.decision_dt
    for doc, sim in retrieved:
        if not doc.get("outcome_visible") or not doc.get("outcome_label"):
            continue
        label = 1.0 if doc["outcome_label"].lower() == "success" else 0.0
        doc_dt = date.fromisoformat(doc["decision_date"])
        age_quarters = max(0.0, (target_dt - doc_dt).days / 91.25)
        recency = math.exp(-recency_lambda * age_quarters)
        weight = max(1e-4, sim) * recency
        weights.append(weight)
        values.append(label)

    if not weights or sum(weights) <= 0:
        return train_base_rate

    prior_weight = 1.0
    prior_value = train_base_rate
    estimate = (sum(w * v for w, v in zip(weights, values)) + prior_weight * prior_value) / (sum(weights) + prior_weight)
    return float(np.clip(estimate, 1e-4, 1.0 - 1e-4))


def _base_rate(cases: Sequence[CaseRecord]) -> float:
    if not cases:
        return 0.5
    return sum(case.outcome_binary for case in cases) / len(cases)


def _conformal_qhat(predictions: Sequence[float], labels: Sequence[int], alpha: float = 0.05) -> float:
    scores = [abs(prob - label) for prob, label in zip(predictions, labels)]
    if not scores:
        return 1.0
    n = len(scores)
    idx = int(math.ceil((n + 1) * (1.0 - alpha))) - 1
    idx = max(0, min(n - 1, idx))
    return float(np.sort(scores)[idx])


def _evaluate_conformal(predictions: Sequence[float], labels: Sequence[int], *, qhat: float) -> Dict[str, Any]:
    covered = 0
    widths = []
    abstentions = 0
    intervals = []

    for prob, label in zip(predictions, labels):
        low = max(0.0, prob - qhat)
        high = min(1.0, prob + qhat)
        is_covered = low <= label <= high
        if is_covered:
            covered += 1
        width = high - low
        widths.append(width)
        abstain = width >= 0.90
        if abstain:
            abstentions += 1
        intervals.append({"prob": prob, "label": label, "low": low, "high": high, "covered": is_covered, "abstain": abstain})

    n = max(1, len(predictions))
    return {
        "alpha": 0.05,
        "target_coverage": 0.95,
        "qhat": qhat,
        "empirical_coverage": covered / n,
        "mean_width": float(np.mean(widths)),
        "abstention_rate": abstentions / n,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run confidence calibration evaluation.")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--max-validation-cases", type=int, default=None)
    parser.add_argument("--max-test-cases", type=int, default=None)
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "evaluation" / "artifacts" / "calibration_results.json"),
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
