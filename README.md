# MARS — Multi-Agent Reasoning System

A multi-agent AI decision system built with **LangGraph**, **LangChain**, **Supabase (pgvector)**, and **FastAPI**.

Given a strategic business query, MARS fans out to four specialist agents (Finance, R&D, Legal, Operations) in parallel, then aggregates their outputs into a single recommendation with an explainability trail.

---

## Repo Layout

```
.
├── backend/              # FastAPI + LangGraph multi-agent system (see backend/README.md)
├── frontend/             # Web UI (planned, not started yet)
└── .gitignore
```


---

## Quick Start

```bash
cd backend && cp .env.example .env   # fill in GROQ_API_KEY, SUPABASE_URL, SUPABASE_KEY
```

Run `backend/sql/001_pgvector_setup.sql` once in your Supabase project's SQL editor (enables pgvector + creates the similarity-search function).

See `backend/README.md` for full local setup and run instructions.

---

## Frontend (planned)

Not built yet — `frontend/` currently just holds a README describing the expected API contract so the backend and frontend can be developed independently. CORS is already configured in `backend/app/core/config.py` for local dev origins; update `CORS_ORIGINS` there once the frontend's dev server is set up.
