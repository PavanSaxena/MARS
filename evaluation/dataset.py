"""Dataset loading, split manifests, and temporal access control for MARS.

This module provides unified access to both:
1. Canonical multi-year decisions & outcomes (2,080 cases across 2023-2026) with
   strict time-safe chronological splitting and leakage-safe corpus access.
2. Verified 2023 benchmark dataset (640 paired cases across 4 departments and 4 quarters)
   and balanced stratified generation sampling.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "dataset"
DEFAULT_SPLIT_SPEC = {
    "train": {"start": "2023-01-01", "end": "2024-12-31"},
    "validation": {"start": "2025-01-01", "end": "2025-06-30"},
    "test": {"start": "2025-07-01", "end": "2026-03-31"},
}


@dataclass(frozen=True)
class CaseRecord:
    case_id: str
    company_name: str
    decision_date: str
    department: str
    action_type: str
    decision_title: str
    decision_description: str
    documented_action: str
    decision_rationale: str
    quantitative_signals: str
    cross_dept_impact: str
    conflicting_perspectives: str
    source_document_id: str
    source_url: str
    source_page_or_section: str
    source_excerpt: str
    outcome_label: str
    observation_date: str
    observation_source_docs: str
    observation_source_section: str
    observation_excerpt: str

    @property
    def decision_dt(self) -> date:
        return parse_date(self.decision_date)

    @property
    def observation_dt(self) -> date:
        return parse_date(self.observation_date)

    @property
    def outcome_binary(self) -> int:
        return 1 if self.outcome_label.lower() == "success" else 0


def parse_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def load_cases(dataset_dir: Path = DATASET_DIR) -> List[CaseRecord]:
    """Load the paired decision/outcome corpus from canonical CSV files."""
    decisions_path = dataset_dir / "decisions.csv"
    outcomes_path = dataset_dir / "outcomes.csv"
    if not decisions_path.exists():
        decisions_path = dataset_dir / "Decisions" / "decisions.csv"
    if not outcomes_path.exists():
        outcomes_path = dataset_dir / "Outcome" / "outcomes.csv"

    if not decisions_path.exists() or not outcomes_path.exists():
        raise FileNotFoundError(f"Missing dataset files in {dataset_dir}: decisions.csv / outcomes.csv")

    with decisions_path.open("r", encoding="utf-8") as f:
        decisions = list(csv.DictReader(f))
    with outcomes_path.open("r", encoding="utf-8") as f:
        outcomes = {row["case_id"]: row for row in csv.DictReader(f)}

    cases: List[CaseRecord] = []
    for d in decisions:
        o = outcomes.get(d["case_id"])
        if not o:
            continue
        cases.append(
            CaseRecord(
                case_id=d["case_id"],
                company_name=d.get("company_name", ""),
                decision_date=d.get("decision_date", ""),
                department=d.get("department", ""),
                action_type=d.get("action_type", ""),
                decision_title=d.get("decision_title", ""),
                decision_description=d.get("decision_description", ""),
                documented_action=d.get("documented_action", ""),
                decision_rationale=d.get("decision_rationale", ""),
                quantitative_signals=d.get("quantitative_signals", ""),
                cross_dept_impact=d.get("cross_dept_impact", ""),
                conflicting_perspectives=d.get("conflicting_perspectives", ""),
                source_document_id=d.get("source_document_id", ""),
                source_url=d.get("source_url", ""),
                source_page_or_section=d.get("source_page_or_section", ""),
                source_excerpt=d.get("source_excerpt", ""),
                outcome_label=o.get("outcome_label", ""),
                observation_date=o.get("observation_date", ""),
                observation_source_docs=o.get("observation_source_docs", ""),
                observation_source_section=o.get("observation_source_section", ""),
                observation_excerpt=o.get("observation_excerpt", ""),
            )
        )
    return sorted(cases, key=lambda c: (c.decision_dt, c.case_id))


def decision_text(case: CaseRecord) -> str:
    """Decision-time text representation suitable for retrieval."""
    parts = [
        f"Title: {case.decision_title}",
        f"Department: {case.department}",
        f"Action Type: {case.action_type}",
        f"Description: {case.decision_description}",
        f"Documented Action: {case.documented_action}",
        f"Rationale: {case.decision_rationale}",
    ]
    if case.quantitative_signals:
        parts.append(f"Signals: {case.quantitative_signals}")
    if case.cross_dept_impact:
        parts.append(f"Cross-Dept Impact: {case.cross_dept_impact}")
    if case.conflicting_perspectives:
        parts.append(f"Conflicting Perspectives: {case.conflicting_perspectives}")
    return "\n".join(parts)


def replay_query_text(case: CaseRecord) -> str:
    """Query text simulating an executive advisory request at decision time."""
    parts = [
        f"Decision Inquiry: {case.decision_title}",
        f"Department Context: {case.department} ({case.action_type})",
        f"Background: {case.decision_description}",
    ]
    if case.cross_dept_impact:
        parts.append(f"Anticipated Organizational Impact: {case.cross_dept_impact}")
    if case.conflicting_perspectives:
        parts.append(f"Stakeholder Tension: {case.conflicting_perspectives}")
    return "\n".join(parts)


def split_cases(
    cases: Sequence[CaseRecord],
    split_spec: Dict[str, Dict[str, str]] = DEFAULT_SPLIT_SPEC,
) -> Dict[str, List[CaseRecord]]:
    """Partition cases into train, validation, and test splits by decision_date."""
    parsed_spec = {
        name: (parse_date(bounds["start"]), parse_date(bounds["end"]))
        for name, bounds in split_spec.items()
    }
    assigned: Dict[str, List[CaseRecord]] = {name: [] for name in split_spec}
    for case in cases:
        dt = case.decision_dt
        for name, (start, end) in parsed_spec.items():
            if start <= dt <= end:
                assigned[name].append(case)
                break
    return assigned


def visible_corpus(
    cases: Sequence[CaseRecord],
    *,
    as_of_date: str | date,
    target_case_id: str | None = None,
    include_visible_outcomes: bool = True,
) -> List[Dict[str, Any]]:
    """Return only precedent cases strictly knowable before as_of_date."""
    ref_dt = parse_date(as_of_date) if isinstance(as_of_date, str) else as_of_date
    corpus = []
    for case in cases:
        if target_case_id and case.case_id == target_case_id:
            continue
        if case.decision_dt >= ref_dt:
            continue

        item = asdict(case)
        item["decision_text"] = decision_text(case)

        # Censor future outcomes
        outcome_visible = include_visible_outcomes and (case.observation_dt <= ref_dt)
        item["outcome_visible"] = outcome_visible
        if not outcome_visible:
            item["outcome_label"] = ""
            item["observation_date"] = ""
            item["observation_excerpt"] = ""
            item["observation_source_docs"] = ""
            item["observation_source_section"] = ""
        corpus.append(item)
    return corpus


def content_fingerprint(case: CaseRecord) -> str:
    text = " | ".join(
        [
            case.department.strip().lower(),
            case.action_type.strip().lower(),
            case.decision_title.strip().lower(),
            case.decision_description.strip().lower(),
            case.documented_action.strip().lower(),
        ]
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def audit_dataset(cases: Sequence[CaseRecord]) -> Dict[str, Any]:
    case_ids: Dict[str, int] = {}
    fingerprints: Dict[str, List[str]] = {}
    chronology_violations = []
    for case in cases:
        case_ids[case.case_id] = case_ids.get(case.case_id, 0) + 1
        fingerprints.setdefault(content_fingerprint(case), []).append(case.case_id)
        if case.observation_dt <= case.decision_dt:
            chronology_violations.append(
                {
                    "case_id": case.case_id,
                    "decision_date": case.decision_date,
                    "observation_date": case.observation_date,
                }
            )

    duplicate_case_ids = {cid: n for cid, n in case_ids.items() if n > 1}
    duplicate_content = [ids for ids in fingerprints.values() if len(ids) > 1]

    return {
        "total_cases": len(cases),
        "duplicate_case_ids": duplicate_case_ids,
        "duplicate_content_groups": duplicate_content,
        "chronology_violations": chronology_violations,
        "outcome_counts": _counts(case.outcome_label for case in cases),
        "department_counts": _counts(case.department for case in cases),
        "action_counts": _counts(case.action_type for case in cases),
    }


def build_split_manifest(
    cases: Sequence[CaseRecord],
    output_path: Path,
    split_spec: Dict[str, Dict[str, str]] = DEFAULT_SPLIT_SPEC,
) -> Dict[str, Any]:
    splits = split_cases(cases, split_spec)
    manifest = {
        "protocol": "MARS leakage-safe chronological split",
        "rules": [
            "Training/calibration/test assignment is based on decision_date.",
            "Replay retrieval must exclude the target case.",
            "Replay retrieval must exclude decisions with decision_date >= query decision_date.",
            "Outcome text/labels may be used only when observation_date <= query decision_date.",
        ],
        "split_spec": split_spec,
        "splits": {
            name: {
                "n": len(rows),
                "case_ids": [case.case_id for case in rows],
                "date_min": min((case.decision_date for case in rows), default=None),
                "date_max": max((case.decision_date for case in rows), default=None),
            }
            for name, rows in splits.items()
        },
        "audit": audit_dataset(cases),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


# =============================================================================
# Verified 2023 Benchmark Dataset Loaders
# =============================================================================

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

            q_sig = d.get("quantitative_signals")
            parsed_signals = []
            if q_sig and isinstance(q_sig, str) and (q_sig.startswith("[") or q_sig.startswith("{")):
                try:
                    parsed_signals = json.loads(q_sig)
                except Exception:
                    parsed_signals = []

            title = d.get("decision_title", "")
            desc = d.get("decision_description", "")
            rationale = d.get("decision_rationale", "")
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
    """Select a balanced stratified sample across all 4 departments and 4 quarters."""
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


def _counts(values: Iterable[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for value in values:
        key = value or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Dataset utilities and split manifest generation.")
    parser.add_argument(
        "--build-manifest",
        action="store_true",
        help="Generate the chronological split manifest in evaluation/artifacts/split_manifest.json",
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "evaluation" / "artifacts" / "split_manifest.json"),
        help="Output path for split manifest JSON.",
    )
    args = parser.parse_args()

    cases = load_cases()
    print(f"Loaded {len(cases)} paired cases from {DATASET_DIR}")
    manifest = build_split_manifest(cases, Path(args.output))
    print(json.dumps({
        "output": args.output,
        "total_cases": manifest["audit"]["total_cases"],
        "splits": {name: data["n"] for name, data in manifest["splits"].items()},
        "chronology_violations": len(manifest["audit"]["chronology_violations"]),
        "duplicate_case_ids": len(manifest["audit"]["duplicate_case_ids"]),
    }, indent=2))


if __name__ == "__main__":
    main()
