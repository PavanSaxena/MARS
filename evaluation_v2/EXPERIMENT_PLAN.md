# MARS Research-Defensible Experiment Plan

This plan supersedes earlier benchmark reports when preparing a paper. Earlier
reports may be useful implementation notes, but paper claims should point to
`evaluation_v2` artifacts generated under the leakage-safe protocol.

## Critical Invariants

- Target case is never retrieved as its own precedent.
- Decisions with `decision_date >= query decision_date` are invisible.
- Outcomes are visible only when `observation_date <= query decision_date`.
- Recency/calibration hyperparameters are selected on validation only.
- Significance tests use real paired per-case outputs.
- Human-evaluation packets hide source-system labels from raters.

## Required Experiments

| Experiment | Research question | Hypothesis | Setup | Dataset/sample size | Baseline | Metrics | Expected table/figure | Acceptance criteria |
|---|---|---|---|---|---|---|---|---|
| Split/leakage audit | Is the evaluation temporally valid? | The corpus can be replayed without target/future leakage. | `python3 -m evaluation_v2.build_manifests` | All 2,080 cases | N/A | duplicate IDs, duplicate content, chronology violations, split counts | Dataset audit table | zero duplicate IDs, zero chronology violations; all downstream runs report zero leakage violations |
| Temporal retrieval | Does retrieval find useful prior precedents? | MARS-style hybrid retrieval improves nDCG/diversity over simple baselines. | `python3 -m evaluation_v2.retrieval --split test` plus `--include-dense` when embeddings are cached | Full test split, 480 cases | BM25, dense, hybrid, hybrid+MMR | Precision/Recall@K, MRR, nDCG@10, diversity@10, latency | Retrieval table and diversity/quality plot | no leakage; claimed winner must beat baseline with paired CI |
| Decision replay | Does MARS improve advisory quality? | Full MARS improves evidence-grounded recommendation quality over LLM-only and RAG. | Generate packets with `python3 -m evaluation_v2.replay`; fill system outputs; score blind | At least 100 test cases, ideally all 480 | LLM-only, Naive RAG, Hybrid RAG, Static Multi-Agent, Full MARS | expert Likert scores, preference, action alignment, risk foresight, grounding | Main decision-quality table | Full MARS beats Naive RAG on primary score with 95% CI > 0 |
| Calibration | Are confidence scores meaningful probabilities? | Recency/outcome-aware confidence improves Brier/NLL/ECE over uncalibrated baselines. | `python3 -m evaluation_v2.calibration` | Validation 320, test 480 | train base rate, precedent success rate, recency-weighted precedent success rate | Brier, NLL, ECE, MCE, reliability bins | Reliability diagram and calibration table | lower Brier/NLL than base rate; if not, claim must be weakened |
| Dynamic weighting ablation | Does query-adaptive weighting improve confidence quality? | Query-conditioned weights improve Brier/NLL/ECE over static and registry weights. | `backend/.venv/bin/python -m evaluation_v2.dynamic_weighting_ablation --split test` | Full test split, 480 cases | static default, registry prior | Brier, NLL, ECE, MCE | Dynamic weighting ablation table | Dynamic wins or claim is limited to architecture/interpretability |
| Recency | Does recency improve future performance? | A validation-selected lambda improves test calibration. | Lambda grid in `evaluation_v2.calibration` | Validation/test splits | lambda=0 | Brier, NLL, ECE by lambda | Lambda sweep plot | selected lambda beats lambda=0 on held-out test, or no recency claim |
| Conformal/risk control | Are intervals/abstentions useful and valid? | Conformal intervals reach target coverage with acceptable width/selective risk. | `evaluation_v2.calibration` conformal block | Validation calibration, test evaluation | no conformal; unweighted conformal | coverage, width, abstention, selective risk | Coverage-width/selective-risk plot | empirical coverage near target; abstention rate not trivially 100% for claimed autonomy |
| Semantic routing | Does routing save compute without missing needed agents? | Dynamic routing reduces agent calls with acceptable recall. | `python3 -m evaluation_v2.routing --split test` | Full test plus OOD set | static all-agent, keyword router, LLM router if available | precision, recall, F1, exact match, false activations, missed departments, p50/p95/p99 | Router confusion table and efficiency plot | high recall for critical departments; compute reduction reported separately from quality |
| Efficiency | What does dynamic routing actually save? | Dynamic routing reduces LLM/tool/retrieval calls and latency. | Add runtime tracing to full decision replay runs | Same as replay | static all-agent | LLM calls, tokens, cost, latency p50/p95/p99, DB/tool calls | Efficiency table | >=30% cost reduction with non-inferior quality |
| Ablations | Which components contribute? | Each claimed component improves at least one primary metric. | Run replay with components removed | Same replay cases | Full MARS | decision score, calibration, cost | Ablation table | remove unsupported component claims |
| MCP/tool robustness | Does tool failure degrade safely? | Tool failures produce explicit fallbacks without hallucinated claims. | Failure injection tests | Synthetic failure suite | tools disabled | crash rate, fallback correctness, hallucination rate | Robustness table | no uncaught crashes; outputs disclose unavailable tools |
| Human evaluation | Do experts prefer MARS? | Experts prefer Full MARS on evidence/risk/conflict dimensions. | `blind_human_eval_packet.json`, 3-5 raters | >=100 cases | all main systems | Likert, pairwise preference, Fleiss/Krippendorff agreement | Human eval table | acceptable inter-rater agreement; statistically significant primary gain |

## Current Verified Artifacts

- `evaluation_v2/artifacts/split_manifest.json`
- `evaluation_v2/artifacts/retrieval_results.json`
- `evaluation_v2/artifacts/calibration_results.json`
- `evaluation_v2/artifacts/routing_results.json`
- `evaluation_v2/artifacts/decision_replay_packet.json`
- `evaluation_v2/artifacts/blind_human_eval_packet.json`
- `evaluation_v2/artifacts/research_audit_summary.json`

## Commands

Quick audit:

```bash
python3 -m evaluation_v2.research_audit
```

Protocol tests:

```bash
pytest -q evaluation_v2/test_protocol.py
```

Full retrieval with dense/hybrid baselines, when the embedding model is cached:

```bash
python3 -m evaluation_v2.retrieval --split test --include-dense
```

Replay packet:

```bash
python3 -m evaluation_v2.replay --split test --max-cases 100
```
