"""MARS Unified Evaluation Package.

Modules
-------
benchmark_dataset       Time-safe dataset loader (BEIR protocol)
eval_retrieval          BM25 vs Dense vs MARS retrieval evaluation
eval_generation         G-Eval / RAGAS / ROUGE generation quality
run_benchmark           Unified BEIR benchmark runner
longitudinal_evaluation Out-of-sample longitudinal backtesting
multicorp_benchmark     MultiCorp-QA cross-industry benchmark
statistical_significance Paired bootstrap + Fleiss Kappa significance tests
dataset                 Leakage-safe corpus with time-split manifests
retrieval               Leave-target-out temporal retrieval evaluation
calibration             Conformal calibration, Brier/NLL/ECE scoring
replay                  Historical decision replay packet builder
routing                 Semantic router evaluation
research_audit          One-command full leakage-safe audit runner
metrics / tracing       Shared utilities
"""
