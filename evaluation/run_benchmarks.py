"""Master Benchmark and Research Audit Runner for MARS.

Consolidates all evaluation suites under a unified CLI:
- retrieval:     BEIR zero-shot and temporal precedent retrieval benchmark
- generation:    G-Eval / RAGAS / ROUGE generation quality benchmark
- routing:       MultiCorp-QA cross-industry & chronological split routing
- calibration:   Confidence calibration, recency decay, and conformal risk
- longitudinal:  Temporal out-of-sample backtesting (2023-2024 -> 2025-2026)
- audit:         One-command full defensibility audit of the evaluation layer
- all:           Run all benchmarks sequentially and update reports
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure paths
MARS_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = MARS_DIR / "backend"
if str(MARS_DIR) not in sys.path:
    sys.path.insert(0, str(MARS_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.dataset import REPO_ROOT, build_split_manifest, load_cases
from evaluation.eval_calibration import run_calibration_evaluation
from evaluation.eval_longitudinal import run_longitudinal_evaluation
from evaluation.eval_replay import run_replay_outputs
from evaluation.eval_retrieval import run_retrieval_benchmark, run_retrieval_evaluation
from evaluation.eval_routing import run_multicorp_benchmark, run_routing_evaluation

RESULTS_DIR = Path(__file__).resolve().parent / "results"
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
REPORT_PATH = Path(__file__).resolve().parent / "BENCHMARK_REPORT.md"


# =============================================================================
# Markdown Report Generator
# =============================================================================

def _fmt_row(label: str, metrics: dict, keys: list) -> str:
    vals = " | ".join(f"{metrics.get(k, 0):.4f}" for k in keys)
    return f"| {label:<42} | {vals} |"


def generate_report(retrieval_data: Optional[dict] = None, generation_data: Optional[dict] = None) -> None:
    """Write BENCHMARK_REPORT.md summarising all benchmark results."""
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# MARS Benchmark Report",
        "",
        f"**Generated:** {now}  ",
        "**System:** MARS — Multi-Agent Retrieval System for Corporate Decision Advisory  ",
        "**Dataset:** 2,080 verified decisions (2023-2026) with time-safe chronological evaluation  ",
        "",
        "---",
        "",
    ]

    # ---- Retrieval Section ----
    if retrieval_data:
        lines += [
            "## 1. Retrieval Benchmark",
            "",
            "> **Standard:** BEIR (Thakur et al., NeurIPS 2021) · RAGChecker (Ru et al., NeurIPS 2024)  ",
            f"> **Corpus:** {retrieval_data.get('dataset_size', 640)} historical decisions",
            "",
            "| System | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 | Dept Prec | Cross Rec | Latency (ms) |",
            "|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
        ]
        r_keys = ["recall_at_1", "recall_at_3", "recall_at_5", "mrr", "ndcg_at_5",
                  "dept_routing_precision", "cross_dept_recall", "mean_latency_ms"]
        for m in retrieval_data.get("metrics", []):
            label = m.get("system", "")
            vals = " | ".join(
                f"{m.get(k, 0):.2f}" if k == "mean_latency_ms" else f"{m.get(k, 0):.4f}"
                for k in r_keys
            )
            lines.append(f"| {label:<42} | {vals} |")
        lines += ["", "---", ""]

    # ---- Generation Section ----
    if generation_data:
        lines += [
            "## 2. Generation Quality Benchmark",
            "",
            "> **Standard:** G-Eval (Liu et al., EMNLP 2023) · RAGAS (Es et al., EACL 2024) · ROUGE (Lin, 2004)  ",
            f"> **Sample Size:** {generation_data.get('sample_size', 40)} stratified cases  ",
            f"> **Generator:** `{generation_data.get('generator_model', 'N/A')}`  ",
            f"> **Judge:** `{generation_data.get('judge_model', 'N/A')}`",
            "",
            "| System | Factual (1-5) | Grounding (1-5) | Foresight (1-5) | ROUGE-1 | ROUGE-2 | ROUGE-L | SemSim | Cit Prec | Cit Recall |",
            "|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
        ]
        g_keys = ["geval_factual_soundness", "geval_grounding_adherence", "geval_risk_foresight",
                  "rouge_1", "rouge_2", "rouge_l", "semantic_similarity",
                  "citation_precision", "citation_recall"]
        for m in generation_data.get("metrics", []):
            lines.append(_fmt_row(m.get("system", ""), m, g_keys))
        lines += ["", "---", ""]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written to: {REPORT_PATH}")


# =============================================================================
# Research Audit Runner
# =============================================================================

def run_research_audit(*, quick: bool = True) -> Dict[str, Any]:
    """One-command full audit across split, retrieval, calibration, routing, and replay."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    cases = load_cases()
    manifest = build_split_manifest(cases, ARTIFACTS_DIR / "split_manifest.json")
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
    routing = run_routing_evaluation(
        split_name="validation" if quick else "test",
        max_queries=50 if quick else None,
    )
    replay_out = run_replay_outputs(
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
        },
        "retrieval_summary": retrieval["summary"],
        "retrieval_leakage_violations": retrieval["leakage_violations"],
        "calibration_test_summary": calibration["test"],
        "conformal_summary": calibration["conformal"],
        "routing_summary": {
            k: routing.get(k)
            for k in [
                "queries_evaluated",
                "micro_precision",
                "micro_recall",
                "micro_f1",
                "exact_match_rate",
                "avg_active_departments",
                "estimated_agent_call_reduction_vs_static",
            ]
            if k in routing
        },
        "replay_output_summary": {
            "mode": replay_out["mode"],
            "cases": replay_out["cases"],
            "leakage_violations": replay_out["leakage_violations"],
            "trace_summary": replay_out["trace_summary"],
        },
    }
    (ARTIFACTS_DIR / "research_audit_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Master MARS Benchmark and Audit Runner.")
    parser.add_argument(
        "--mode",
        choices=["retrieval", "generation", "routing", "calibration", "longitudinal", "audit", "all"],
        default="audit",
        help="Which benchmark or evaluation suite to run.",
    )
    parser.add_argument("--sample-size", type=int, default=40, help="Sample size for generation benchmark.")
    parser.add_argument("--report-only", action="store_true", help="Regenerate BENCHMARK_REPORT.md from existing results.")
    parser.add_argument("--full", action="store_true", help="Run full evaluation instead of quick sample.")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.report_only:
        ret_data, gen_data = None, None
        ret_file = RESULTS_DIR / "retrieval_results.json"
        gen_file = RESULTS_DIR / "generation_results.json"
        if ret_file.exists():
            ret_data = json.loads(ret_file.read_text(encoding="utf-8"))
        if gen_file.exists():
            gen_data = json.loads(gen_file.read_text(encoding="utf-8"))
        generate_report(ret_data, gen_data)
        return

    ret_data = None
    gen_data = None

    if args.mode in ("retrieval", "all"):
        print("\n>>> [1/5] Running Retrieval Benchmark...")
        ret_data = run_retrieval_benchmark()

    if args.mode in ("generation", "all"):
        print("\n>>> [2/5] Running Generation Benchmark...")
        from evaluation.eval_generation import run_generation_benchmark
        gen_data = run_generation_benchmark(sample_size=args.sample_size)

    if args.mode in ("routing", "all"):
        print("\n>>> [3/5] Running Routing & MultiCorp-QA Benchmarks...")
        run_routing_evaluation(split_name="validation" if not args.full else "test")
        run_multicorp_benchmark()

    if args.mode in ("calibration", "all"):
        print("\n>>> [4/5] Running Calibration & Conformal Risk Evaluation...")
        run_calibration_evaluation()

    if args.mode in ("longitudinal", "all"):
        print("\n>>> [5/5] Running Longitudinal Temporal Backtesting...")
        run_longitudinal_evaluation()

    if args.mode == "audit":
        mode_str = "Full" if args.full else "Quick"
        print(f"\n>>> Running {mode_str} Leakage-Safe Research Audit...")
        audit_res = run_research_audit(quick=not args.full)
        print(json.dumps(audit_res, indent=2))

    if ret_data or gen_data:
        generate_report(ret_data, gen_data)


if __name__ == "__main__":
    main()
