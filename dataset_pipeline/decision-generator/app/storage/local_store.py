from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import CASE_MEMORY_DIR, OUTPUT_DIR, PIPELINE_ARTIFACTS_DIR, UPLOADED_DOCUMENTS_DIR, ensure_directories


class LocalFileStore:
    def __init__(self) -> None:
        ensure_directories()

    @staticmethod
    def _utc_stamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def run_dir(self, run_id: str) -> Path:
        path = PIPELINE_ARTIFACTS_DIR / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_json(self, directory: Path, name: str, payload: Any) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return path

    def save_artifact(self, run_id: str, name: str, payload: Any) -> Path:
        return self.save_json(self.run_dir(run_id), name, payload)

    def save_uploaded_document(self, file_name: str, content: bytes) -> Path:
        UPLOADED_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
        path = UPLOADED_DOCUMENTS_DIR / file_name
        path.write_bytes(content)
        return path

    def save_uploaded_documents(self, files: list[tuple[str, bytes]]) -> list[Path]:
        UPLOADED_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
        for existing in UPLOADED_DOCUMENTS_DIR.iterdir():
            if existing.is_file() and existing.name != "manifest.json":
                existing.unlink()

        stored_paths = [self.save_uploaded_document(file_name, content) for file_name, content in files]
        manifest_path = UPLOADED_DOCUMENTS_DIR / "manifest.json"
        manifest_path.write_text(json.dumps([path.name for path in stored_paths], indent=2), encoding="utf-8")
        return stored_paths

    def list_uploaded_documents(self) -> list[Path]:
        manifest_path = UPLOADED_DOCUMENTS_DIR / "manifest.json"
        if manifest_path.exists():
            file_names = json.loads(manifest_path.read_text(encoding="utf-8"))
            return [UPLOADED_DOCUMENTS_DIR / file_name for file_name in file_names if (UPLOADED_DOCUMENTS_DIR / file_name).exists()]

        if not UPLOADED_DOCUMENTS_DIR.exists():
            return []
        return sorted(path for path in UPLOADED_DOCUMENTS_DIR.iterdir() if path.is_file() and path.name != "manifest.json")

    def append_case_memory(self, cases: list[dict[str, Any]]) -> Path:
        CASE_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        path = CASE_MEMORY_DIR / "accepted_cases.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            for case in cases:
                handle.write(json.dumps(case, default=str) + "\n")
        return path

    def load_case_memory(self) -> list[dict[str, Any]]:
        path = CASE_MEMORY_DIR / "accepted_cases.jsonl"
        if not path.exists():
            return []
        cases: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cases.append(json.loads(line))
        return cases

    def save_generated_csv(self, rows: list[dict[str, Any]], path: Path | None = None) -> Path:
        output_path = path or (OUTPUT_DIR / "generated.csv")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(output_path, index=False)
        return output_path

    def latest_run_id(self) -> str:
        return self._utc_stamp()
