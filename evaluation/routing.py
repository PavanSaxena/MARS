"""Semantic routing benchmark and efficiency trace scaffolding."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set

from evaluation.dataset import REPO_ROOT, CaseRecord, load_cases, replay_query_text, split_cases


DEPT_MAP = {
    "Finance": "finance",
    "Legal": "legal",
    "Operations": "operations",
    "R&D": "rd",
}


def run_routing_evaluation(*, split_name: str = "test", max_queries: int | None = None) -> Dict[str, Any]:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from backend.app.reasoning.semantic_router import route_departments_semantically

    cases = split_cases(load_cases())[split_name]
    if max_queries is not None:
        cases = cases[:max_queries]

    per_case = []
    totals = {"tp": 0, "fp": 0, "fn": 0}
    latency_ms = []

    for case in cases:
        target = _target_departments(case)
        start = time.perf_counter()
        try:
            predicted, scores = route_departments_semantically(replay_query_text(case))
        except Exception as exc:
            return {
                "protocol": "evaluation.leakage_safe semantic routing",
                "split": split_name,
                "queries_evaluated": len(per_case),
                "status": "blocked_by_router_runtime",
                "error": str(exc),
                "note": (
                    "Semantic router could not run. In offline environments this is usually "
                    "because all-MiniLM-L6-v2 is not cached and Hugging Face is unreachable."
                ),
                "per_case": per_case,
            }
        elapsed = (time.perf_counter() - start) * 1000
        latency_ms.append(elapsed)
        predicted_set = set(predicted)
        tp = len(target & predicted_set)
        fp = len(predicted_set - target)
        fn = len(target - predicted_set)
        totals["tp"] += tp
        totals["fp"] += fp
        totals["fn"] += fn
        per_case.append(
            {
                "case_id": case.case_id,
                "target_departments": sorted(target),
                "predicted_departments": sorted(predicted_set),
                "scores": scores,
                "precision": tp / len(predicted_set) if predicted_set else 0.0,
                "recall": tp / len(target) if target else 0.0,
                "exact_match": target == predicted_set,
                "latency_ms": round(elapsed, 4),
            }
        )

    precision = totals["tp"] / (totals["tp"] + totals["fp"]) if totals["tp"] + totals["fp"] else 0.0
    recall = totals["tp"] / (totals["tp"] + totals["fn"]) if totals["tp"] + totals["fn"] else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    exact = sum(1 for row in per_case if row["exact_match"]) / len(per_case) if per_case else 0.0
    avg_active = sum(len(row["predicted_departments"]) for row in per_case) / len(per_case) if per_case else 0.0
    static_agents = 4
    estimated_agent_reduction = 1 - (avg_active / static_agents) if static_agents else 0.0

    return {
        "protocol": "evaluation.leakage_safe semantic routing",
        "split": split_name,
        "queries_evaluated": len(per_case),
        "label_policy": "target department plus departments named in cross_dept_impact",
        "micro_precision": round(precision, 6),
        "micro_recall": round(recall, 6),
        "micro_f1": round(f1, 6),
        "exact_match_rate": round(exact, 6),
        "avg_active_departments": round(avg_active, 6),
        "estimated_agent_call_reduction_vs_static": round(estimated_agent_reduction, 6),
        "latency_ms": _latency_summary(latency_ms),
        "per_case": per_case,
    }


def _target_departments(case: CaseRecord) -> Set[str]:
    targets = {DEPT_MAP.get(case.department, case.department.lower())}
    cross = (case.cross_dept_impact or "").replace(",", ";")
    for raw in cross.split(";"):
        item = raw.strip()
        if item in DEPT_MAP:
            targets.add(DEPT_MAP[item])
        else:
            lowered = item.lower()
            if lowered in {"finance", "legal", "operations", "rd", "r&d"}:
                targets.add("rd" if lowered == "r&d" else lowered)
    return targets


def _latency_summary(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    return {
        "p50": round(_percentile(ordered, 0.50), 4),
        "p95": round(_percentile(ordered, 0.95), 4),
        "p99": round(_percentile(ordered, 0.99), 4),
        "mean": round(sum(values) / len(values), 4),
    }


def _percentile(ordered: Sequence[float], q: float) -> float:
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[idx]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run semantic routing evaluation.")
    parser.add_argument("--split", default="test", choices=["train", "validation", "test"])
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "evaluation" / "leakage_safe" / "artifacts" / "routing_results.json"),
    )
    args = parser.parse_args()
    result = run_routing_evaluation(split_name=args.split, max_queries=args.max_queries)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "queries_evaluated": result["queries_evaluated"],
        "status": result.get("status", "ok"),
        "micro_f1": result.get("micro_f1"),
        "estimated_agent_call_reduction_vs_static": result.get("estimated_agent_call_reduction_vs_static"),
        "latency_ms": result.get("latency_ms"),
        "error": result.get("error"),
    }, indent=2))


if __name__ == "__main__":
    main()
