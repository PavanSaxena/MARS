"""
MultiCorp-QA Benchmark Dataset & Cross-Domain Harness
=====================================================
Implements standardized multi-industry corporate decision advisory benchmark based on:
1. BEIR: Thakur et al. (NeurIPS 2021) "Benchmarking IR Models"
2. FinQA: Chen et al. (EMNLP 2021) "A Dataset of Numerical Reasoning over Financial Data"
3. RAGAS: Es et al. (EACL 2024) "Automated Evaluation of Retrieval Augmented Generation"

Covers 4 critical enterprise industries:
- Big Tech & Software: Apple Inc. (AAPL), Microsoft Corp. (MSFT)
- Healthcare & Biopharma: Pfizer Inc. (PFE), Moderna Inc. (MRNA)
- Clean Energy & Auto: Tesla Inc. (TSLA), Toyota Motor Corp. (TM)
- Banking & Financial Services: JPMorgan Chase (JPM), Goldman Sachs (GS)
"""

import os
import sys
import json
import math
from typing import Dict, List, Tuple, Any

# Ensure backend root is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(current_dir) if os.path.basename(current_dir) == "evaluation" else current_dir
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app.reasoning.semantic_router import route_departments_semantically


MULTICORP_BENCHMARK_CASES = [
    # --- BIG TECH & SOFTWARE ---
    {
        "case_id": "MSFT-2024Q1-001",
        "company": "Microsoft Corp.",
        "sector": "Big Tech / Software",
        "query": "CapEx commitment for multi-gigawatt Azure OpenAI GPU datacenter expansion amidst liquid cooling power grid constraints",
        "target_departments": ["rd", "operations", "finance"],
        "primary_conflict": "Finance vs Operations",
        "ground_truth_outcome": "success",
        "expected_action": "expand"
    },
    {
        "case_id": "AAPL-2024Q2-002",
        "company": "Apple Inc.",
        "sector": "Big Tech / Software",
        "query": "EU Digital Markets Act compliance audit on alternative iOS app marketplaces, third-party payment gateways, and core technology fee penalties",
        "target_departments": ["legal"],
        "primary_conflict": "Legal vs Finance",
        "ground_truth_outcome": "failure",
        "expected_action": "revise"
    },
    {
        "case_id": "MSFT-2023Q4-003",
        "company": "Microsoft Corp.",
        "sector": "Big Tech / Software",
        "query": "FTC and CMA regulatory concessions and restructuring of cloud streaming rights for Activision Blizzard merger clearance",
        "target_departments": ["legal"],
        "primary_conflict": "Legal vs Operations",
        "ground_truth_outcome": "success",
        "expected_action": "revise"
    },

    # --- HEALTHCARE & BIOPHARMA ---
    {
        "case_id": "PFE-2024Q1-004",
        "company": "Pfizer Inc.",
        "sector": "Healthcare / Biopharma",
        "query": "Comirnaty vaccine manufacturing plant capacity decommissioning and $5.5B inventory impairment write-down post-pandemic",
        "target_departments": ["operations", "finance"],
        "primary_conflict": "Finance vs Operations",
        "ground_truth_outcome": "success",
        "expected_action": "terminate"
    },
    {
        "case_id": "PFE-2023Q3-005",
        "company": "Pfizer Inc.",
        "sector": "Healthcare / Biopharma",
        "query": "Phase 3 clinical trial protocol suspension for oral GLP-1 danuglipron due to high liver enzyme elevation and adverse patient discontinuation rates",
        "target_departments": ["rd", "legal"],
        "primary_conflict": "R&D vs Legal",
        "ground_truth_outcome": "failure",
        "expected_action": "terminate"
    },
    {
        "case_id": "MRNA-2024Q2-006",
        "company": "Moderna Inc.",
        "sector": "Healthcare / Biopharma",
        "query": "mRNA RSV vaccine mRESVIA commercial launch pricing and European patent infringement litigation with Arbutus Biopharma",
        "target_departments": ["legal", "finance"],
        "primary_conflict": "Legal vs Finance",
        "ground_truth_outcome": "success",
        "expected_action": "expand"
    },

    # --- CLEAN ENERGY & AUTOMOTIVE ---
    {
        "case_id": "TSLA-2024Q2-007",
        "company": "Tesla Inc.",
        "sector": "Clean Energy / Auto",
        "query": "Full Self-Driving FSD v12 end-to-end neural network commercial rollout and NHTSA regulatory recall scrutiny regarding driver monitoring safeguards",
        "target_departments": ["rd", "legal"],
        "primary_conflict": "R&D vs Legal",
        "ground_truth_outcome": "success",
        "expected_action": "expand"
    },
    {
        "case_id": "TSLA-2024Q1-008",
        "company": "Tesla Inc.",
        "sector": "Clean Energy / Auto",
        "query": "Giga Berlin factory expansion delay due to environmental water rights protests and high European EV import tariffs",
        "target_departments": ["operations", "legal"],
        "primary_conflict": "Operations vs Legal",
        "ground_truth_outcome": "failure",
        "expected_action": "revise"
    },
    {
        "case_id": "TM-2024Q3-009",
        "company": "Toyota Motor Corp.",
        "sector": "Clean Energy / Auto",
        "query": "Hybrid powertrain production reallocation from pure battery electric vehicles to meet surging global consumer demand for Prius and RAV4 hybrids",
        "target_departments": ["operations", "finance"],
        "primary_conflict": "Operations vs Finance",
        "ground_truth_outcome": "success",
        "expected_action": "revise"
    },

    # --- BANKING & FINANCIAL SERVICES ---
    {
        "case_id": "JPM-2023Q2-010",
        "company": "JPMorgan Chase",
        "sector": "Banking / Financial Services",
        "query": "Emergency acquisition and balance sheet absorption of First Republic Bank FDIC receivership with $50B loan loss-sharing agreement",
        "target_departments": ["finance", "legal"],
        "primary_conflict": "Finance vs Legal",
        "ground_truth_outcome": "success",
        "expected_action": "expand"
    },
    {
        "case_id": "JPM-2024Q1-011",
        "company": "JPMorgan Chase",
        "sector": "Banking / Financial Services",
        "query": "Federal Reserve Basel III Endgame capital adequacy rule compliance and commercial real estate office loan loss provisions",
        "target_departments": ["finance", "legal"],
        "primary_conflict": "Finance vs Legal",
        "ground_truth_outcome": "success",
        "expected_action": "revise"
    },
    {
        "case_id": "GS-2023Q4-012",
        "company": "Goldman Sachs",
        "sector": "Banking / Financial Services",
        "query": "Strategic divestiture and offloading of GreenSky consumer fintech lending platform and Apple Card credit partnership portfolio",
        "target_departments": ["finance", "operations"],
        "primary_conflict": "Finance vs Operations",
        "ground_truth_outcome": "failure",
        "expected_action": "terminate"
    }
]


def run_multicorp_benchmark() -> Dict[str, Any]:
    """
    Executes cross-domain evaluation on MultiCorp-QA benchmark:
    - Measures Sector-by-Sector Router Precision and Recall
    - Measures Cross-Domain Transfer of Semantic MoE Centroids
    - Computes macro and micro routing F1 scores
    """
    total_cases = len(MULTICORP_BENCHMARK_CASES)
    sector_results = {}
    
    total_tp = 0
    total_fp = 0
    total_fn = 0

    case_evaluations = []

    for case in MULTICORP_BENCHMARK_CASES:
        sector = case["sector"]
        if sector not in sector_results:
            sector_results[sector] = {
                "cases_count": 0,
                "precision_sum": 0.0,
                "recall_sum": 0.0,
                "exact_match_count": 0
            }

        # Run MARS semantic router
        active_depts, scores = route_departments_semantically(
            query=case["query"],
            threshold=0.20,  # Adjusted for multi-department discovery
            margin_ratio=0.60
        )

        target_set = set(case["target_departments"])
        predicted_set = set(active_depts)

        tp = len(target_set.intersection(predicted_set))
        fp = len(predicted_set - target_set)
        fn = len(target_set - predicted_set)

        total_tp += tp
        total_fp += fp
        total_fn += fn

        precision = tp / len(predicted_set) if predicted_set else 0.0
        recall = tp / len(target_set) if target_set else 0.0
        is_exact = target_set == predicted_set

        sector_results[sector]["cases_count"] += 1
        sector_results[sector]["precision_sum"] += precision
        sector_results[sector]["recall_sum"] += recall
        if is_exact:
            sector_results[sector]["exact_match_count"] += 1

        case_evaluations.append({
            "case_id": case["case_id"],
            "company": case["company"],
            "sector": sector,
            "target": list(target_set),
            "predicted": list(predicted_set),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "exact_match": is_exact,
            "scores": scores
        })

    # Aggregate sector stats
    summary_by_sector = {}
    for sector, data in sector_results.items():
        k = data["cases_count"]
        p_avg = data["precision_sum"] / k
        r_avg = data["recall_sum"] / k
        f1 = (2 * p_avg * r_avg / (p_avg + r_avg)) if (p_avg + r_avg) > 0 else 0.0
        summary_by_sector[sector] = {
            "cases": k,
            "avg_precision": round(p_avg, 3),
            "avg_recall": round(r_avg, 3),
            "macro_f1": round(f1, 3),
            "exact_match_rate": round(data["exact_match_count"] / k, 3)
        }

    global_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    global_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    global_micro_f1 = (2 * global_precision * global_recall / (global_precision + global_recall)) if (global_precision + global_recall) > 0 else 0.0

    return {
        "benchmark_name": "MultiCorp-QA Enterprise Cross-Domain Benchmark",
        "total_cases": total_cases,
        "sectors_evaluated": list(sector_results.keys()),
        "micro_precision": round(global_precision, 4),
        "micro_recall": round(global_recall, 4),
        "micro_f1": round(global_micro_f1, 4),
        "summary_by_sector": summary_by_sector,
        "case_details": case_evaluations
    }


if __name__ == "__main__":
    res = run_multicorp_benchmark()
    print("=== MultiCorp-QA Benchmark Results ===")
    print(json.dumps(res, indent=2))
