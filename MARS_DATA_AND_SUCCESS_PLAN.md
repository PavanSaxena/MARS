# MARS Data, Confidence, and Success-Prediction Plan

## Status and purpose

**This is a planning document only.** No pipeline, backend, CSV, database, or model change is approved until the team reviews the decision gates in this plan.

MARS will be an evidence-grounded, multi-agent decision-support system that recommends the action **historically most associated with success in comparable earlier cases**. It must never claim to guarantee success or claim a causal effect that the observational data cannot prove.

## Final architecture

```text
Verified decision facts ─┐
                         ├─> MARS recommendation
Verified later outcomes ─┤       ├─ cited evidence and constraints
                         │       ├─ evidence status / escalation
Runtime MARS logs ───────┘       └─ calibrated success probability (future phase)
```

The three layers have different purposes:

- **Verified decision facts:** retrieval and reasoning available at decision time.
- **Verified later outcomes:** training and evaluation labels only; never shown to MARS when it makes a historical replay decision.
- **Runtime logs:** MARS's own recommendations, citations, conflicts, and evidence status. They are not historical facts and must not be mixed into the corpus.

## Core decisions

1. Preserve only verifiable real-world facts in the decision corpus.
2. Keep later outcomes in a separate linked dataset.
3. Do not use the old `w1 × similarity + w2 × recency + w3 × past_success` formula.
4. Do not ask LLM agents for percentage confidence or rank agents by self-reported confidence.
5. Use an evidence profile and selective escalation immediately.
6. Add a calibrated success probability only after enough independently verified success/failure labels exist.
7. Apply source-backed hard constraints before preference trade-offs; legal or compliance blockers cannot be outvoted.

## Phase 0 — Freeze and audit current material

The existing CSVs and generator remain unchanged during this phase. Treat them as **legacy/unverified** until every row is audited.

For every row, record:

- direct primary source and exact page/section;
- whether the action is explicitly disclosed;
- whether every factual field is source-supported;
- whether later outcome evidence exists;
- whether a second reviewer verified it.

Count usable decisions, known successes, known failures, unresolved outcomes, departments, and action types. Do not start outcome prediction until this audit shows that enough genuine labels exist.

## Phase 1 — Define the data contracts

### A. Verified decision corpus

| Field | Requirement and reason |
|---|---|
| `case_id` | Globally unique ID; links decision, outcome, review, and runtime records. |
| `company_name` | Exact organisation; prevents cross-company confusion. |
| `decision_date` | Disclosure/action date; enables time-safe retrieval. |
| `source_document_id`, `source_url` | Durable provenance and independent verification. |
| `source_page_or_section` | Exact evidence location. |
| `source_excerpt` | Full verbatim text; primary grounding evidence. |
| `decision_title`, `decision_description` | Concise annotations for retrieval; clearly marked as annotated, not quotes. |
| `documented_action` | Action explicitly disclosed in the source. |
| `action_type` | Predefined label such as `approve`, `expand`, `reduce`, `defer`, `revise`, `investigate`, or `reject`; enables consistent evaluation. |
| `decision_rationale` | Retain only when directly supported by the source. |
| `quantitative_signals` | Exact values, units, and dates from the source. |
| `department`, `department_basis` | Department plus `reported` or `inferred`, so inferences are visible. |
| `tags` | Optional retrieval annotations. |
| `annotation_status`, `annotator_id`, `reviewer_id` | Audit trail and independent review. |

### B. Verified outcome corpus

Outcomes are not decision-time evidence. Each later outcome record must contain:

- `outcome_id` and linked `case_id`;
- observation date;
- source document ID, URL, page/section, and exact excerpt;
- pre-defined success criterion and time window;
- observed result;
- `success`, `failure`, or `unresolved` label;
- annotator and independent reviewer.

`unresolved` is never converted into failure. An outcome record must be dated after its linked decision.

### C. Fields excluded from the verified decision corpus

| Excluded field | Reason |
|---|---|
| Agent/master confidence fields | Prompted or heuristic values are neither real employee assessments nor calibrated model probabilities. |
| `master_agent_decision` | MARS output is not a historical source fact. |
| `profit_confidence` | The current pipeline derives it from heuristics rather than evidence. |
| Generated `conflicting_perspectives` | Keep only source-cited disagreements; do not manufacture cross-functional conflict. |
| Forced `options_considered` | Public disclosures rarely provide an exhaustive three-option menu. |
| Predicted profit impact/pathway | These are forecasts or causal stories unless directly sourced. |
| Outcome text in the decision corpus | It leaks future information into retrieval and historical replay. |
| Inferred risk level | Retain only if explicitly defined by the source. |

## Phase 2 — Annotation and verification workflow

1. Extract only explicitly disclosed actions from primary sources.
2. Preserve the complete exact excerpt and location; never truncate or invent text.
3. Annotate source-supported summaries, action type, and department basis.
4. A second reviewer checks every fact before status becomes `verified`.
5. Add later outcome evidence separately, using the pre-approved criterion.
6. Reject rows with no source, no explicit action, generated/default text, or unresolved provenance.

### Success criteria

Define criteria before outcome labelling. Examples:

- Finance: stated cash-flow, cost, margin, or capital target met in its stated window.
- Operations: delivery, capacity, quality, or cost target met.
- Legal: compliance achieved or no material adverse event within a defined window.
- R&D: stated technical, quality, safety, adoption, or milestone target met.

Do not use a generic `Success` label without a criterion, time window, observed result, and source.

## Phase 3 — Time-safe benchmark

The evaluation question is:

> Given only information available before a documented decision, does MARS retrieve relevant precedent, provide grounded reasoning, and recommend an action associated with success in comparable earlier cases?

For each benchmark case:

1. Set a cutoff immediately before the documented action.
2. Build a scenario packet only from documents published before the cutoff.
3. Hide the later documented action and later outcome.
4. Retrieve only decision cases dated before the cutoff.
5. Use the hidden action for action-agreement evaluation and the hidden outcome for success-prediction evaluation.

Use chronological development, calibration, and untouched final-test splits; never random-split across time. Stratify the final test set by department and action type where sample sizes permit.

## Phase 4 — MARS output and arbitration

Each department agent must return:

- proposed action;
- cited decision/source IDs;
- material assumptions;
- constraints and risks; and
- an `insufficient_evidence` flag.

The master agent should inspect recommendation, citations, constraints, and conflicts. It must apply hard constraints first. Example: three domains may support launch, but a source-backed legal prohibition requires delay until resolved.

This is reasoning-based arbitration, not majority voting and not confidence-weighted voting.

## Confidence: immediate evidence status

Do not display an unsupported percentage. Display one status:

| Status | Rule | System behaviour |
|---|---|---|
| `supported` | Decisive claims have primary-source support, evidence does not materially conflict, and no required agent lacks evidence. | Show recommendation, citations, assumptions, and constraints. |
| `conflicting evidence` | Cited evidence or agent constraints support incompatible material actions. | Explain trade-off and ask for a human decision where policy cannot resolve it. |
| `insufficient evidence — human review required` | A decisive claim is unsupported, relevant retrieval fails, a required domain has no evidence, or the source is ambiguous. | Do not make a definitive recommendation; request missing evidence or escalate. |

The profile can show relevance, retrieval coverage, metadata match, diversity, recency, novelty, citation coverage, claim support, repeated-run stability, and disagreement. These are diagnostic signals, not a probability until calibrated.

## Phase 5 — Baselines and evaluation

Run the same time-safe benchmark through:

1. one LLM without retrieval;
2. one LLM with retrieval;
3. full MARS with department agents and master arbitration.

### Retrieval metrics

- **Recall@5:** proportion of queries with a labelled relevant case in the top five.
- **MRR:** average reciprocal rank of the first relevant case.
- **nDCG@5:** ranking quality where fully relevant and partially relevant cases receive different gains.

### Recommendation metrics

- documented-action agreement: accuracy, macro-F1, and confusion matrix;
- clearly describe this as agreement with historical action, not proof the original action was optimal.

### Grounding and expert review

Blind reviewers score factual grounding, citation correctness, relevance, cross-functional reasoning, actionability, and safety on a 1–5 rubric. Mark each factual claim as supported, partially supported, or unsupported.

Report citation-support precision, citation coverage, unsupported-claim rate, rubric summaries, and inter-rater agreement. Use Cohen's kappa for two categorical reviewers, Fleiss' kappa for three or more categorical reviewers, and ordinal agreement measures for 1–5 scoring.

### Escalation metrics

Have independent reviewers label each output as `supported`, `conflicting`, or `insufficient`. Report macro-F1, referral precision/recall, conflict-detection precision/recall, and:

```text
unsafe automation rate = reviewer-insufficient cases labelled supported by MARS
                         -----------------------------------------------------
                         all reviewer-insufficient cases
```

Perform error analysis for retrieval misses, extraction errors, unsupported claims, wrong action mapping, missed hard constraints, unresolved conflicts, inappropriate escalation, and ambiguous evidence.

## Phase 6 — Outcome prediction and calibrated success confidence

Begin this phase only after enough verified `success` and `failure` labels exist for the selected scope.

For historical replay, compute only pre-cutoff features: action type, source-supported context, retrieval relevance, evidence coverage, conflict flags, and repeated-run stability. Train an interpretable baseline to estimate:

```text
P(success | scenario, proposed action, comparable earlier cases)
```

Fit probability calibration on a separate chronological calibration set. Evaluate once on the untouched final test set with:

- AUROC and PR-AUC for discrimination;
- Brier score for probability error;
- Expected Calibration Error and reliability diagram for calibration;
- risk-versus-coverage curve for selective prediction.

The displayed percentage, if approved later, means:

> Estimated probability of success according to comparable historical, verified cases.

It does not prove that MARS caused success or that an unobserved alternative would have failed. Conformal prediction is deferred because it also requires labelled calibration examples and a clear target label.

## Implementation sequence after approval

1. Audit legacy data and approve scope.
2. Add decision/outcome contracts and validators.
3. Update extraction to require source provenance and emit `null`, not synthetic defaults.
4. Add human review workflow.
5. Update retrieval with date cutoff and outcome exclusion.
6. Replace confidence-weighted aggregation with evidence/constraint arbitration.
7. Build benchmark runner and baseline comparison.
8. Add success model and calibration only after label-quality gate passes.

## Risks and controls

| Risk | Control |
|---|---|
| Synthetic data presented as factual | Separate legacy data; require source and reviewer for verified rows. |
| Future information leakage | Enforce a date cutoff and exclude outcomes from retrieval. |
| Too few failures | Report class counts/PR-AUC and defer numeric success probability. |
| External causes influence outcomes | Use association language, not causal guarantees. |
| Important legal dissent is outvoted | Treat cited legal/compliance constraints as hard blockers. |
| MARS learns from its own mistakes | Retain only independently verified organisational decisions and outcomes. |

## Approval checklist

- [ ] Goal wording approved.
- [ ] Action taxonomy approved.
- [ ] Department/action success criteria and windows approved.
- [ ] Source and second-review standard approved.
- [ ] Initial company and decision-type scope approved.
- [ ] Legacy-data audit complete.
- [ ] Benchmark protocol approved.
- [ ] Team authorises implementation beginning with the data contracts.

## References

- Angelopoulos, A. N., & Bates, S. (2021). *A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification*. https://arxiv.org/abs/2107.07511
- Xiong, M. et al. (2024). *Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs*. https://arxiv.org/abs/2306.13063
- Es, S. et al. (2023). *RAGAS: Automated Evaluation of Retrieval Augmented Generation*. https://arxiv.org/abs/2309.15217
- Ru, D. et al. (2024). *RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation*. https://arxiv.org/abs/2408.08067
- Gebru, T. et al. (2018). *Datasheets for Datasets*. https://arxiv.org/abs/1803.09010
