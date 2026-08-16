from __future__ import annotations


def generate_rows(seed_cases: list[dict], rows: int = 1000) -> list[dict]:
    if rows <= 0:
        return []

    unique_rows = []
    seen_titles: set[str] = set()
    for row in seed_cases:
        title = str(row.get("decision_title", "")).strip().lower()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        unique_rows.append(row)

    unique_rows.sort(key=lambda row: (row.get("profit_confidence", 0), row.get("master_agent_confidence", 0)), reverse=True)
    return unique_rows[:rows]