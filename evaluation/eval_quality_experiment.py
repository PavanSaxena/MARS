"""Ablation & Decision Quality Evaluation Experiment.
Compares:
  - Baseline G1: Zero-Shot LLM
  - Baseline G2: Naive RAG Single Agent
  - MARS: Multi-Agent System with High-Recall Semantic Routing & Dialectical Aggregation
"""

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import numpy as np

MARS_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = MARS_DIR / "backend"
if str(MARS_DIR) not in sys.path:
    sys.path.insert(0, str(MARS_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from evaluation.dataset import load_cases, split_cases, load_verified_dataset
from evaluation.eval_generation import (
    ZeroShotLLMSystem,
    NaiveRAGSystem,
    MARSSystem,
    frontier_geval_score,
    calculate_deterministic_metrics,
    FRONTIER_JUDGE_MODEL,
    GENERATION_MODEL,
    DailyRateLimitExceeded,
)

def run_experiment(
    sample_size: int = 20,
    offset_per_dept: int = 0,
    judge_model: str = "qwen/qwen3.8-27b",
    gen_model: str = "groq:qwen/qwen3.8-27b",
    output_filename: str = "quality_experiment_results.json",
    checkpoint_filename: str = "quality_experiment_checkpoint.json",
):
    print("=" * 90)
    print("MARS DECISION QUALITY EXPERIMENTAL RUN")
    print(f"Generator Model: {gen_model} | Frontier Judge: {judge_model}")
    print(f"Sample Size: {sample_size} | Offset Per Dept: {offset_per_dept}")
    print(f"Output File: {output_filename} | Checkpoint: {checkpoint_filename}")
    print("=" * 90)

    # Load verified dataset and pick a balanced stratified test sample
    all_cases = load_verified_dataset()
    cases_by_dept = {"Finance": [], "Operations": [], "R&D": [], "Legal": []}
    for c in all_cases:
        dept = c.get("department")
        if dept in cases_by_dept:
            cases_by_dept[dept].append(c)

    per_dept = max(1, sample_size // 4)
    sample: List[Dict[str, Any]] = []
    for dept, dcases in cases_by_dept.items():
        # Pick cases with known outcomes and rich conflicts
        sorted_cases = sorted(dcases, key=lambda x: len(str(x.get("conflicting_perspectives", ""))), reverse=True)
        sample.extend(sorted_cases[offset_per_dept : offset_per_dept + per_dept])

    print(f"Selected {len(sample)} stratified cases ({per_dept} per department, offset {offset_per_dept}).")
    for s in sample:
        print(f"  - {s.get('case_id')} ({s.get('department')}): {s.get('decision_title')[:50]}")

    valid_case_ids = {c["case_id"] for c in all_cases}

    docs_text = [
        f"Decision Title: {d['decision_title']} Description: {d['decision_description']} "
        f"Rationale: {d['decision_rationale']} Department: {d['department']}"
        for d in all_cases
    ]
    from sentence_transformers import SentenceTransformer
    encoder = SentenceTransformer("all-MiniLM-L6-v2")
    corpus_embeddings = encoder.encode(
        docs_text, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
    )

    systems = [
        ZeroShotLLMSystem(model=gen_model),
        NaiveRAGSystem(corpus=all_cases, corpus_embeddings=corpus_embeddings, model=gen_model),
        MARSSystem(model=gen_model),
    ]

    out_file = MARS_DIR / "evaluation" / "results" / output_filename
    checkpoint_file = MARS_DIR / "evaluation" / "results" / checkpoint_filename

    # Resume from checkpoint if it exists
    results: Dict[str, List[Dict[str, Any]]] = {s.NAME: [] for s in systems}
    evaluated_pairs: set = set()  # (case_id, sys_name) pairs already done
    if checkpoint_file.exists():
        try:
            ckpt = json.loads(checkpoint_file.read_text())
            results = ckpt.get("per_system", results)
            for sys_name, recs in results.items():
                for r in recs:
                    evaluated_pairs.add((r["case_id"], sys_name))
            print(f"[RESUME] Loaded checkpoint: {len(evaluated_pairs)} evaluations already done.")
        except Exception as e:
            print(f"[WARN] Could not load checkpoint: {e}")

    def _save_checkpoint():
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_file.write_text(json.dumps({"per_system": results}, indent=2, default=str))

    for idx, case in enumerate(sample):
        cid = case.get("case_id")
        dept = case.get("department")
        outcome = case.get("outcome_label")
        title = case.get("decision_title", "")[:50]
        print(f"\n[{idx+1}/{len(sample)}] Evaluating {cid} ({dept} | {outcome}): {title}")

        for sys_obj in systems:
            sys_name = sys_obj.NAME
            if (cid, sys_name) in evaluated_pairs:
                print(f"  -> [SKIP] {sys_name} (already in checkpoint)")
                continue
            print(f"  -> Running {sys_name}...", end="", flush=True)
            t0 = time.perf_counter()
            try:
                resp = sys_obj.run(case)
                latency = (time.perf_counter() - t0) * 1000
                print(f" done ({latency:.0f}ms). Judging...", end="", flush=True)
                
                det = calculate_deterministic_metrics(resp, case, valid_case_ids)
                geval = frontier_geval_score(case, resp, judge_model=judge_model)
                print(f" Composite: {geval['composite']:.2f} (Align={geval['action_alignment']}, Confl={geval['conflict_awareness']}, Fact={geval['factual_grounding']}, Risk={geval['risk_foresight']})")
                
                record = {
                    "case_id": cid,
                    "department": dept,
                    "outcome_label": outcome,
                    "response": resp,
                    "latency_ms": latency,
                    **det,
                    **geval,
                }
                results[sys_name].append(record)
                evaluated_pairs.add((cid, sys_name))
                _save_checkpoint()  # Save after each successful evaluation
            except DailyRateLimitExceeded as e:
                print(f"\n[FATAL] Daily rate limit exceeded: {e}")
                print(f"Checkpoint safely saved. Please provide a new Groq API key and re-run to resume.")
                sys.exit(2)
            except Exception as e:
                print(f" ERROR: {e}")
                import traceback; traceback.print_exc()

            time.sleep(12)  # Respect TPM limit

    # Summarize results
    summary = {}
    print("\n" + "=" * 100)
    print("FINAL EXPERIMENTAL QUALITY BENCHMARK SCORES")
    print("=" * 100)
    print(f"{'System':<42} | {'ActAlign':>8} | {'ConflAware':>10} | {'FactGround':>10} | {'RiskFore':>8} | {'Composite':>9} | {'SemanticSim':>11}")
    print("-" * 100)

    for sys_name, records in results.items():
        if not records:
            continue
        agg = {
            "action_alignment": round(float(np.mean([r["action_alignment"] for r in records])), 3),
            "conflict_awareness": round(float(np.mean([r["conflict_awareness"] for r in records])), 3),
            "factual_grounding": round(float(np.mean([r["factual_grounding"] for r in records])), 3),
            "risk_foresight": round(float(np.mean([r["risk_foresight"] for r in records])), 3),
            "composite": round(float(np.mean([r["composite"] for r in records])), 3),
            "semantic_similarity": round(float(np.mean([r["semantic_similarity"] for r in records])), 3),
            "n": len(records),
        }
        summary[sys_name] = agg
        print(f"{sys_name:<42} | {agg['action_alignment']:>8.3f} | {agg['conflict_awareness']:>10.3f} | {agg['factual_grounding']:>10.3f} | {agg['risk_foresight']:>8.3f} | {agg['composite']:>9.3f} | {agg['semantic_similarity']:>11.3f}")

    print("=" * 100)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump({"summary": summary, "per_system": results, "meta": {"sample_size": len(sample), "offset_per_dept": offset_per_dept, "generator": gen_model, "judge": judge_model}}, f, indent=2, default=str)
    print(f"Results saved to {out_file}")
    # Clean up checkpoint
    if checkpoint_file.exists():
        checkpoint_file.unlink()
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MARS Decision Quality Experiment")
    parser.add_argument("--sample-size", type=int, default=20, help="Number of cases to sample")
    parser.add_argument("--offset", type=int, default=0, help="Offset per department")
    parser.add_argument("--batch", type=int, default=None, help="Batch index (e.g. 2 for cases 21-40)")
    parser.add_argument("--output", type=str, default=None, help="Output JSON filename")
    parser.add_argument("--checkpoint", type=str, default=None, help="Checkpoint JSON filename")
    args = parser.parse_args()

    offset = args.offset
    out_name = args.output or "quality_experiment_results.json"
    ckpt_name = args.checkpoint or "quality_experiment_checkpoint.json"

    if args.batch == 2:
        offset = 5
        out_name = args.output or "quality_experiment_results_batch2.json"
        ckpt_name = args.checkpoint or "quality_experiment_checkpoint_batch2.json"

    run_experiment(
        sample_size=args.sample_size,
        offset_per_dept=offset,
        output_filename=out_name,
        checkpoint_filename=ckpt_name,
    )
