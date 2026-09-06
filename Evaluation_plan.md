# MARS Evaluation Framework & Baseline Benchmark (Literature-Grounded)

## Executive Summary & Academic Framing

The MARS (Multi-Agent Reasoning System) enterprise decision-support pipeline is evaluated on the completed 2023 empirical benchmark (640 verified decisions and 640 matched subsequent outcomes across Q1–Q4, spanning Finance, Operations, R&D, and Legal).

Per the research design and capstone objectives, **all baselines, evaluation protocols, and metrics are strictly grounded in peer-reviewed research papers published within the last 5 years (2021–2025/2026)** across NeurIPS, ICML, AAAI, EMNLP, EACL, and ICLR.

---

## 1. Recent Research Paper Foundations (5-Year Window: 2021–2025)

| Reference & Publication Venue | Core Finding & Method Adopted in MARS Evaluation |
|---|---|
| **Thakur et al. (NeurIPS 2021)**<br>*"BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models"* | Demonstrates that BM25 lexical search and standard dense vector embeddings (`Sentence-BERT`/`all-MiniLM-L6-v2`) are mandatory, non-trivial baselines for information retrieval. Establishes the standard evaluation metrics: **Recall@K**, **MRR**, and **nDCG@K**. |
| **Ru et al. (NeurIPS 2024)**<br>*"RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation"* (arXiv:2408.08067) | Decouples retrieval evaluation from generation evaluation. Introduces fine-grained diagnostics: claim recall, context precision, and factual faithfulness (groundedness vs. unsupported claim rate). |
| **Es et al. (EACL 2024 / arXiv 2023)**<br>*"RAGAS: Automated Evaluation of Retrieval Augmented Generation"* | Formalizes reference-free RAG metrics: context relevance, answer faithfulness, and factual precision, validating LLM-based evaluation metrics against human expert judges. |
| **Lee, Akatsuka, Vidyaratne, Kumar, Farahat, Gupta (AAAI-25)**<br>*"Reliable Decision-Making for Multi-Agent LLM Systems"* (arXiv:2406.04092) | Directly evaluates multi-agent decision reliability in enterprise settings. Formalizes the baseline taxonomy: **Single Agent Baseline vs. Aggregation vs. Spoke-and-Wheel (Master-Worker) Architectures**, proving that structured multi-agent coordination mitigates individual agent failure modes. |
| **Du, Li, Torralba, Tenenbaum, Mordatch (ICML 2024)**<br>*"Improving Factuality and Reasoning in Language Models through Multiagent Debate"* | Proves that multi-agent perspectives and consensus/arbitration dramatically reduce hallucination and enhance strategic cross-functional reasoning compared to single-agent prompts. |
| **Liu et al. (EMNLP 2023)**<br>*"G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment"* | Establishes the Chain-of-Thought (CoT) form-filling rubric framework for LLM-as-a-Judge, achieving Spearman $\rho > 0.51$ with expert human raters for multidimensional quality scoring. |
| **Pradeep, Caro-Martínez, Wijekoon (Expert Systems with Applications, 2024)**<br>*"A practical exploration of the convergence of Case-Based Reasoning and Explainable AI"* | Validates case retrieval and precedent reuse for transparent enterprise decisions and explainability trails. |

---

## 2. Formal Baseline Taxonomy (Retrieval & Generation)

Following **BEIR (NeurIPS 2021)** and **Lee et al. (AAAI-25)**, MARS is benchmarked against two rigorous baseline tiers:

### A. Retrieval Baselines
1. **Baseline R1: Lexical BM25 Retrieval** (Robertson & Zaragoza; Thakur et al., *BEIR*, NeurIPS 2021)
   - Exact term-frequency / inverse-document-frequency ranking over decision text.
   - Represents traditional enterprise search without neural semantics.
2. **Baseline R2: Naive Dense Vector Retrieval** (Reimers & Gurevych; Thakur et al., *BEIR*, NeurIPS 2021)
   - Flat cosine similarity over `all-MiniLM-L6-v2` embeddings across the unpartitioned case corpus.
   - Represents standard zero-shot neural semantic search without domain routing or cross-department expansion.
3. **Proposed: MARS Domain-Filtered Hybrid Retrieval + MMR Diversity**
   - Domain-specific routing + Cross-Department Impact expansion (`sql/004_cross_dept_retrieval.sql`) + Lexical re-ranking + Maximal Marginal Relevance (MMR) redundancy suppression.

### B. Generation & Multi-Agent Reasoning Baselines
1. **Baseline G1: Zero-Shot Single Agent (No Retrieval)** (Lee et al., *AAAI-25*; Du et al., *ICML 2024*)
   - Single generalist LLM prompt receiving only the decision situation/trigger.
   - Tests model performance relying solely on parametric pre-training weights without historical precedent.
2. **Baseline G2: Standard Naive RAG Single Agent** (Lewis et al., NeurIPS; Es et al., *RAGAS*, EACL 2024)
   - Single generalist LLM prompt receiving top-5 retrieved cases from Baseline R2.
   - Tests standard RAG without multi-agent domain specialization or conflict arbitration.
3. **Proposed: MARS Hierarchical Multi-Agent System**
   - 4 Domain Specialists (Finance, Operations, R&D, Legal) operating concurrently with domain-specific case evidence and MCP tools.
   - Master Aggregator synthesizing inter-departmental tensions, resolving conflicting perspectives, and enforcing hard constraints.

---

## 3. Evaluation Metrics & Mathematical Formulations

### A. Retrieval Metrics (BEIR / RAGChecker Standard)
- **Recall@K (Hit@K, $K \in \{1, 3, 5\}$)**:
  $$\text{Recall@}K = \frac{1}{|Q|} \sum_{q \in Q} \mathbb{I}(\text{target\_case} \in \text{Top-}K)$$
- **Mean Reciprocal Rank (MRR)**:
  $$\text{MRR} = \frac{1}{|Q|} \sum_{q \in Q} \frac{1}{\text{rank}(\text{target\_case})}$$
- **nDCG@5 (Normalized Discounted Cumulative Gain)**:
  $$\text{DCG@5} = \sum_{i=1}^{5} \frac{2^{\text{rel}_i} - 1}{\log_2(i + 1)}, \quad \text{nDCG@5} = \frac{\text{DCG@5}}{\text{IDCG@5}}$$
  Graded relevance: Exact target precedent = 3, same department & topic = 2, same department = 1, unrelated = 0.
- **Cross-Department Retrieval Recall**:
  For cases documenting cross-functional impact ($\text{cross\_dept\_impact} \neq \emptyset$), the fraction of retrieved sets containing relevant cases from the impacted external department.
- **Department Routing Precision**:
  Fraction of retrieved cases aligned with the querying agent's operational domain.

### B. Generation & Reasoning Metrics (RAGAS / G-Eval / AAAI-25 Standard)
- **Documented Action Agreement (Accuracy & Macro-F1)** (Lee et al., *AAAI-25*):
  Measures classification agreement between generated action and Apple's historical executed action (`approve`, `expand`, `reduce`, `defer`, `revise`, `investigate`, `reject`).
- **Cross-Functional Conflict Awareness Score ($0.0 - 1.0$)** (Du et al., *ICML 2024*):
  Evaluates whether the system detects and explicitly addresses authentic departmental trade-offs (e.g., Finance CapEx vs. Operations backlog; Legal regulatory liability vs. R&D feature deployment) documented in ground-truth `conflicting_perspectives`.
- **Factual Faithfulness & Grounding (1–5 Rubric)** (Es et al., *RAGAS*, EACL 2024; Liu et al., *G-Eval*, EMNLP 2023):
  CoT-evaluated score verifying that claims, metrics, and quantitative signals are grounded in retrieved precedent rather than hallucinated.
  $$\text{Unsupported Claim Rate} = \frac{\text{unsupported claims}}{\text{total factual claims}}$$
- **Outcome Risk Foresight on Failure Cases** (Lee et al., *AAAI-25*):
  For episodes where historical outcomes resulted in failure (`outcome_label = 'failure'`), does the system articulate the relevant risk factors and recommend caution?
  $$\text{Risk Foresight Rate} = \frac{\text{Failures correctly flagged with high risk / conditions}}{\text{Total historical failure cases}}$$

---

## 4. Work Breakdown & Implementation Plan

### Component 1: Evaluation Benchmark Data Loader
#### [NEW] [benchmark_dataset.py](file:///home/harshith/Documents/Capstone/MARS/evaluation/benchmark_dataset.py)
- Loads 2023 verified dataset (640 decisions and 640 outcomes across Q1–Q4).
- Implements strict **time-safe chronological splits** (Phase 3 of `MARS_DATA_AND_SUCCESS_PLAN.md`): cases from Q2, Q3, Q4 only query cases dated $\le$ cutoff date.
- Creates:
  1. Full Retrieval Benchmark (640 queries with target cases and cross-department annotations).
  2. Stratified Generation Benchmark (40 representative cases: 10 per department across Q1–Q4, balanced across Success and Failure outcomes).

### Component 2: Retrieval Evaluation Engine
#### [NEW] [eval_retrieval.py](file:///home/harshith/Documents/Capstone/MARS/evaluation/eval_retrieval.py)
- Implements Baseline R1 (BM25), Baseline R2 (Naive Vector), and MARS Hybrid Retrieval.
- Computes Recall@1, Recall@3, Recall@5, MRR, nDCG@5, Department Accuracy, and Cross-Dept Recall.
- Records query latencies.

### Component 3: Generation & Reasoning Evaluation Engine
#### [NEW] [eval_generation.py](file:///home/harshith/Documents/Capstone/MARS/evaluation/eval_generation.py)
- Executes Baseline G1 (Zero-Shot), Baseline G2 (Naive RAG), and MARS Multi-Agent on the stratified benchmark set.
- Implements G-Eval CoT Judge (`app.agents.common:get_llm`) with deterministic JSON schema scoring:
  - Action alignment classification.
  - Conflict awareness (0–1).
  - Grounding & citation faithfulness (1–5).
  - Risk anticipation flag.

### Component 4: Unified CLI Runner & Benchmark Reporter
#### [NEW] [run_benchmark.py](file:///home/harshith/Documents/Capstone/MARS/evaluation/run_benchmark.py)
- Executes benchmarks with `--mode retrieval`, `--mode generation`, or `--mode all`.
- Generates:
  - `MARS/evaluation/results/retrieval_results.json`
  - `MARS/evaluation/results/generation_results.json`
  - `MARS/evaluation/BENCHMARK_REPORT.md` containing formatted markdown tables, LaTeX table snippets for the Capstone Phase 3 presentation/report, and analytical commentary.

---

## Verification Plan

1. **Dry Run**: Run retrieval evaluation on 20 queries and generation evaluation on 4 queries (1 per department) to confirm zero runtime errors, valid JSON parsing, and proper metric calculations.
2. **Full Retrieval Run**: Run across all 640 cases in the 2023 dataset to establish definitive empirical metrics for BM25 vs Naive Vector vs MARS Hybrid.
3. **Stratified Generation Run**: Run across the 40 stratified benchmark cases for Baseline G1, Baseline G2, and MARS Multi-Agent.
4. **Report Inspection**: Verify `BENCHMARK_REPORT.md` contains complete comparison tables and literature citations.
