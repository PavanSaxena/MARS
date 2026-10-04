# MARS Standard Operating Procedure (SOP): Decision & Outcome Extraction & Verification

This document is the official standard operating procedure (SOP) for AI agents and human annotators extracting **evidence-grounded corporate decisions** and **empirically-verified later outcomes** from corporate disclosures (SEC Form 10-Q, 10-K, Press Releases, and Financial Statements) for the Multi-Agent Reasoning System (MARS) benchmark.

Any AI agent provided with this document, a target quarter ($Q_T$), and its corresponding primary documents must follow this procedure to produce 100% source-grounded, time-safe, and calibrated datasets.

---

## 1. Directory Structure & File Naming Conventions

All dataset files reside under `MARS/Dataset/` with the following standardized structure:

```text
MARS/Dataset/
├── Decisions/                         <-- Individual quarterly decision files (160 rows each)
│   ├── decisions_2023_q1.csv
│   ├── decisions_2023_q2.csv
│   ├── decisions_2023_q3.csv
│   └── decisions.csv                  <-- Cumulative master decisions file (all completed quarters)
│
├── Outcome/                           <-- Individual quarterly outcome files (160 rows each)
│   ├── outcomes_2023_q1.csv
│   ├── outcomes_2023_q2.csv
│   ├── outcomes_2023_q3.csv
│   └── outcomes.csv                   <-- Cumulative master outcomes file (all completed quarters)
│
├── Original/                          <-- Raw legacy datasets (26 uncalibrated columns, preserved)
│   ├── 2023-q1.csv, 2024-q1.csv ... 2025-q4.csv
│
├── quarterly_filings/                 <-- Primary SEC Form 10-Q and 10-K filings in PDF format
├── press_releases/                    <-- Primary quarterly earnings press releases in TXT format
├── consolidated_financial_statements/ <-- Consolidated balance sheets, income statements, cash flows
│
├── decisions_all_backup.csv           <-- Master reference backup (1,733 decisions across all quarters)
├── decisions.csv                      <-- Root-level mirror of master cumulative decisions
└── outcomes.csv                       <-- Root-level mirror of master cumulative outcomes
```

### Strict Naming Rules:
1. **No `verified_` prefix**: All new files are named `decisions_<YYYY>_<qx>.csv` and `outcomes_<YYYY>_<qx>.csv`.
2. **Quarterly vs. Cumulative**:
   - `decisions_<YYYY>_<qx>.csv` and `outcomes_<YYYY>_<qx>.csv` hold exactly the 160 rows of that specific quarter.
   - `decisions.csv` and `outcomes.csv` represent the **cumulative master dataset** combining all completed quarters (e.g. Q1 + Q2 + Q3 = 480 rows).

---

## 2. Core Operating Principles & Scale

1. **Local Filesystem Only**: Never write to external databases or cloud endpoints (e.g., Supabase) directly. Work exclusively with local CSV and JSON files in `MARS/Dataset/`.
2. **Dataset Scale Requirement**: **160 rows per quarter**
   - Each quarter must contain approximately 160 decision cases, distributed across the 4 corporate departments:
     - **Operations**: ~40 – 50 cases
     - **Finance**: ~40 – 45 cases
     - **R&D**: ~35 – 40 cases
     - **Legal & Compliance**: ~30 – 35 cases
   - Total cases per quarter: **160 rows** (aligned with benchmark evaluation suites).
3. **Primary Source Grounding for Decisions**: Every decision must be anchored in the primary disclosure documents for that quarter (Form 10-Q/10-K, Press Release, Financial Statements). The `source_excerpt` captures the explicit disclosure context, trigger, management action, and scope.
4. **Multi-Source Outcome Verification (Filings + Internet Lookups)**: Outcomes are not restricted to the target quarter's documents. An AI agent is **explicitly authorized and encouraged to look up the internet** as well as subsequent SEC filings across any future year and quarter. Agents may cross-reference:
   - Subsequent SEC Form 10-Q and 10-K filings ($Q_{T+1}$ through any future year).
   - Independent market and shipment research (e.g., IDC, Canalys, Counterpoint, TrendForce).
   - Regulatory and court dockets (e.g., European Commission decisions, U.S. DOJ complaints, ITC exclusion orders, Ninth Circuit/Supreme Court rulings).
   - Reputable industry investigations and financial reporting (e.g., Bloomberg, Reuters, Financial Times, Wall Street Journal).
5. **Strict Chronological Firewall**:
   $$\text{observation\_date} > \text{decision\_date}$$
   No information, outcome, or signal that occurred after the disclosure date of quarter $Q_T$ may appear in the decision record. Outcomes are stored in an entirely separate linked dataset and dated strictly after the decision.
6. **Cross-Functional Realism & Natural Calibration (With Realistic Variance)**:
   Corporate decision-making is fraught with risk, and business conditions fluctuate across quarters. A realistic dataset avoids survivorship bias (where only Legal experiences failures) and also avoids rigid artificial uniformity (not forced to an exact mathematical 30.0% across every single department).
   - Target failure rate band: **24% – 36% overall** (typically ~40–58 failures out of 160 rows).
   - **Departmental Variance**: Failure rates should naturally fluctuate by department and quarter (e.g., Operations might be 27.5%, Finance 25.0%, R&D 35.0%, Legal 32.5%), reflecting real-world variance in quarterly corporate exposure.
   - Failures must be distributed across **all four departments**, grounded in documented setbacks, market contractions, regulatory sanctions, or technical delays.
7. **Exact 1:1 Relational Alignment**: Every row in `decisions_<YYYY>_<qx>.csv` must have exactly one corresponding row in `outcomes_<YYYY>_<qx>.csv` matched by `case_id`.
8. **Strict Content Uniqueness (Zero Duplicate Excerpts)**: Every single row must have a unique decision title, unique primary source excerpt, and unique observation excerpt (`nunique() == len(df)`). Generic copy-paste templates and repeated text across batch iterations are strictly prohibited.
9. **Authentic Source Grounding & Anti-Fabrication**: Every excerpt must be grounded in verified primary filings (Form 10-Q/10-K sections, item/note citations) or public dockets/trackers (e.g. DOJ complaint, EC decision, ITC ruling, IDC/Canalys market report). Excerpts must state concrete empirical facts, dates, dollar amounts, and percentages rather than fabricated generic prose.
10. **Enriched Decision Depth Standard (Multi-Sentence Operational Detail)**:
    - Decisions must never be reduced to superficial 5-word summaries (e.g. avoiding *"Increase premium SKU production share by 4%"* or *"Supports EPS"*).
    - `decision_description` must be 2–4 complete sentences detailing concrete corporate parameters: product lines, assembly partners (Foxconn, Pegatron, Luxshare, TSMC, etc.), volume shifts, channels, and numerical goals.
    - `decision_rationale` must be 2–3 complete sentences explaining the underlying strategic economics, gross margin protection, risk mitigation, and trade-offs.
    - `quantitative_signals` must provide verified metrics, units, and dates from the official disclosures.
11. **Cross-Department Influence & Inter-Departmental Friction**:
    - Decisions never occur in departmental silos. A manufacturing shift by Operations affects Finance's CapEx and Legal's labor compliance; an App Store policy change by Legal directly impacts Services revenue and R&D engineering roadmaps.
    - Every decision must explicitly document its cross-functional ripple effects:
      - `cross_dept_impact`: Semicolon-delimited list of secondary departments affected (e.g. `Finance;Legal`, `Operations;R&D`).
      - `conflicting_perspectives`: A detailed, multi-sentence account of inter-departmental objections, financial/operational friction, and how executive management balanced competing departmental objectives.

---

## 3. How to Extract ~150–160 Decisions from a Quarter

A single quarterly disclosure report contains macro-level sections (MD&A, Notes 1–9, Risk Factors, Legal Proceedings). In enterprise management and decision science, each macro area encompasses multiple discrete decisions, operational parameter tunings, supplier allocations, geographic hedging positions, and compliance guidelines:

### Department Breakdown & Scope:

- **Operations & Supply Chain (~40–50 cases)**:
  - Manufacturing commitments: Long-term noncancelable purchase obligations ($55.1B), capacity reservations.
  - Assembly & Facility Operations: Zhengzhou capacity management, multi-partner outsourcing (Foxconn, Pegatron, Luxshare), India/Vietnam assembly diversification.
  - Inventory Optimization: 150-day demand forecast schedules, component buffer stock thresholds, finished goods vs. raw component balancing, warehouse inventory dwell-time rotations.
  - Distribution & Channels: Indirect retail channel fill controls post-launch, air-to-ocean freight transitions, certified refurbished dynamic pricing, fulfillment center consolidation.
  - Commercial Credit: Vendor non-trade receivables financing ($30.4B), customer credit support, third-party non-recourse lease financing.

- **Finance (~40–45 cases)**:
  - Capital Returns: Board-authorized share repurchase pacing ($19.0B), Rule 10b5-1 daily execution schedules, quarterly common stock dividend declarations ($0.23/share), annual dividend increase guidance.
  - Liquidity & Working Capital: Commercial paper program issuances ($1.7B), cash and cash equivalents allocations, capital expenditure budgeting.
  - Fixed-Rate Debt: Fixed-rate term debt management ($109.4B), maturity tranche structuring, credit rating maintenance.
  - Treasury & Risk Management: Foreign currency cash flow hedging designations (up to 12 months), interest rate derivative liability hedging, bilateral derivative collateral security posting thresholds, master netting agreements, unhedged emerging market currency policy.

- **Research & Development (R&D) (~35–40 cases)**:
  - Engineering Capital Allocation: R&D spending expansion, specialized engineering headcount growth.
  - Architecture & Silicon: Custom Apple Silicon development (M-series, A-series), spatial computing OS development (visionOS).
  - Platform & Scale: Infrastructure scaling to support 2+ billion active devices, iCloud end-to-end encryption layers (Advanced Data Protection).
  - Services Software Engineering: Cloud services expansion, App Store commerce APIs, Apple Music spatial audio infrastructure, MLS streaming rights infrastructure.
  - Product Mix Strategy: Hardware portfolio adjustments (prioritizing Apple Watch Ultra/Series 8 over AirPods refresh, M2 iPad Pro promotions in Greater China, localized software bundles in Japan and Rest of Asia Pacific).

- **Legal & Compliance (~30–35 cases)**:
  - Antitrust Litigation: Defending App Store guidelines against Epic Games Sherman Act claims, cross-appealing California UCL anti-steering injunctions, enforcing developer contract breach damages.
  - Regulatory Frameworks: EU Digital Markets Act gatekeeper compliance evaluations, App Tracking Transparency (ATT) responses to French CNIL and German Bundeskartellamt scrutiny.
  - Corporate Governance & Securities: Rule 10b5-1 trading plan compliance for repurchases, Board discretionary repurchase authorities.
  - Risk & Contingencies: ASC 450 material loss contingency assessments, SEC Regulation S-K risk factor disclosures, non-material ordinary course litigation settlements.

---

## 4. Schemas & Relational Data Contract

### 4.1 Decision Schema (`decisions_<YYYY>_<qx>.csv`)

| Column Name | Type | Format / Constraints | Description |
|---|---|---|---|
| `case_id` | String | `AAPL-<YYYY>Q<X>-<NNNN>` (e.g., `AAPL-2023Q1-0001` to `0160`) | Unique primary key across all quarters. |
| `company_name` | String | `Apple Inc.` | Standard corporate entity name. |
| `decision_date` | String | `YYYY-MM-DD` (e.g., `2023-02-02`) | Official filing/announcement date. |
| `source_document_id` | String | `quarterly_filings/<YYYY>_<QX>.pdf` | File path relative to `MARS/Dataset/`. |
| `source_url` | String | SEC EDGAR URL | Persistent URL to primary source. |
| `source_page_or_section` | String | e.g., `Item 2. Management\'s Discussion and Analysis - Operations` | Exact section within document. |
| `source_excerpt` | String | Disclosure Context quote with Trigger, Action, Scope, Rationale | Grounding excerpt from disclosure. |
| `decision_title` | String | Imperative/Gerund phrase (< 15 words) | Clear human-readable summary title. |
| `decision_description` | String | 2–4 complete sentences (typically > 120 chars) | Concrete operational action, specific product lines, assembly partners, channels, and volume/dollar parameters. |
| `documented_action` | String | Short verb phrase (e.g., `Partial redistribution`, `Increase allocation`) | Core documented action. |
| `action_type` | String | `expand` \| `reduce` \| `maintain` \| `investigate` \| `revise` \| `approve` \| `defer` \| `terminate` | Standard MARS action taxonomy. |
| `decision_rationale` | String | 2–3 complete sentences (typically > 80 chars) | Strategic economics, gross margin impact, risk trade-offs, and underlying causal mechanism. |
| `quantitative_signals` | JSON | Valid JSON array of objects `[{"name": "...", "value": "...", "unit": "...", "observed_on": "..."}]` | Concrete financial and operational metrics directly from filing. |
| `department` | String | `Operations` \| `Finance` \| `R&D` \| `Legal` | Department responsible. |
| `department_basis` | String | `reported` \| `inferred` | `reported` if stated; `inferred` if functional. |
| `tags` | String/JSON | Array or set format | Categorization tags. |
| `cross_dept_impact` | String | Semicolon-delimited departments (e.g., `Finance;Legal`) | Secondary departments impacted by the decision. |
| `conflicting_perspectives` | String | Multi-sentence narrative (> 100 chars) | Specific historical account of inter-departmental objections, trade-offs, and executive compromises. |

### 4.2 Outcome Schema (`outcomes_<YYYY>_<qx>.csv`)

| Column Name | Type | Format / Constraints | Description |
|---|---|---|---|
| `case_id` | String | Must match `case_id` from decision CSV | Foreign key linking 1:1 to decision record. |
| `outcome_label` | String | `success` \| `failure` | Calibrated ground-truth outcome label. |
| `observation_date` | String | `YYYY-MM-DD` (**Must be $> \text{decision\_date}$**) | Date of subsequent observation/filing. |
| `observation_source_docs` | String | e.g., `SEC Form 10-Q (2023_Q3); Bloomberg Intelligence` | Document where outcome was observed. |
| `observation_source_section` | String | e.g., `Item 2. MD&A - Products and Services Performance` | Specific section of observation document. |
| `observation_excerpt` | String | Concrete factual summary citing figures & dates | Specific empirical evidence documenting the result. |

---

## 5. Automated Validation & Quality Gates

Every generated quarter dataset must pass this automated test in Python before acceptance:

```python
import pandas as pd

def validate_quarter_dataset(dec_path, out_path):
    dec = pd.read_csv(dec_path)
    out = pd.read_csv(out_path)

    # 1. Target scale & 1:1 Case ID Alignment
    assert len(dec) == 160, f"Expected 160 rows, got {len(dec)}"
    assert len(dec) == len(out), f"Mismatch: {len(dec)} decisions vs {len(out)} outcomes"
    assert list(dec['case_id']) == list(out['case_id']), "Case IDs do not align 1:1 in exact order"
    
    # 2. No Null Values
    assert dec.isnull().sum().sum() == 0, f"Nulls found in decisions: {dec.isnull().sum().to_dict()}"
    assert out.isnull().sum().sum() == 0, f"Nulls found in outcomes: {out.isnull().sum().to_dict()}"

    # 3. Chronological Firewall
    merged = dec.merge(out, on='case_id')
    time_violations = merged[merged['observation_date'] <= merged['decision_date']]
    assert len(time_violations) == 0, f"Chronological violation in {len(time_violations)} rows!"

    # 4. Failure Rate Calibration Check (24% - 36%)
    fail_rate = (out['outcome_label'] == 'failure').mean()
    print(f"Overall Failure Rate: {fail_rate*100:.1f}% (Target Band: 24% - 36%)")
    assert 0.24 <= fail_rate <= 0.36, f"Failure rate {fail_rate:.2f} out of acceptable calibration bounds!"

    # 5. Department Distribution Check
    print("Departmental Distribution & Failure Rates:")
    for dept, group in merged.groupby('department'):
        dept_fails = (group['outcome_label'] == 'failure').sum()
        pct = (dept_fails / len(group)) * 100
        print(f"  {dept:12}: {dept_fails:2} fails / {len(group):2} total ({pct:.1f}%)")
        assert dept_fails > 0, f"Department {dept} has 0 failures! Survivorship bias detected."

    # 6. Strict Content Uniqueness Check (Zero Boilerplate / Zero Duplicate Excerpts)
    assert dec['decision_title'].nunique() == len(dec), f"Duplicate decision titles found: {len(dec) - dec['decision_title'].nunique()}"
    assert dec['source_excerpt'].nunique() == len(dec), f"Duplicate source excerpts found: {len(dec) - dec['source_excerpt'].nunique()}"
    assert out['observation_excerpt'].nunique() == len(out), f"Duplicate observation excerpts found: {len(out) - out['observation_excerpt'].nunique()}"

    # 7. Authentic Source Verification & Anti-Fabrication Check
    forbidden_generic_patterns = ["Operational initiative '", "Compliance initiative '", "Financial initiative '", "R&D program '"]
    for pattern in forbidden_generic_patterns:
        templated_count = out['observation_excerpt'].str.startswith(pattern).sum()
        assert templated_count == 0, f"Found {templated_count} templated generic excerpts starting with {pattern}!"

    # 8. Enriched Decision Depth Check
    assert (dec['decision_description'].str.len() >= 80).all(), "Found overly brief decision_description (< 80 chars)!"
    assert (dec['decision_rationale'].str.len() >= 50).all(), "Found overly brief decision_rationale (< 50 chars)!"
    assert dec['decision_description'].str.len().mean() >= 130, f"Mean decision_description length ({dec['decision_description'].str.len().mean():.1f}) below standard 130 chars!"

    # 9. Cross-Department Influence & Managerial Friction Check
    if 'cross_dept_impact' in dec.columns:
        assert dec['cross_dept_impact'].notnull().all(), "Null values detected in cross_dept_impact!"
        assert dec['conflicting_perspectives'].notnull().all(), "Null values detected in conflicting_perspectives!"
        assert dec['conflicting_perspectives'].nunique() == len(dec), "Duplicate conflicting_perspectives detected!"
        assert (dec['conflicting_perspectives'].str.len() >= 100).all(), "Overly brief conflicting_perspectives (< 100 chars)!"
        assert dec['conflicting_perspectives'].str.len().mean() >= 200, f"Mean conflicting_perspectives length ({dec['conflicting_perspectives'].str.len().mean():.1f}) below standard 200 chars!"

    print("\nALL QUALITY GATES PASSED SUCCESSFULLY!")
```

---

## 6. Execution Workflow for AI Agents

When assigned a target quarter (e.g. `2023_Q4`):
1. **Load Primary Disclosures**: Ingest the 10-Q/10-K PDF and press release text for that quarter.
2. **Decompose into 160 Cases**: Extract ~35–45 granular decision cases across Operations, Finance, R&D, and Legal from `decisions_all_backup.csv` or primary documents.
3. **Research Subsequent Reality (Filings + Internet Search)**: Search subsequent filings across any year/quarter AND look up the internet (industry market share trackers, regulatory agency rulings, court dockets, tech press investigations) to discover and confirm the real-world operational, financial, technical, or legal result of each decision.
4. **Calibrate Outcomes**: Assign ~24%–36% failures across each department grounded in real reported headwinds, category contractions, or regulatory sanctions, incorporating natural variance.
5. **Document Cross-Department Influence**: Detail secondary affected departments (`cross_dept_impact`) and articulate the authentic inter-departmental tensions and trade-offs (`conflicting_perspectives`).
6. **Save Outputs in Standard Folders**:
   - `MARS/Dataset/Decisions/decisions_<YYYY>_<qx>.csv`
   - `MARS/Dataset/Outcome/outcomes_<YYYY>_<qx>.csv`
7. **Update Cumulative Master Files**:
   - Concatenate all completed quarter files into `Decisions/decisions.csv` and `Outcome/outcomes.csv` (and mirror at root `decisions.csv` and `outcomes.csv`).
8. **Validate**: Run the quality gate test script to guarantee 100% compliance.

