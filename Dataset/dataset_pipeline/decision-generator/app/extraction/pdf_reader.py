from __future__ import annotations

from pathlib import Path

import fitz


def extract_pdf_text(path: str | Path) -> str:
    document = fitz.open(str(path))
    try:
        return "".join(page.get_text() for page in document)
    finally:
        document.close()