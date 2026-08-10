from __future__ import annotations

from difflib import SequenceMatcher


def is_duplicate(row: dict, existing: list[dict], threshold: float = 0.9) -> bool:
    current_title = str(row.get("decision_title", "")).strip().lower()
    if not current_title:
        return False

    for existing_row in existing:
        existing_title = str(existing_row.get("decision_title", "")).strip().lower()
        if SequenceMatcher(None, current_title, existing_title).ratio() >= threshold:
            return True

    return False


def deduplicate_rows(rows: list[dict]) -> list[dict]:
    deduplicated = []
    for row in rows:
        if not is_duplicate(row, deduplicated):
            deduplicated.append(row)
    return deduplicated