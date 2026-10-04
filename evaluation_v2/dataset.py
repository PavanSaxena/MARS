"""Dataset loading, split manifests, and temporal access control for MARS.

This module is intentionally conservative: every evaluation should go through
these helpers so target cases, future decisions, and future outcomes are not
accidentally exposed to systems under test.
"""

from __future__ import annotations

import csv
import hashlib
import json
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
    """Load the paired decision/outcome corpus from the canonical CSV files."""
    decisions_path = dataset_dir / "decisions.csv"
    outcomes_path = dataset_dir / "outcomes.csv"
    if not decisions_path.exists():
        decisions_path = dataset_dir / "Decisions" / "decisions.csv"
    if not outcomes_path.exists():
        outcomes_path = dataset_dir / "Outcome" / "outcomes.csv"

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
    """Decision-time-only text suitable for query/document embeddings."""
    return "\n".join(
        part
        for part in [
            f"Title: {case.decision_title}",
            f"Description: {case.decision_description}",
            f"Action: {case.documented_action}",
            f"Rationale: {case.decision_rationale}",
            f"Department: {case.department}",
            f"Cross-department impact: {case.cross_dept_impact}",
            f"Conflicting perspectives: {case.conflicting_perspectives}",
        ]
        if part.split(": ", 1)[-1].strip()
    )


def replay_query_text(case: CaseRecord) -> str:
    """The query shown to systems in historical replay.

    It excludes the realized outcome and avoids using observation excerpts.
    """
    return (
        f"Department: {case.department}\n"
        f"Decision: {case.decision_title}\n"
        f"Context: {case.decision_description}\n"
        f"Known rationale at decision time: {case.decision_rationale}\n"
        f"Cross-department considerations: {case.cross_dept_impact}\n"
        f"Conflicting perspectives: {case.conflicting_perspectives}"
    ).strip()


def split_cases(
    cases: Sequence[CaseRecord],
    split_spec: Dict[str, Dict[str, str]] = DEFAULT_SPLIT_SPEC,
) -> Dict[str, List[CaseRecord]]:
    splits: Dict[str, List[CaseRecord]] = {name: [] for name in split_spec}
    for case in cases:
        for name, bounds in split_spec.items():
            if parse_date(bounds["start"]) <= case.decision_dt <= parse_date(bounds["end"]):
                splits[name].append(case)
                break
    return splits


def visible_corpus(
    cases: Sequence[CaseRecord],
    *,
    as_of_date: str | date,
    target_case_id: Optional[str] = None,
    include_visible_outcomes: bool = True,
) -> List[Dict[str, Any]]:
    """Return only records knowable at `as_of_date`.

    Decisions must strictly predate the query decision to avoid self-retrieval
    and same-day leakage. Outcomes are included only if their observation date
    is on or before `as_of_date`.
    """
    as_of = parse_date(as_of_date) if isinstance(as_of_date, str) else as_of_date
    rows: List[Dict[str, Any]] = []
    for case in cases:
        if target_case_id and case.case_id == target_case_id:
            continue
        if case.decision_dt >= as_of:
            continue

        row = asdict(case)
        row["decision_text"] = decision_text(case)
        row["outcome_visible"] = case.observation_dt <= as_of
        if not include_visible_outcomes or not row["outcome_visible"]:
            row["outcome_label"] = "unknown"
            row["observation_excerpt"] = ""
            row["observation_date"] = ""
        rows.append(row)
    return rows


def content_fingerprint(case: CaseRecord) -> str:
    text = " ".join(
        [
            case.decision_title.strip().lower(),
            case.decision_description.strip().lower(),
            case.documented_action.strip().lower(),
            case.decision_rationale.strip().lower(),
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
        "protocol": "MARS evaluation_v2 leakage-safe chronological split",
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


def _counts(values: Iterable[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for value in values:
        key = value or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))

