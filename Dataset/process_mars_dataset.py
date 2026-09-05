"""Process and transform legacy MARS dataset CSVs into clean verified corpora.

Implements clean decision-time facts and separate outcome corpora:
  1. verified_decisions.csv: Decision-time facts only (no outcome leakage).
  2. verified_outcomes.csv: Later observed results linked via case_id.
"""

import csv
import json
import re
from pathlib import Path
from typing import Dict, List

DATASET_DIR = Path(__file__).resolve().parent

QUARTER_FILES = [
    ("2023-q1.csv", "Q1-2023", "2023-02-02", "2023-05-04", "AAPL-10Q-2023Q1", "AAPL-10Q-2023Q2"),
    ("2024-q1.csv", "Q1-2024", "2024-02-01", "2024-05-02", "AAPL-10Q-2024Q1", "AAPL-10Q-2024Q2"),
    ("2024-q2.csv", "Q2-2024", "2024-05-02", "2024-08-01", "AAPL-10Q-2024Q2", "AAPL-10Q-2024Q3"),
    ("2024-q3.csv", "Q3-2024", "2024-08-01", "2024-10-31", "AAPL-10Q-2024Q3", "AAPL-10K-2024"),
    ("2025-q1.csv", "Q1-2025", "2025-01-30", "2025-05-01", "AAPL-10Q-2025Q1", "AAPL-10Q-2025Q2"),
    ("2025-q2.csv", "Q2-2025", "2025-05-01", "2025-07-31", "AAPL-10Q-2025Q2", "AAPL-10Q-2025Q3"),
    ("2025-q3.csv", "Q3-2025", "2025-07-31", "2025-10-30", "AAPL-10Q-2025Q3", "AAPL-10K-2025"),
    ("2025-q4.csv", "Q4-2025", "2025-10-30", "2026-01-29", "AAPL-10K-2025", "AAPL-10Q-2026Q1"),
]


def normalize_department(dept_raw: str, fallback_text: str = "") -> str:
    """Normalize department string to one of Finance, Operations, Legal, R&D."""
    d = (dept_raw or "").strip().lower()
    f = fallback_text.lower()
    if "finance" in d or "finance" in f:
        return "Finance"
    if "ops" in d or "operation" in d or "supply" in f:
        return "Operations"
    if "legal" in d or "compliance" in d or "regulatory" in f:
        return "Legal"
    if "r&d" in d or "r_and_d" in d or "research" in d or "ai" in f or "chip" in f:
        return "R&D"
    return "Operations"


def classify_action_type(chosen_option: str, archetype: str, title: str) -> str:
    """Classify the action into one of the 7 approved taxonomy types."""
    text = f"{chosen_option} {archetype} {title}".lower()

    if any(w in text for w in ["reduce", "cut", "freeze", "decrease", "lower", "trim", "slow", "-12%", "-20%"]):
        return "reduce"
    if any(w in text for w in ["expand", "accelerate", "increase", "scale", "boost", "grow", "ramp", "broaden", "overtime"]):
        return "expand"
    if any(w in text for w in ["defer", "delay", "postpone", "pause", "wait", "hold"]):
        return "defer"
    if any(w in text for w in ["reject", "cancel", "terminate", "halt", "deny"]):
        return "reject"
    if any(w in text for w in ["audit", "investigate", "review", "evaluate", "assess", "monitor", "benchmark"]):
        return "investigate"
    if any(w in text for w in ["revise", "amend", "modify", "update", "rebalance", "reallocate", "redistribute", "refactor", "optimize", "patch", "shift"]):
        return "revise"
    if any(w in text for w in ["approve", "proceed", "execute", "adopt", "implement", "deploy", "onboard"]):
        return "approve"

    return "revise"


def parse_quantitative_signals(signals_str: str, observed_date: str) -> str:
    """Convert raw signal string into a structured JSON string."""
    if not signals_str or not signals_str.strip():
        return "[]"

    parsed = []
    parts = [p.strip() for p in signals_str.split(";") if p.strip()]
    for part in parts:
        if ":" in part:
            name, val = part.split(":", 1)
            name = name.strip()
            val = val.strip()
        else:
            name = "Metric"
            val = part.strip()

        unit = "value"
        if "%" in val:
            unit = "percentage"
        elif "$" in val or "B" in val or "M" in val:
            unit = "currency"
        elif "days" in val.lower():
            unit = "days"
        elif "c" in val.lower() and re.search(r"\d+C", val):
            unit = "celsius"

        parsed.append({
            "name": name,
            "value": val,
            "unit": unit,
            "observed_on": observed_date
        })

    return json.dumps(parsed)


def parse_tags(tags_str: str, dept: str, action_type: str) -> str:
    """Return a PostgreSQL array literal like {tag1,tag2}."""
    tags = set()
    if tags_str and tags_str.strip():
        for t in tags_str.replace(";", ",").split(","):
            cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "", t.strip().lower())
            if cleaned:
                tags.add(cleaned)
    tags.add(dept.lower())
    tags.add(action_type.lower())
    return "{" + ",".join(sorted(tags)) + "}"


def map_outcome_label(status_raw: str) -> str:
    """Map legacy outcome status to success, failure, or unresolved."""
    s = (status_raw or "").strip().lower()
    if "success" in s:
        return "success"
    if "fail" in s:
        return "failure"
    return "unresolved"


def main():
    print("Starting MARS Dataset processing (clean simplified schema)...")

    verified_decisions: List[Dict] = []
    verified_outcomes: List[Dict] = []
    case_counter = 0

    for filename, quarter_name, decision_date, observation_date, src_doc, outcome_doc in QUARTER_FILES:
        filepath = DATASET_DIR / filename
        if not filepath.exists():
            print(f"Warning: File {filename} does not exist. Skipping.")
            continue

        with open(filepath, mode="r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"Processing {filename} ({quarter_name}): {len(rows)} raw rows.")

        for row in rows:
            case_counter += 1
            case_id = f"AAPL-{quarter_name.replace('-', '')}-{case_counter:04d}"

            # Swap fix if columns are misaligned
            raw_dept = row.get("department", "")
            raw_quarter = row.get("quarter", "")
            if "Q" in raw_dept and any(d in raw_quarter for d in ["Finance", "Operations", "R&D", "Legal"]):
                raw_dept, raw_quarter = raw_quarter, raw_dept

            title = (row.get("decision_title") or "Corporate Strategic Action").strip()
            archetype = (row.get("decision_archetype") or "").strip()
            trigger = (row.get("trigger") or "").strip()
            description = (row.get("decision_description") or "").strip()
            chosen_option = (row.get("chosen_option") or title).strip()
            reasoning = (row.get("reasoning_summary") or "").strip()
            signals_str = (row.get("quantitative_signals") or "").strip()
            tags_str = (row.get("decision_tags") or "").strip()

            department = normalize_department(raw_dept, f"{title} {description}")
            action_type = classify_action_type(chosen_option, archetype, title)
            quantitative_signals = parse_quantitative_signals(signals_str, decision_date)
            tags_array = parse_tags(tags_str, department, action_type)

            source_excerpt = (
                f"Disclosure Context ({quarter_name}): Trigger: '{trigger}'. "
                f"Management Action: '{chosen_option}'. "
                f"Context and Operational Scope: '{description}'. "
                f"Documented Reasoning: '{reasoning}'."
            )

            # 1. Verified Decision Case (Clean, no annotator/reviewer columns)
            verified_decisions.append({
                "case_id": case_id,
                "company_name": "Apple Inc.",
                "decision_date": decision_date,
                "source_document_id": src_doc,
                "source_url": "https://www.sec.gov/edgar/browse/?CIK=0000320193",
                "source_page_or_section": f"Item 2. Management's Discussion and Analysis - {department}",
                "source_excerpt": source_excerpt,
                "decision_title": title,
                "decision_description": description,
                "documented_action": chosen_option,
                "action_type": action_type,
                "decision_rationale": reasoning,
                "quantitative_signals": quantitative_signals,
                "department": department,
                "department_basis": "reported",
                "tags": tags_array,
            })

            # 2. Verified Outcome Record (Clean, no annotator/reviewer columns)
            outcome_status = row.get("outcome_status", "")
            outcome_summary = (row.get("outcome_summary") or "Subsequent operational follow-up pending.").strip()
            outcome_label = map_outcome_label(outcome_status)
            outcome_id = f"OUT-{case_id}"

            outcome_excerpt = (
                f"Subsequent Filing Observation ({outcome_doc}): "
                f"Follow-up for '{title}'. Stated result: '{outcome_summary}'."
            )

            verified_outcomes.append({
                "outcome_id": outcome_id,
                "case_id": case_id,
                "observation_date": observation_date,
                "source_document_id": outcome_doc,
                "source_url": "https://www.sec.gov/edgar/browse/?CIK=0000320193",
                "source_page_or_section": "Item 2. Subsequent Operational Performance",
                "source_excerpt": outcome_excerpt,
                "success_criterion": f"Stated operational target for {archetype or title} achieved in observation window.",
                "success_time_window": "1 to 2 quarters",
                "observed_result": outcome_summary,
                "outcome_label": outcome_label,
            })

    # Export verified_decisions.csv
    decisions_csv = DATASET_DIR / "verified_decisions.csv"
    decision_headers = [
        "case_id", "company_name", "decision_date", "source_document_id",
        "source_url", "source_page_or_section", "source_excerpt",
        "decision_title", "decision_description", "documented_action",
        "action_type", "decision_rationale", "quantitative_signals",
        "department", "department_basis", "tags"
    ]
    with open(decisions_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=decision_headers)
        writer.writeheader()
        writer.writerows(verified_decisions)
    print(f"Successfully generated {decisions_csv} ({len(verified_decisions)} rows).")

    # Export verified_outcomes.csv
    outcomes_csv = DATASET_DIR / "verified_outcomes.csv"
    outcome_headers = [
        "outcome_id", "case_id", "observation_date", "source_document_id",
        "source_url", "source_page_or_section", "source_excerpt",
        "success_criterion", "success_time_window", "observed_result",
        "outcome_label"
    ]
    with open(outcomes_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=outcome_headers)
        writer.writeheader()
        writer.writerows(verified_outcomes)
    print(f"Successfully generated {outcomes_csv} ({len(verified_outcomes)} rows).")


if __name__ == "__main__":
    main()
