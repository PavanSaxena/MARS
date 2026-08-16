# MARS Frontend

Vite + React console for the MARS multi-agent backend.

## Setup

```bash
npm install
cp .env.example .env.local   # only needed if the backend isn't on localhost:8000
npm run dev
```

Runs on `http://localhost:5173` — already whitelisted in the backend's
`CORS_ORIGINS` (`backend/app/core/config.py`), so no backend changes needed
for local dev.

## What it does

- `src/api.js` — thin client for the three backend endpoints (`GET /models`,
  `GET /threads/{id}/model`, `POST /query`). Surfaces FastAPI's
  `{"detail": "..."}` error bodies directly.
- `src/App.jsx` — query console (question, thread ID, model picker) plus the
  results view.
- `src/components/DepartmentGrid.jsx` — status per department (Finance, R&D,
  Legal, Operations). The backend answers all four in one round trip, so all
  four cards move from "processing" to "reported" together — this reflects
  actual backend behavior rather than faking staggered progress.
- `src/components/DecisionPanel.jsx` — final decision, risk/ROI badges, key
  insights, conflicts.
- `src/components/ExplainabilityAccordion.jsx` — per-department reasoning
  trail, parsed from the `explainability` string's `[Department]` markers
  (see `backend/app/reasoning/aggregator.py`).

## Notes

- `risk_level`, `roi`, and `notes` on `final_decision` are optional and may
  be `null` — they depend on the aggregator's LLM actually following the
  structured sub-field format in its prompt (`Decision: / Risk Level: /
  ROI: / Notes:`), which isn't enforced. The UI already handles them being
  absent.
- Thread IDs are generated client-side (`web-xxxxxx`) and are just opaque
  strings the backend's LangGraph checkpointer uses to keep conversation
  memory per thread — reuse one to continue a conversation, change it to
  start fresh.
