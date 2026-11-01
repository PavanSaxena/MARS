"""Ablation & Decision Quality Evaluation Experiment.
Compares:
  - Baseline G1: Zero-Shot LLM
  - Baseline G2: Naive RAG Single Agent
  - MARS: Multi-Agent System with High-Recall Semantic Routing & Dialectical Aggregation
"""

import argparse
import concurrent.futures
import datetime
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    MultiPersonaSystem,
    HybridRAGSystem,
    ZeroShotCoTSystem,
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
    systems_to_run: Optional[List[str]] = None,
    preseed_file: Optional[str] = None,
    workers: int = 1,
):
    print("=" * 90)
    print("MARS DECISION QUALITY EXPERIMENTAL RUN")
    print(f"Generator Model: {gen_model} | Frontier Judge: {judge_model}")
    print(f"Sample Size: {sample_size} | Offset Per Dept: {offset_per_dept}")
    print(f"Output File: {output_filename} | Checkpoint: {checkpoint_filename}")
    if systems_to_run:
        print(f"Active Systems Filter: {systems_to_run}")
    if preseed_file:
        print(f"Pre-seed Source: {preseed_file}")
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

    keys_str = os.environ.get("GROQ_API_KEYS", "")
    if keys_str:
        groq_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
    else:
        single_k = os.environ.get("GROQ_API_KEY", "")
        groq_keys = [single_k] if single_k else []
    groq_keys = [k for k in groq_keys if k]
    print(f"Loaded {len(groq_keys)} Groq API key(s) in active pool.")

    def build_systems_for_key(api_key: Optional[str] = None) -> List[Any]:
        registry = {
            "G1": ZeroShotLLMSystem(model=gen_model, api_key=api_key),
            "G2": NaiveRAGSystem(corpus=all_cases, corpus_embeddings=corpus_embeddings, model=gen_model, api_key=api_key),
            "G1": ZeroShotCoTSystem(model=gen_model, api_key=api_key),
            "G2": MultiPersonaSystem(model=gen_model, api_key=api_key),
            "G3": HybridRAGSystem(corpus=all_cases, corpus_embeddings=corpus_embeddings, model=gen_model, api_key=api_key),
            "MARS": MARSSystem(model=gen_model, api_key=api_key),
        }
        if systems_to_run:
            sys_list = []
            for s in systems_to_run:
                sc = s.strip().upper()
                if sc in registry:
                    sys_list.append(registry[sc])
                elif sc in ("ALL", "LEAN"):
                    return [registry["G1"], registry["G2"], registry["G3"], registry["MARS"]]
            return sys_list
        # Canonical 4-system lean benchmark: Zero-Shot CoT, Multi-Persona, Hybrid RAG, MARS
        return [registry["G1"], registry["G2"], registry["G3"], registry["MARS"]]

    ref_systems = build_systems_for_key(groq_keys[0] if groq_keys else None)
    active_sys_names = [s.NAME for s in ref_systems]

    out_file = MARS_DIR / "evaluation" / "results" / output_filename
    checkpoint_file = MARS_DIR / "evaluation" / "results" / checkpoint_filename

    # Initialize results mapping
    results: Dict[str, List[Dict[str, Any]]] = {}
    evaluated_pairs: set = set()  # (case_id, sys_name) pairs already done

    # Pre-seed from existing results file if provided
    if preseed_file:
        preseed_path = MARS_DIR / "evaluation" / "results" / preseed_file
        if preseed_path.exists():
            try:
                ps_data = json.loads(preseed_path.read_text())
                results = ps_data.get("per_system", {})
                for sys_name, recs in results.items():
                    for r in recs:
                        evaluated_pairs.add((r["case_id"], sys_name))
                print(f"[PRESEED] Pre-seeded {len(evaluated_pairs)} evaluations from {preseed_file}")
            except Exception as e:
                print(f"[WARN] Could not pre-seed from {preseed_file}: {e}")

    # Ensure active systems are present in results dict
    for sname in active_sys_names:
        if sname not in results:
            results[sname] = []

    # Resume from checkpoint if it exists
    if checkpoint_file.exists():
        try:
            ckpt = json.loads(checkpoint_file.read_text())
            for sys_name, recs in ckpt.get("per_system", {}).items():
                results[sys_name] = recs
                for r in recs:
                    evaluated_pairs.add((r["case_id"], sys_name))
            print(f"[RESUME] Loaded checkpoint: {len(evaluated_pairs)} evaluations now recorded.")
        except Exception as e:
            print(f"[WARN] Could not load checkpoint: {e}")

    checkpoint_lock = threading.Lock()

    def _save_checkpoint():
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_file.write_text(json.dumps({"per_system": results}, indent=2, default=str))

    # Identify remaining cases
    pending_cases: List[Tuple[int, Dict[str, Any]]] = []
    for idx, case in enumerate(sample):
        cid = case.get("case_id")
        if any((cid, sname) not in evaluated_pairs for sname in active_sys_names):
            pending_cases.append((idx, case))

    num_workers = max(1, workers)
    print(f"Deploying {num_workers} worker(s) for {len(pending_cases)} pending cases ({len(sample) - len(pending_cases)} already done).")

    def process_case(case_idx: int, case: Dict[str, Any], worker_id: int):
        cid = case.get("case_id")
        dept = case.get("department")
        outcome = case.get("outcome_label")
        title = case.get("decision_title", "")[:45]
        # Build systems using dynamic multi-key pool (api_key=None draws round-robin)
        worker_systems = build_systems_for_key(None)

        print(f"\n[W{worker_id+1} | Case {case_idx+1}/{len(sample)}] {cid} ({dept} | {outcome}): {title}", flush=True)

        case_records: Dict[str, Dict[str, Any]] = {}
        for sys_obj in worker_systems:
            sys_name = sys_obj.NAME
            with checkpoint_lock:
                if (cid, sys_name) in evaluated_pairs:
                    continue

            t0 = time.perf_counter()
            try:
                resp = sys_obj.run(case)
                latency = (time.perf_counter() - t0) * 1000
                det = calculate_deterministic_metrics(resp, case, valid_case_ids)
                geval = frontier_geval_score(case, resp, judge_model=judge_model, api_key=None)

                record = {
                    "case_id": cid,
                    "department": dept,
                    "outcome_label": outcome,
                    "response": resp,
                    "latency_ms": latency,
                    **det,
                    **geval,
                }
                case_records[sys_name] = record
                print(f"  [W{worker_id+1}] {sys_name[:22]} -> Comp: {geval['composite']:.2f} (Align={geval['action_alignment']}, Confl={geval['conflict_awareness']}, Fact={geval['factual_grounding']}, Risk={geval['risk_foresight']})", flush=True)
            except DailyRateLimitExceeded as e:
                print(f"\n[STOP W{worker_id+1}] Daily token limit reached: {e}", flush=True)
                raise
            except Exception as e:
                print(f"  [W{worker_id+1}] ERROR on {sys_name}: {e}", flush=True)
                import traceback; traceback.print_exc()

        with checkpoint_lock:
            for sys_name, rec in case_records.items():
                results[sys_name].append(rec)
                evaluated_pairs.add((cid, sys_name))
            _save_checkpoint()
            completed_cases_count = len({r["case_id"] for r in results.get(active_sys_names[0], [])})
            print(f"==> Progress: {completed_cases_count}/{len(sample)} cases complete.", flush=True)

    if num_workers > 1 and pending_cases:
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(process_case, cidx, case, i % num_workers)
                for i, (cidx, case) in enumerate(pending_cases)
            ]
            for f in concurrent.futures.as_completed(futures):
                try:
                    f.result()
                except DailyRateLimitExceeded:
                    print("[STOP] Daily token limit reached — saving checkpoint and stopping.")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
    elif pending_cases:
        try:
            for i, (cidx, case) in enumerate(pending_cases):
                process_case(cidx, case, 0)
        except DailyRateLimitExceeded:
            print("[STOP] Daily token limit reached — saving checkpoint and stopping.")

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
    # Clean up checkpoint only if all cases are completed
    all_completed = all(len(results.get(sname, [])) >= len(sample) for sname in active_sys_names)
    if all_completed and checkpoint_file.exists():
        checkpoint_file.unlink()
    elif checkpoint_file.exists():
        print(f"Partial run completed: checkpoint kept at {checkpoint_file}")
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MARS Decision Quality Experiment")
    parser.add_argument("--sample-size", type=int, default=20, help="Number of cases to sample")
    parser.add_argument("--offset", type=int, default=0, help="Offset per department")
    parser.add_argument("--batch", type=int, default=None, help="Batch index (e.g. 2 for cases 21-40)")
    parser.add_argument("--output", type=str, default=None, help="Output JSON filename")
    parser.add_argument("--checkpoint", type=str, default=None, help="Checkpoint JSON filename")
    parser.add_argument("--systems", type=str, default=None, help="Comma-separated systems to evaluate: G1,G2,G3,G4,G5,MARS,ALL")
    parser.add_argument("--preseed", type=str, default=None, help="JSON file in evaluation/results to pre-seed already evaluated systems")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker threads (default 1 for single-key)")
    args = parser.parse_args()

    offset = args.offset
    out_name = args.output or "quality_experiment_results.json"
    ckpt_name = args.checkpoint or "quality_experiment_checkpoint.json"

    if args.batch == 2:
        offset = 5
        out_name = args.output or "quality_experiment_results_batch2.json"
        ckpt_name = args.checkpoint or "quality_experiment_checkpoint_batch2.json"

    sys_list = [s.strip() for s in args.systems.split(",")] if args.systems else None

    run_experiment(
        sample_size=args.sample_size,
        offset_per_dept=offset,
        output_filename=out_name,
        checkpoint_filename=ckpt_name,
        systems_to_run=sys_list,
        preseed_file=args.preseed,
        workers=args.workers,
    )
