from __future__ import annotations


def chunk_text(text: str, size: int = 5000) -> list[str]:
    if size <= 0:
        raise ValueError("size must be greater than zero")

    cleaned_text = text.strip()
    if not cleaned_text:
        return []

    return [cleaned_text[index : index + size] for index in range(0, len(cleaned_text), size)]