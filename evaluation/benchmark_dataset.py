"""Benchmark Dataset Loader for MARS Retrieval and Generation Evaluation.

Adheres strictly to the Time-Safe Chronological Protocol (MARS_DATA_AND_SUCCESS_PLAN.md Phase 3 & 5)
and empirical research standards (Thakur et al., BEIR NeurIPS 2021; Ru et al., RAGChecker NeurIPS 2024).
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
BASE_DIR = Path(__file__).resolve().parent.parent

# Check for lowercase or uppercase dataset dir
if (BASE_DIR / "dataset").exists():
    DATASET_DIR = BASE_DIR / "dataset"
elif (BASE_DIR / "Dataset").exists():
    DATASET_DIR = BASE_DIR / "Dataset"
else:
    DATASET_DIR = BASE_DIR / "dataset"


def load_verified_2023_dataset() -> List[Dict[str, Any]]:
    """Load all 640 paired decision-outcome cases from 2023 Q1-Q4."""
    quarters = ["2023_q1", "2023_q2", "2023_q3", "2023_q4"]
    all_cases = []

    for q in quarters:
        d_path = DATASET_DIR / "Decisions" / f"decisions_{q}.csv"
        o_path = DATASET_DIR / "Outcome" / f"outcomes_{q}.csv"

        if not d_path.exists() or not o_path.exists():
            raise FileNotFoundError(f"Missing quarterly file: {d_path} or {o_path}")

        with open(d_path, "r", encoding="utf-8") as f_d:
            decisions = list(csv.DictReader(f_d))
        with open(o_path, "r", encoding="utf-8") as f_o:
            outcomes = {r["case_id"]: r for r in csv.DictReader(f_o)}

        for d in decisions:
            case_id = d["case_id"]
            out = outcomes.get(case_id, {})
            
            # Parse quantitative signals
            q_sig = d.get("quantitative_signals")
            parsed_signals = []
            if q_sig and isinstance(q_sig, str) and (q_sig.startswith("[") or q_sig.startswith("{")):
                try:
                    parsed_signals = json.loads(q_sig)
                except Exception:
                    parsed_signals = []

            # Construct benchmark query (situation prompt)
            title = d.get("decision_title", "")
            desc = d.get("decision_description", "")
            rationale = d.get("decision_rationale", "")

            # Query text simulating a real executive / management strategic inquiry
            benchmark_query = f"{title}. Context: {desc}"

            all_cases.append({
                "case_id": case_id,
                "quarter": q.upper(),
                "decision_date": d.get("decision_date"),
                "department": d.get("department"),
                "decision_title": title,
                "decision_description": desc,
                "documented_action": d.get("documented_action"),
                "action_type": d.get("action_type"),
                "decision_rationale": rationale,
                "quantitative_signals": parsed_signals,
                "cross_dept_impact": d.get("cross_dept_impact", ""),
                "conflicting_perspectives": d.get("conflicting_perspectives", ""),
                "outcome_label": out.get("outcome_label", "unknown"),
                "observation_date": out.get("observation_date"),
                "observation_excerpt": out.get("observation_excerpt", ""),
                "benchmark_query": benchmark_query,
            })

    return all_cases


def get_stratified_generation_sample(
    sample_size: int = 40,
    seed: int = 42
) -> List[Dict[str, Any]]:
    """
    Select a balanced stratified sample across all 4 departments and 4 quarters.
    Ensures ~30% failure outcomes to mirror historical distribution.
    """
    import random
    rng = random.Random(seed)

    cases = load_verified_2023_dataset()
    by_dept = {"Finance": [], "Operations": [], "R&D": [], "Legal": []}
    for c in cases:
        dept = c["department"]
        if dept in by_dept:
            by_dept[dept].append(c)

    per_dept = max(1, sample_size // 4)
    selected = []

    for dept, dept_cases in by_dept.items():
        failures = [c for c in dept_cases if c["outcome_label"] == "failure"]
        successes = [c for c in dept_cases if c["outcome_label"] == "success"]

        target_fail = max(0, int(round(per_dept * 0.30)))
        target_succ = max(0, per_dept - target_fail)
        if target_fail == 0 and failures:
            target_fail = 1
            target_succ = max(0, per_dept - 1)

        rng.shuffle(failures)
        rng.shuffle(successes)

        dept_sample = failures[:target_fail] + successes[:target_succ]
        selected.extend(dept_sample)

    rng.shuffle(selected)
    return selected[:sample_size]


if __name__ == "__main__":
    cases = load_verified_2023_dataset()
    print(f"Total 2023 benchmark cases: {len(cases)}")
    sample = get_stratified_generation_sample(40)
    print(f"Stratified generation sample: {len(sample)} cases")
    from collections import Counter
    print("Dept breakdown:", Counter(c["department"] for c in sample))
    print("Outcome breakdown:", Counter(c["outcome_label"] for c in sample))
    print("Quarter breakdown:", Counter(c["quarter"] for c in sample))
