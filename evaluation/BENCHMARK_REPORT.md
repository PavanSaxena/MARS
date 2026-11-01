# MARS Master Benchmark Report
**Clean Multi-Agent Decision Advisory Evaluation · Empirical Statistical Inference · Audit-Aligned Findings**

**Dataset:** Apple Corporate Decision Corpus (2023Q3–2025Q4)  
**Evaluation Protocol:** 40 Stratified Decisions (10 Finance, 10 Operations, 10 R&D, 10 Legal) · 4 Systems × 40 Cases = 160 Evaluations  
**Generator Model:** `groq:qwen/qwen3.8-27b` · **Judge Model:** `qwen/qwen3.8-27b` (G-Eval Chain-of-Thought Rubric)  
**Results File:** `evaluation/results/quality_experiment_results_clean4.json`  

---

> [!IMPORTANT]
> **Research Audit Notice (2026-11-02):**
> In alignment with the comprehensive research and code audit (`MARS_audit_vs_research.md` / `claims_registry.json`), this report documents strictly verified, empirical evaluation results. Three legacy claims from prototype iterations (an unsupported "+95.9% Brier improvement", hardcoded "simulated" bootstrap $p=0.0$ / Fleiss' $\kappa=0.5088$, and mathematically impossible retrieval nDCG $>1.0$ from self-retrieval) are formally **retracted** in Section 5. All generation results reported below use target-case exclusion to prevent self-retrieval leakage.

---

## 1. Executive Summary & Core Results

MARS (Multi-Agent Reasoning System) coordinates four parallel department specialists (**Finance, Operations, R&D, Legal**) with hybrid BM25 + dense retrieval, Maximal Marginal Relevance (MMR) diversity reranking, and an adversarial strategic aggregator.

We evaluated MARS against three rigorous, fair baselines receiving identical case information (decision description, quantitative signals, cross-departmental impact, and documented stakeholder tensions) across 40 chronological corporate decision cases.

### 1.1 System Architecture Definitions

| System ID | Architecture Name | Retrieval | Reasoning Strategy |
|:---|:---|:---:|:---|
| **G1** | Baseline G1: Zero-Shot CoT | None | Direct chain-of-thought prompting (Wei et al., 2022) |
| **G2** | Baseline G2: Single-Agent Multi-Persona | None | Roleplay Executive Council (Finance, Ops, R&D, Legal) in single LLM prompt |
| **G3** | Baseline G3: Hybrid RAG Single-Agent | BM25 + Dense + MMR ($k=5$) | Single-agent RAG with temporal precedent grounding (target excluded) |
| **MARS** | Multi-Agent Hybrid + MMR + Cross-Dept | BM25 + Dense + MMR ($k=5$ per dept) | 4 parallel domain agents + strategic governance aggregator |

### 1.2 Final Multi-Dimensional Quality Scores (40 Cases · 160 Evaluations)

Scores evaluated on a 1–5 G-Eval Likert scale across four decision dimensions:
- **Action Alignment (ActAlign):** Practical feasibility, specificity, and execution readiness.
- **Conflict Awareness (ConflAware):** Explicit recognition of cross-departmental trade-offs and tensions.
- **Factual Grounding (FactGround):** Substantiation by cited historical precedent cases and quantitative signals.
- **Risk Foresight (RiskFore):** Downstream risk identification and proactive mitigation planning.
- **Composite Score:** Unweighted arithmetic mean across all four dimensions.

```
========================================================================================================
FINAL EXPERIMENTAL QUALITY BENCHMARK SCORES (n=40 Cases, 160 Total Evaluations)
========================================================================================================
System                                     | ActAlign | ConflAware | FactGround | RiskFore | Composite
--------------------------------------------------------------------------------------------------------
Baseline G1: Zero-Shot CoT                 |    4.025 |      4.900 |      3.075 |    3.450 |     3.862
Baseline G2: Single-Agent Multi-Persona    |    4.275 |      4.800 |      3.000 |    3.775 |     3.962
Baseline G3: Hybrid RAG Single-Agent       |    3.475 |      4.500 |      2.500 |    3.800 |     3.569
MARS: Multi-Agent Hybrid + MMR + Cross-Dept|    4.550 |      4.800 |      4.550 |    4.525 |     4.606
========================================================================================================
```

**Key Findings:**
- **MARS leads all baselines overall:** Achieves a **4.606** composite score, an improvement of **+0.644 points (+16.2%)** over the strongest single-agent baseline (G2 Multi-Persona at 3.962).
- **Factual Grounding is the primary differentiator:** MARS scores **4.550** vs. 3.075 (G1) and 2.500 (G3), a **+1.475 point advantage ($p < 0.0001$)**. Multi-agent domain isolation ensures that domain-specific citations and data are preserved rather than diluted in a generalist prompt.
- **Risk Foresight is substantially elevated:** Department specialist agents identify structural, operational, and regulatory failure modes that generalist agents overlook (**4.525** vs. 3.800 for G3, $p = 0.0001$).
- **Conflict Awareness is uniformly high across architectures:** All systems perform strongly on conflict recognition (4.500–4.900), indicating that when explicitly provided with documented stakeholder tensions, frontier LLMs readily reflect cross-functional trade-offs.

---

## 2. Statistical Inference & Significance Testing

To verify that MARS's observed performance gains are not sample artifacts, we conducted non-parametric paired hypothesis testing and bootstrap resampling.

### 2.1 95% Bootstrap Confidence Intervals (10,000 Resamples)

| System | Mean Composite | 95% Bootstrap CI | CI Width |
|:---|:---:|:---:|:---:|
| Baseline G1: Zero-Shot CoT | 3.862 | [3.631, 4.081] | 0.450 |
| Baseline G2: Single-Agent Multi-Persona | 3.962 | [3.781, 4.138] | 0.356 |
| Baseline G3: Hybrid RAG Single-Agent | 3.569 | [3.300, 3.831] | 0.531 |
| **MARS: Multi-Agent System** | **4.606** | **[4.375, 4.812]** | **0.438** |

> **Non-Overlapping Intervals:** The lower bound of the MARS bootstrap interval (4.375) strictly exceeds the upper bound of the strongest baseline (G2 at 4.138), demonstrating that the composite performance gap is statistically robust.

### 2.2 Paired Wilcoxon Signed-Rank Hypothesis Tests (One-Tailed: MARS > Baseline)

| Comparison | Wilcoxon $W$ | $p$-value | Rank-Biserial $r_{rb}$ | Cohen's $d$ | Significance |
|:---|:---:|:---:|:---:|:---:|:---:|
| **MARS > Baseline G1** | 600.0 | $< 0.0001$ | -0.463 | **1.026** | *** ($p < 0.001$) |
| **MARS > Baseline G2** | 637.0 | $0.0001$ | -0.554 | **0.995** | *** ($p < 0.001$) |
| **MARS > Baseline G3** | 620.5 | $< 0.0001$ | -0.513 | **1.304** | *** ($p < 0.001$) |

> Cohen's $d \approx 1.0 - 1.3$ denotes very large practical effect sizes across all three paired comparisons.

### 2.3 Dimension-Specific Statistical Testing (MARS vs. Best Baseline)

| Dimension | Best Baseline | MARS Mean | Baseline Mean | $\Delta$ | $p$-value | Significance |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| Action Alignment | G2 (Multi-Persona) | 4.550 | 4.275 | +0.275 | $0.0330$ | * ($p < 0.05$) |
| Conflict Awareness | G1 (Zero-Shot CoT) | 4.800 | 4.900 | -0.100 | $0.7602$ | ns (not significant) |
| **Factual Grounding** | **G1 (Zero-Shot CoT)** | **4.550** | **3.075** | **+1.475** | **$< 0.0001$** | **\*\*\* ($p < 0.001$)** |
| **Risk Foresight** | **G3 (Hybrid RAG)** | **4.525** | **3.800** | **+0.725** | **$0.0001$** | **\*\*\* ($p < 0.001$)** |
| **Composite Score** | **G2 (Multi-Persona)** | **4.606** | **3.962** | **+0.644** | **$0.0001$** | **\*\*\* ($p < 0.001$)** |

---

## 3. Departmental Performance Breakdown

Evaluating performance across functional domains reveals where multi-agent specialization provides the greatest marginal return:

| Department | Cases | G1: Zero-Shot | G2: Multi-Persona | G3: Hybrid RAG | MARS | MARS Lead vs. Best Baseline |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Finance** | 10 | 3.675 | 3.975 | 3.425 | **4.850** | **+0.875** (vs. G2) |
| **Operations** | 10 | 3.925 | 3.925 | 3.975 | **4.700** | **+0.725** (vs. G3) |
| **R&D** | 10 | 3.875 | 3.700 | 3.475 | **4.525** | **+0.650** (vs. G1) |
| **Legal** | 10 | 3.975 | 4.250 | 3.400 | **4.350** | **+0.100** (vs. G2) |

### Departmental Insights:
1. **Finance (+0.875 lead):** Financial decisions require grounding in balance sheet liquidity, gross margins, and capital expenditure constraints. MARS's Finance specialist agent preserves quantitative ratios without letting generalist prose dilute them.
2. **Operations (+0.725 lead):** Operations decisions require concrete supplier SLAs, yield targets, and logistics contingencies. Isolated retrieval provides concrete operational precedents.
3. **Legal (+0.100 lead — most competitive baseline):** Legal decisions show the smallest gap between MARS and G2. Well-specified regulatory scenarios (e.g., EU DMA compliance, contractual arbitration) are handled competently by a single-agent multi-persona prompt.
4. **The "Single-Agent RAG Pathology" (G3 underperformance):** In Finance (3.425) and Legal (3.400), Baseline G3 underperforms even the non-retrieval baselines (G1 and G2). Concatenating 5 retrieved cases across disparate departments into a single prompt creates context distraction, causing the LLM to average out conflicting domain evidence. MARS resolves this by delegating retrieval to domain specialists before strategic synthesis.

---

## 4. Confidence Calibration & Longitudinal Backtesting

> **Reference Artifact:** `evaluation/artifacts/calibration_results.json`  
> **Evaluation Sample:** 480 held-out test decisions (temporal split: Train/Val = 2023Q1–2024Q4, Test = 2025Q1–2026Q1)

In corporate decision advisory, confidence calibration is essential: when the system provides advice, its expressed confidence must match empirical success probabilities.

### 4.1 Empirical Calibration Results (Test Set, $N = 480$)

| Predictive Method | Brier Score (lower = better) | Negative Log-Likelihood (NLL) | ECE |
|:---|:---:|:---:|:---:|
| **Constant Train Base Rate (0.705)** | **0.2040** | **0.5983** | **0.0000** |
| Dynamic Weighting (Simplex Ablation) | 0.2190 | 0.6470 | 0.0890 |
| MARS Recency-Weighted ($\lambda = 0.08$) | 0.2251 | 0.7031 | 0.1125 |
| Standard RAG (Unweighted) | 0.2252 | 0.7036 | 0.1130 |

> **Scientific Disclosure:**  
> Under a strict, leakage-safe protocol, neither standard RAG nor recency-weighted precedent scoring outperforms a constant baseline predicting the historical base rate (0.705). In corporate decision making, historical precedent similarity alone is not a sufficient statistical predictor of future outcome success.

### 4.2 Conformal Risk Control (Inductive Split Conformal Prediction, $\alpha = 0.05$)

- **Target Coverage:** $95.0\%$ ($1 - \alpha$)
- **Calibrated Non-Conformity Cutoff ($\hat{q}$):** **0.8159** (calculated on held-out validation set)
- **Empirical Test Coverage:** **94.58%**
- **Mean Conformal Interval Width:** **0.9841**
- **Abstention Rate (for strict human review):** **96.67%**

> **Implication for Autonomy:**  
> Because the empirical non-conformity threshold is $\hat{q} \approx 0.816$, finite-sample distribution-free intervals are wide ($[0.0, 1.0]$ for most decisions). Consequently, the enterprise risk policy correctly triggers `ABSTAIN_FOR_HUMAN_REVIEW` on $96.7\%$ of cases rather than asserting false certainty. This aligns with human-above-the-loop decision support: MARS acts as an evidence synthesizer and trade-off analyst, not an autonomous decider.

---

## 5. Audit Findings & Formal Retraction of Unsupported Claims

Following an exhaustive source and artifact audit (`/home/harshith/Downloads/MARS_audit_vs_research.md`), the following claims from preliminary drafts have been audited and updated:

| Prior Claim | Prior Status | Audit Finding | Updated Scientific Position |
|:---|:---:|:---|:---|
| **"+95.9% Brier Improvement"** | Claimed in early README | Label leakage in prototype script `eval_longitudinal.py` (`simulate_precedent_retrieval` directly read `case["ground_truth_label"]`). | **RETRACTED.** Clean calibration yields Brier = 0.225 vs. base-rate Brier = 0.204. No model beats the base rate on this corpus. |
| **"p = 0.00000 Bootstrap & Fleiss' $\kappa = 0.5088$"** | Claimed in report v1 | Hardcoded arrays in `run_tier1_benchmarks.py` labelled "simulated" in code comments; no real human agreement study was run. | **RETRACTED.** Replaced with real empirical Wilcoxon tests ($p = 0.0001$) and 10,000-resample bootstrap CIs reported in Section 2. |
| **"Retrieval nDCG@5 = 1.19"** | Claimed in retrieval table | Mathematically impossible ($> 1.0$). Resulted from self-retrieval where query cases existed in their own retrieval pool. | **RETRACTED.** All generation and retrieval evaluations now enforce `target_case_id` exclusion. |
| **"Production $\hat{q} = 0.284$"** | Hardcoded constant | Prototype fallback constant. Empirical calibration yields $\hat{q} = 0.816$. | **CORRECTED.** Updated `conformal_predictor.py` fallback to 0.816 matching `calibration_results.json`. |
| **"Aggregator Sees User Problem"** | Claimed in docs | Aggregator read `state.get("problem_statement")` which was absent from `State`, resulting in an empty problem string in prompt. | **FIXED.** Aggregator now extracts the user query directly from `state["messages"]`. |
| **"State.retrieved_cases Populated"** | Claimed in docs | No graph node wrote to `State.retrieved_cases`, preventing API evidence panel display. | **FIXED.** Aggregator collects department evidence and returns `retrieved_cases` in state. |

---

## 6. Dataset Provenance, Corpus Scope & Limitations

1. **Single-Corporation Scope:** The 2,080 cases are sourced from Apple Inc. public disclosures, 10-K/10-Q filings, and associated trade press (2023–2026). While domain diversity spans Finance, Operations, R&D, and Legal, cross-firm generalizability remains to be validated.
2. **Templated Decision Clusters in 2025Q1–Q3:** Several 2025Q1 Finance cases (`AAPL-2025Q1-0085` through `0090`) and 2025Q2–Q3 R&D cases share structured boilerplate phrasing ("Restructure Short-Term Liquidity Allocation Tranche", "Scale Dedicated Neural Engine Optimization Pipeline"). Future benchmarks should increase cross-year case dispersion.
3. **Judge Model Self-Alignment:** The benchmark utilized `qwen/qwen3.8-27b` both as generator and G-Eval judge. While strict rubric prompts and Chain-of-Thought scoring mitigate bias, cross-model judging (e.g., using Claude 3.5 Sonnet or GPT-4o as external judge) is recommended for independent confirmation.
4. **Evaluation Sample Size:** The 40-case stratified sample provides sufficient statistical power for composite and major dimensional effects ($d \approx 1.0, p < 0.001$), but sub-dimension comparisons with subtle effect sizes (e.g., Conflict Awareness) require larger sample sizes.

---

## 7. Conclusions & Research Implications

The clean, audit-verified 40-case benchmark demonstrates that **MARS achieves statistically significant, practically meaningful improvements in decision support quality over single-agent and standard RAG baselines**:

1. **Domain-Isolated Retrieval Prevents Evidence Degradation:** Parallel department agents preserve specific precedent citations and quantitative constraints that single-agent prompts dilute.
2. **Specialist Agents Surface Latent Risks:** Department specialists produce a **+0.725 Risk Foresight advantage ($p = 0.0001$)**, identifying operational and contractual vulnerabilities.
3. **Empirical Honesty Over Over-Claiming:** By retracting prototype leakage artifacts and publishing real calibration bounds ($\hat{q} = 0.816$, abstention = $96.7\%$), MARS represents an honest, robust foundation for human-in-the-loop enterprise decision advisory.

---
*Report certified: 2026-11-02 | Evaluation Harness: `evaluation/eval_quality_experiment.py` | Statistical Scripts: `evaluation/compute_stats.py`*
