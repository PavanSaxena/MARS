# MARS Unified Evaluation Suite

Empirical evaluation and research benchmark suite for MARS (Multi-Agent Retrieval System).

## Directory Structure

```
evaluation/
├── dataset.py                # Unified dataset loader, chronological splits & manifest generation
├── eval_retrieval.py         # Retrieval evaluation (BEIR benchmark + leakage-safe temporal retrieval)
├── eval_generation.py        # Generation quality evaluation (G-Eval rubric, RAGAS, ROUGE-1/2/L)
├── eval_routing.py           # Department routing benchmark (temporal split + MultiCorp-QA 4 sectors)
├── eval_calibration.py       # Confidence calibration, recency decay (Brier, ECE/MCE, conformal risk)
├── eval_longitudinal.py      # Longitudinal out-of-sample backtesting (2023-2024 -> 2025-2026)
├── eval_replay.py            # Historical decision replay packet generation & execution tracing
├── run_benchmarks.py         # Master CLI runner orchestrating all benchmarks and audit
├── metrics.py                # Relevance, diversity, and calibration metrics
├── statistical_significance.py # Paired bootstrap hypothesis testing and Fleiss' Kappa
├── tracing.py                # Runtime latency, agent invocation, and retrieval tracing
├── artifacts/                # Generated evaluation manifests, JSON packets, and registries
└── results/                  # Benchmark execution output JSONs and BENCHMARK_REPORT.md
```

## Quick Start Commands

### 1. Master Benchmark Runner
Run any benchmark or the entire suite via `run_benchmarks.py`:

```bash
# Run one-command research audit (manifests, retrieval, calibration, routing, replay)
backend/.venv/bin/python -m evaluation.run_benchmarks --mode audit

# Run retrieval benchmark (BEIR + RAGChecker standards)
backend/.venv/bin/python -m evaluation.run_benchmarks --mode retrieval

# Run generation benchmark with judge LLM
backend/.venv/bin/python -m evaluation.run_benchmarks --mode generation --sample-size 40

# Run cross-industry routing benchmark (MultiCorp-QA)
backend/.venv/bin/python -m evaluation.run_benchmarks --mode routing

# Run out-of-sample longitudinal backtest
backend/.venv/bin/python -m evaluation.run_benchmarks --mode longitudinal

# Run all benchmarks
backend/.venv/bin/python -m evaluation.run_benchmarks --mode all
```

### 2. Individual Component Runners
Each `eval_*.py` module can also be executed directly:

```bash
# Temporal retrieval evaluation
backend/.venv/bin/python -m evaluation.eval_retrieval --mode leakage_safe --split test

# Confidence calibration evaluation
backend/.venv/bin/python -m evaluation.eval_calibration --k 10

# MultiCorp-QA cross-industry benchmark
backend/.venv/bin/python -m evaluation.eval_routing --mode multicorp

# Longitudinal backtest
backend/.venv/bin/python -m evaluation.eval_longitudinal

# Replay packet generation
backend/.venv/bin/python -m evaluation.eval_replay --mode packet --split test --max-cases 25
```

### 3. Unit and Protocol Tests
Integration and protocol-level tests are located in `backend/tests/`:

```bash
backend/.venv/bin/pytest backend/tests/test_protocol.py backend/tests/test_tool_robustness.py
backend/.venv/bin/python -m unittest backend/tests/test_confidence_reasoning.py
backend/.venv/bin/python backend/tests/run_tier1_benchmarks.py
```
