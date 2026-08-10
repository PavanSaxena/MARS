from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

import fitz

from app.config import CHUNK_SIZE
from app.models.document import DocumentChunk, DocumentSection, ParsedDocument
from app.extraction.chunker import chunk_text


logger = logging.getLogger(__name__)


SECTION_PATTERN = re.compile(r"^(item\s+\d+[\w\.-]*|management\s+discussion|risk\s+factors|financial\s+statements|notes?)\b", re.IGNORECASE)


class DocumentIntelligence:
    def extract_text(self, path: Path) -> str:
        with fitz.open(str(path)) as document:
            return "\n".join(page.get_text() for page in document)

    def extract_pages(self, path: Path) -> list[str]:
        with fitz.open(str(path)) as document:
            return [page.get_text().strip() for page in document]

    def detect_sections(self, pages: Iterable[str]) -> list[DocumentSection]:
        sections: list[DocumentSection] = []
        for page_number, page_text in enumerate(pages, start=1):
            for line in page_text.splitlines():
                cleaned_line = line.strip()
                if cleaned_line and len(cleaned_line) < 140 and SECTION_PATTERN.match(cleaned_line):
                    sections.append(DocumentSection(title=cleaned_line, page_number=page_number, text=cleaned_line))
        return sections

    def detect_document_type(self, file_name: str) -> str:
        lower_name = file_name.lower()
        if "proxy" in lower_name:
            return "proxy_statement"
        if "10-q" in lower_name or "quarter" in lower_name:
            return "quarterly_report"
        if "earnings" in lower_name or "transcript" in lower_name:
            return "earnings_call_transcript"
        return "unknown"

    def parse_document(self, file_path: Path) -> ParsedDocument:
        try:
            pages = self.extract_pages(file_path)
            text = "\n".join(pages)
        except Exception as exc:
            logger.warning("pdf_parse_failed file=%s error=%s", file_path.name, exc)
            pages = []
            text = ""

        chunks = [
            DocumentChunk(chunk_id=f"{file_path.stem}-{index}", page_number=index + 1, text=chunk)
            for index, chunk in enumerate(chunk_text(text, size=CHUNK_SIZE or 5000))
        ]
        sections = self.detect_sections(pages)
        metadata = {
            "source": "pdf",
            "page_count": str(len(pages)),
            "ocr_status": "placeholder",
        }
        return ParsedDocument(
            file_name=file_path.name,
            file_path=file_path,
            document_type=self.detect_document_type(file_path.name),
            page_count=len(pages),
            metadata=metadata,
            pages=pages,
            sections=sections,
            chunks=chunks,
            ocr_status="placeholder",
        )

    def parse_documents(self, file_paths: list[Path]) -> list[ParsedDocument]:
        return [self.parse_document(path) for path in file_paths]
