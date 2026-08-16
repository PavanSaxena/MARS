from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from app.config import ensure_directories
from app.models.pipeline import GenerationRequest
from app.pipeline.orchestrator import Pipeline


app = FastAPI(title="Decision Generator")
pipeline = Pipeline()


ensure_directories()


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate")
async def generate_dataset(
    files: list[UploadFile] | None = File(default=None),
    max_cases: int = Query(default=50, ge=1, le=50),
    rows: int | None = Query(default=None, ge=1, le=50),
):
    requested_cases = rows if rows is not None else max_cases
    if requested_cases <= 0:
        raise HTTPException(status_code=400, detail="max_cases must be greater than zero")

    uploaded_files: list[tuple[str, bytes]] | None = None
    if files:
        uploaded_files = []
        for uploaded_file in files:
            uploaded_files.append((uploaded_file.filename or "input.pdf", await uploaded_file.read()))

    try:
        response = pipeline.run(GenerationRequest(max_cases=requested_cases), uploaded_files=uploaded_files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return response.model_dump()
