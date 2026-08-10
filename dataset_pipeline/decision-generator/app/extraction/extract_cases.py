from __future__ import annotations

from app.generation.agent_reasoning import build_case_row, clean_text, split_sentences


SOURCE_KEYWORDS = (
    "guidance",
    "forecast",
    "defer",
    "delay",
    "approve",
    "approved",
    "authorization",
    "compliance",
    "litigation",
    "settlement",
    "revenue",
    "expense",
    "cash flow",
    "liquidity",
    "impairment",
    "restructuring",
    "launch",
    "manufacturing",
    "inventory",
    "capital expenditure",
    "capex",
)


def _is_source_rich(sentence: str) -> bool:
    lower_sentence = sentence.lower()
    return any(keyword in lower_sentence for keyword in SOURCE_KEYWORDS)


def extract_cases(chunks: list[str], source_file_name: str, quarter: str = "Q4-2025") -> list[dict]:
    cases = []
    seen_titles: set[str] = set()
    case_id = 1

    for chunk in chunks:
        sentences = split_sentences(chunk)
        for sentence in sentences:
            if len(clean_text(sentence)) < 40 or not _is_source_rich(sentence):
                continue

            source_excerpt = clean_text(sentence)
            title_key = source_excerpt.lower()
            if title_key in seen_titles:
                continue

            seen_titles.add(title_key)
            cases.append(
                build_case_row(
                    case_id=case_id,
                    source_file_name=source_file_name,
                    source_excerpt=source_excerpt,
                    quarter=quarter,
                )
            )
            case_id += 1

    return cases