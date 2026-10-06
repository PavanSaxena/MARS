"""Sweep query-adaptive modulation gain for dynamic weighting."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from evaluation_v2.dataset import REPO_ROOT
from evaluation_v2.dataset import load_cases, replay_query_text, split_cases, visible_corpus
from evaluation_v2.dynamic_weighting_ablation import _dept_key, _feature_tuple, _weighted_confidence
from evaluation_v2.metrics import calibration_curve
from evaluation_v2.retrieval import BM25Index


DEFAULT_GAINS = [0.0, 0.25, 0.50, 0.70, 0.85, 1.00, 1.20]


def run_gain_sweep(
    *,
    split_name: str = "test",
    max_cases: int | None = None,
    k: int = 10,
    gains=DEFAULT_GAINS,
) -> dict:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    from backend.app.reasoning.dynamic_weighting import QueryAdaptiveWeightEngine

    all_cases = load_cases()
    targets = split_cases(all_cases)[split_name]
    if max_cases is not None:
        targets = targets[:max_cases]
    prepared = []
    for target in targets:
        query = replay_query_text(target)
        corpus = visible_corpus(
            all_cases,
            as_of_date=target.decision_date,
            target_case_id=target.case_id,
            include_visible_outcomes=True,
        )
        retrieved = [doc for doc, _ in BM25Index(corpus).retrieve(query, k=k)]
        prepared.append(
            {
                "target": target,
                "query": query,
                "features": _feature_tuple(target, query, retrieved),
                "label": target.outcome_binary,
            }
        )

    runs = []
    for gain in gains:
        engine = QueryAdaptiveWeightEngine(modulation_gain=float(gain))
        preds = []
        labels = []
        for row in prepared:
            target = row["target"]
            dyn = engine.compute_weights(
                query=row["query"],
                department=_dept_key(target.department),
                action_type=target.action_type,
            )
            preds.append(_weighted_confidence(row["features"], dyn.weights))
            labels.append(row["label"])
        dyn = calibration_curve(preds, labels)
        runs.append(
            {
                "gain": float(gain),
                "brier": dyn["brier"],
                "nll": dyn["nll"],
                "ece": dyn["ece"],
                "mce": dyn["mce"],
            }
        )

    return {
        "protocol": "evaluation_v2 dynamic weighting gain sweep",
        "split": split_name,
        "cases": len(prepared),
        "k": k,
        "gains": runs,
        "best_by_brier": min(runs, key=lambda row: row["brier"]),
        "best_by_nll": min(runs, key=lambda row: row["nll"]),
        "best_by_ece": min(runs, key=lambda row: row["ece"]),
        "best_by_mce": min(runs, key=lambda row: row["mce"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep dynamic weighting modulation gain.")
    parser.add_argument("--split", default="test", choices=["train", "validation", "test"])
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--gains", default=",".join(str(g) for g in DEFAULT_GAINS))
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "evaluation_v2" / "artifacts" / "dynamic_weighting_gain_sweep.json"),
    )
    args = parser.parse_args()
    gains = [float(item.strip()) for item in args.gains.split(",") if item.strip()]
    result = run_gain_sweep(
        split_name=args.split,
        max_cases=args.max_cases,
        k=args.k,
        gains=gains,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "best_by_brier": result["best_by_brier"],
        "best_by_nll": result["best_by_nll"],
        "best_by_ece": result["best_by_ece"],
        "best_by_mce": result["best_by_mce"],
        "gains": result["gains"],
    }, indent=2))


if __name__ == "__main__":
    main()
