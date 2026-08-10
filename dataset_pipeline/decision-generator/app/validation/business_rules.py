from __future__ import annotations


def _parse_option_labels(options_text: str) -> list[str]:
    labels = []
    for option in str(options_text).split(";"):
        cleaned = option.strip()
        if not cleaned:
            continue
        labels.append(cleaned.split(":", 1)[0].strip())
    return labels


def validate_business_rules(row: dict) -> bool:
    required_fields = [
        "case_id",
        "source_file_name",
        "source_excerpt",
        "quarter",
        "department",
        "decision_title",
        "decision_archetype",
        "trigger",
        "decision_description",
        "options_considered",
        "chosen_option",
        "reasoning_summary",
        "quantitative_signals",
        "risk_level",
        "cross_dept_impact",
        "expected_profit_impact",
        "profit_confidence",
        "profit_impact_pathway",
        "outcome_status",
        "outcome_summary",
        "decision_tags",
        "finance_agent_conf",
        "r_and_d_agent_conf",
        "ops_agent_conf",
        "legal_agent_conf",
        "conflicting_perspectives",
        "master_agent_decision",
        "master_agent_confidence",
    ]

    if any(not str(row.get(field, "")).strip() for field in required_fields):
        return False

    options = _parse_option_labels(str(row.get("options_considered", "")))
    chosen_option = str(row.get("chosen_option", "")).strip()

    if options and chosen_option not in options:
        return False

    for field in ("profit_confidence", "finance_agent_conf", "r_and_d_agent_conf", "ops_agent_conf", "legal_agent_conf", "master_agent_confidence"):
        value = row.get(field)
        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
            return False

    if any("\n" in str(row.get(field, "")) for field in ("decision_title", "trigger", "chosen_option", "master_agent_decision")):
        return False

    if len(options) < 3:
        return False

    return True