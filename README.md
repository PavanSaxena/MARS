# MARS — Multi-Agent Reasoning System

A multi-agent AI decision system built with **LangGraph**, **LangChain**, **Supabase (pgvector)**, and **FastAPI**, with **Open WebUI** as the chat frontend.

Given a strategic business query, MARS fans out to four specialist agents (Finance, R&D, Legal, Operations) in parallel — each grounding its answer in similar historical cases retrieved from Supabase and, where relevant, live tool calls — then aggregates the four assessments into a single recommendation with a full explainability trail.

```
User Query
    │
    ▼
┌──────────┐
│  Master  │  (entry / router node)
└──────────┘
    │ fan-out (parallel)
    ├──────────────┬──────────────┬──────────────┐
    ▼              ▼              ▼              ▼
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────────┐
│ Finance │  │   R&D   │  │  Legal  │  │ Operations │
└─────────┘  └─────────┘  └─────────┘  └────────────┘
    │              │              │              │
    └──────────────┴──────────────┴──────────────┘
                        │ fan-in
                        ▼
                 ┌────────────┐
                 │ Aggregator │  (ranks by confidence, resolves conflicts, explains)
                 └────────────┘
                        │
                        ▼
                  Final Decision
```

---

## Repo Layout

```
.
├── backend/              # FastAPI + LangGraph multi-agent system (see backend/README.md)
│   ├── Dockerfile
│   ├── docker-compose.yml   # backend + Open WebUI
│   └── ...
└── .gitignore
```

There's no separate `frontend/` — the UI is [Open WebUI](https://github.com/open-webui/open-webui), run as its own container and pointed at MARS's OpenAI-compatible API (`backend/app/api/openai_compat.py`). Nothing custom to build or maintain there.

---

## Quick Start (Docker)

This is the recommended way to run MARS — it brings up the backend and the chat UI together.

```bash
cd backend
cp .env.example .env   # fill in GROQ_API_KEY, SUPABASE_URL, SUPABASE_KEY (see below)
docker compose up --build
```

Then run the one-time Supabase setup (see **Supabase Setup** below) before sending your first query.

Once it's up:

| Service | URL | Purpose |
|---|---|---|
| **Open WebUI** | `http://localhost:3000` | Chat UI — open this in your browser |
| MARS backend | `http://localhost:8000` | Native API + `/v1/*` OpenAI-compatible routes (not meant to be browsed directly) |

Open WebUI is pre-wired to the backend via `OPENAI_API_BASE_URL=http://mars-backend:8000/v1` in `docker-compose.yml`, so no manual connection setup should be needed. If its model dropdown comes back empty, it means none of `settings.AVAILABLE_MODELS` (`backend/app/core/config.py`) has a matching provider API key set in `.env` — `GET /v1/models` only advertises models it can actually call.

### Notes on the Docker build

- The image installs a **CPU-only build of `torch`** (via PyTorch's own CPU wheel index) rather than the default PyPI wheel, which bundles CUDA and is 2GB+ larger than needed — MARS only uses `torch` to run a small local embedding model (`all-MiniLM-L6-v2`), not GPU training/inference.
- `torch` + `transformers` + `sentence-transformers` still add up to a multi-GB image. If the build fails with `No space left on device`, that's disk space on the Docker host/VM, not the app — run `docker system prune -a --volumes` to reclaim space, and on Docker Desktop check **Settings → Resources → Advanced → Disk image size**. On Linux, confirm `df -h /` isn't full — Docker's storage (`/var/lib/docker` by default) lives on the root partition unless you've configured `data-root` elsewhere in `/etc/docker/daemon.json`.
- Secrets in `.env` are never baked into the image — `.dockerignore` excludes it from the build context, and `docker-compose.yml` mounts it in at runtime via `env_file`.

---

## Quick Start (without Docker)

For local development on the backend without containers, see **[backend/README.md](backend/README.md)** for full setup, project structure, the tooling layer, and API usage details.

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in credentials
uvicorn main:app --reload
```

You'll still need a frontend to talk to it — either point Open WebUI's own container at `http://localhost:8000/v1` (adjust `OPENAI_API_BASE_URL` accordingly if running it standalone), or call `POST /api/query` directly (see backend README).

---

## Supabase Setup (one-time)

MARS uses Supabase both as the source-of-truth database and as the vector store (via the `pgvector` extension) — there's no separate vector DB to keep in sync. Historical decisions live in the **`decisions`** table, and their observed outcomes in **`outcomes`**, sourced from `dataset/Decisions/decisions.csv` and `dataset/Outcome/outcomes.csv`.

In your Supabase project's SQL editor, run:

1. `backend/sql/001_setup.sql` — enables `pgvector`, creates `decisions` and `outcomes`, the `match_decisions` similarity-search RPC, the batched embedding-write RPC, the outcome-chronology trigger, and RLS policies.

Then import the CSVs and compute embeddings in one pass:

```bash
# from backend/, with dependencies installed locally, or via `docker compose exec mars-backend`
python -m app.storage.sync_decisions_to_supabase
```

Re-run this any time the dataset changes — it upserts by `case_id`.

---

## Configuration

All settings load once from `backend/.env` via `backend/app/core/config.py`. Minimum required:

```env
GROQ_API_KEY=your_groq_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

Optional:

```env
TAVILY_API_KEY=your_tavily_api_key       # powers 3 live-search tools; without it they return "unavailable"
OPENAI_API_KEY=your_openai_api_key       # only needed to enable openai:* models
ANTHROPIC_API_KEY=your_anthropic_api_key # only needed to enable anthropic:* models
SUPABASE_DECISIONS_TABLE=decisions
SUPABASE_OUTCOMES_TABLE=outcomes
API_HOST=0.0.0.0
API_PORT=8000
```

See `backend/README.md` for the full list, model-switching details, and the tooling layer.

---

## Learn More

See **[backend/README.md](backend/README.md)** for:
- Full architecture and per-agent tooling layer
- Project structure
- Model switching across Groq / OpenAI / Anthropic
- Native `POST /api/query` and `GET /api/models` usage
