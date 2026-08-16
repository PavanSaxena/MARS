# Decision Generator

Decision Generator is a local FastAPI application for producing enterprise decision cases from company filings and transcripts. The pipeline now follows a modular orchestration flow: document intelligence, enterprise context building, prompt construction, generation, validation, and CSV export.

## What It Does

- Accepts uploaded PDF documents for the same fiscal quarter.
- Reuses previously uploaded documents on later requests when no new files are provided.
- Generates up to 50 decision cases per run.
- Validates schema, business rules, confidence bounds, and duplicate risk.
- Writes `output/generated.csv` as the final artifact.

## Run It

```bash
docker compose up --build
```

Health check:

```bash
curl http://localhost:8000/health
```

## API

`POST /generate`

Inputs:

- `files`: optional list of uploaded PDFs
- `max_cases`: requested number of cases, capped at 50
- `rows`: legacy alias for `max_cases`

If `files` is omitted, the pipeline reuses the most recently uploaded documents from `data/uploaded_documents/`.

Example:

```bash
curl -X POST "http://localhost:8000/generate?max_cases=25" \
  -F "files=@proxy_statement.pdf" \
  -F "files=@quarterly_report.pdf" \
  -F "files=@earnings_call_transcript.pdf"
```

## Artifacts

Generated artifacts are written under `data/pipeline_artifacts/<run_id>/`:

- `parsed_documents.json`
- `enterprise_context.json`
- `generated_cases.json`
- `validated_cases.json`

The final CSV is written to:

- `output/generated.csv`

Accepted cases are also appended to:

- `data/case_memory/accepted_cases.jsonl`

## Configuration

Configuration is centralized in `app/config.py` and can be adjusted with environment variables:

- `MAX_CASES`
- `CHUNK_SIZE`
- `RETRY_LIMIT`
- `TEMPERATURE`
- `MODEL`
- `LLM_PROVIDER`
- `LLM_API_KEY`

## Notes

- CSV export is handled only by `app/export/csv_export.py`.
- The LLM layer is provider-agnostic and can run locally without an API key.
- The pipeline is designed to stay local and filesystem-backed.
