"""One-command lightweight audit for the defensible MARS evaluation layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.leakage_safe.build_manifests import main as _manifest_main
from evaluation.leakage_safe.calibration import run_calibration_evaluation
from evaluation.leakage_safe.dataset import REPO_ROOT, build_split_manifest, load_cases
from evaluation.leakage_safe.retrieval import run_retrieval_evaluation
from evaluation.leakage_safe.routing import run_routing_evaluation
from evaluation.leakage_safe.run_replay_outputs import run_replay_outputs


def run_research_audit(*, quick: bool = True) -> dict:
    output_dir = REPO_ROOT / "evaluation" / "leakage_safe" / "artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = load_cases()
    manifest = build_split_manifest(cases, output_dir / "split_manifest.json")
    retrieval = run_retrieval_evaluation(
        split_name="validation" if quick else "test",
        max_queries=50 if quick else None,
        include_dense=False,
    )
    calibration = run_calibration_evaluation(
        k=10,
        max_validation_cases=40 if quick else None,
        max_test_cases=40 if quick else None,
    )
    routing = run_routing_evaluation(split_name="validation" if quick else "test", max_queries=50 if quick else None)
    replay_outputs = run_replay_outputs(
        split_name="validation" if quick else "test",
        max_cases=10 if quick else 100,
        k=5,
        mode="deterministic",
    )
    result = {
        "mode": "quick" if quick else "full",
        "manifest_summary": {
            "total_cases": manifest["audit"]["total_cases"],
            "splits": {name: data["n"] for name, data in manifest["splits"].items()},
            "chronology_violations": len(manifest["audit"]["chronology_violations"]),
            "duplicate_case_ids": len(manifest["audit"]["duplicate_case_ids"]),
            "duplicate_content_groups": len(manifest["audit"]["duplicate_content_groups"]),
        },
        "retrieval_summary": retrieval["summary"],
        "retrieval_leakage_violations": retrieval["leakage_violations"],
        "calibration_test_summary": calibration["test"],
        "conformal_summary": calibration["conformal"],
        "routing_summary": _routing_summary(routing),
        "replay_output_summary": {
            "mode": replay_outputs["mode"],
            "cases": replay_outputs["cases"],
            "leakage_violations": replay_outputs["leakage_violations"],
            "trace_summary": replay_outputs["trace_summary"],
            "note": (
                "Deterministic replay outputs are protocol/tracing smoke tests, "
                "not final LLM quality evidence."
            ),
        },
    }
    (output_dir / "research_audit_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _routing_summary(routing: dict) -> dict:
    if routing.get("status"):
        return {
            "status": routing.get("status"),
            "queries_evaluated": routing.get("queries_evaluated", 0),
            "error": routing.get("error"),
            "note": routing.get("note"),
        }
    return {
        key: routing[key]
        for key in [
            "queries_evaluated",
            "micro_precision",
            "micro_recall",
            "micro_f1",
            "exact_match_rate",
            "avg_active_departments",
            "estimated_agent_call_reduction_vs_static",
            "latency_ms",
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run evaluation.leakage_safe research audit.")
    parser.add_argument("--full", action="store_true", help="Use full test split for retrieval/routing.")
    args = parser.parse_args()
    result = run_research_audit(quick=not args.full)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
