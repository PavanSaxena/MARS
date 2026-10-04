"""MARS Unified Evaluation Package.

Modules
-------
dataset                 Unified dataset loading, time splits, and verified 2023 corpus
eval_retrieval          BM25 vs Dense vs MARS hybrid retrieval & temporal evaluation
eval_generation         G-Eval / RAGAS / ROUGE generation quality evaluation
eval_routing            Semantic dynamic routing & MultiCorp-QA cross-industry benchmark
eval_calibration        Confidence calibration, recency decay, and conformal risk
eval_longitudinal       Out-of-sample longitudinal backtesting (2023-2024 -> 2025-2026)
eval_replay             Decision replay packets, blind evaluation, and execution tracing
run_benchmarks          Master CLI runner for all benchmarks and research audit
metrics                 Retrieval, generation, and calibration evaluation metrics
statistical_significance Paired bootstrap hypothesis testing and Fleiss' Kappa
tracing                 Tracer primitives for latency, tool calls, and model outputs
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure paths
_MARS_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_ROOT = _MARS_ROOT / "backend"
if str(_MARS_ROOT) not in sys.path:
    sys.path.insert(0, str(_MARS_ROOT))
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Primary exports
from evaluation.dataset import (
    CaseRecord,
    load_cases,
    load_verified_2023_dataset,
    get_stratified_generation_sample,
    split_cases,
    visible_corpus,
)
from evaluation.eval_retrieval import (
    BM25Index,
    DenseIndex,
    HybridIndex,
    run_retrieval_benchmark,
    run_retrieval_evaluation,
)
from evaluation.eval_routing import (
    MULTICORP_BENCHMARK_CASES,
    run_multicorp_benchmark,
    run_routing_evaluation,
)
from evaluation.eval_calibration import (
    run_calibration_evaluation,
)
from evaluation.eval_longitudinal import (
    run_longitudinal_evaluation,
)
from evaluation.eval_replay import (
    SYSTEMS,
    build_replay_cases,
    build_blind_human_eval_packet,
    run_replay_outputs,
)
