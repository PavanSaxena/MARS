from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class DocumentSection(BaseModel):
    title: str
    page_number: int = Field(ge=1)
    text: str


class DocumentChunk(BaseModel):
    chunk_id: str
    page_number: int = Field(ge=1)
    text: str


class ParsedDocument(BaseModel):
    file_name: str
    file_path: Path
    document_type: str
    page_count: int = Field(ge=0)
    metadata: dict[str, str]
    pages: list[str]
    sections: list[DocumentSection]
    chunks: list[DocumentChunk]
    ocr_status: str = "placeholder"


class UploadedDocument(BaseModel):
    file_name: str
    file_path: Path
    mime_type: str | None = None
    size_bytes: int = 0
