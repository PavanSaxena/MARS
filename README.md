# MARS — Multi-Agent Reasoning System

A multi-agent AI strategic decision system built with **LangGraph**, **LangChain**, **Supabase (pgvector)**, and **FastAPI**, with **Open WebUI** as the chat frontend.

Given a strategic business query, MARS classifies user intent and either routes conversational follow-ups to a contextual chat agent or fans out to four department specialist agents (Finance, R&D, Legal, Operations) in parallel. Each department agent grounds its reasoning in similar historical cases retrieved from Supabase and live tool executions, followed by aggregation into an evidence-backed recommendation with complete explainability.

```
                    User Query
                        │
                        ▼
                ┌───────────────┐
                │ Intent Router │  (classifies: "pipeline" vs "chat")
                └───────┬───────┘
                        │
         ┌──────────────┴──────────────┐
         │ [pipeline]                  │ [chat]
         ▼                             ▼
  ┌──────────────┐              ┌──────────────┐
  │ Master Router│ (fan-out)    │  Chat Agent  │ ──► Conversation Response
  └──────┬───────┘              └──────────────┘
         │
 ┌───────┼──────────────┬──────────────┐
 ▼       ▼              ▼              ▼
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────────┐
│ Finance │  │   R&D   │  │  Legal  │  │ Operations │
└────┬────┘  └────┬────┘  └────┬────┘  └─────┬──────┘
     │            │            │             │
     └────────────┴──────┬─────┴─────────────┘
                         │ fan-in
                         ▼
                  ┌────────────┐
                  │ Aggregator │  (confidence ranking, conflict resolution, explainability)
                  └─────┬──────┘
                        │
                        ▼
                  Final Strategic Decision
```

---

## Repo Layout

```
.
├── backend/                  # FastAPI + LangGraph multi-agent system (see backend/README.md)
│   ├── app/                  # Application code (agents, reasoning, tools, storage, API)
│   ├── sql/                  # pgvector & schema setup scripts (001 & 002)
│   ├── Dockerfile            # Container definition (PyTorch CPU + dependencies)
│   ├── docker-compose.yml    # Backend + Open WebUI stack
│   └── requirements.txt
│
├── Dataset/                  # Enterprise decision cases corpus
│
└── .gitignore
```

There is no separate custom frontend codebase needed — the chat interface is [Open WebUI](https://github.com/open-webui/open-webui), deployed via container and connected to MARS's native OpenAI-compatible API (`backend/app/api/openai_compat.py`).

---

## Quick Start (Docker)

This is the recommended way to run MARS — it brings up the backend and Open WebUI together.

```bash
cd backend
cp .env.example .env   # fill in GROQ_API_KEY, SUPABASE_URL, SUPABASE_KEY (see below)
docker compose up --build
```

Then run the one-time Supabase setup (see **Supabase Setup** below) before sending your first query.

Once up:

| Service | URL | Purpose |
|---|---|---|
| **Open WebUI** | `http://localhost:5001` | Chat UI — open in your browser (`WEBUI_AUTH=false` pre-configured) |
| **MARS Backend** | `http://localhost:8000` | Native REST API (`/api/*`) + OpenAI-compatible API (`/v1/*`) |

Open WebUI connects automatically to the backend container over `OPENAI_API_BASE_URL=http://mars-backend:8000/v1`. Authentication is disabled (`WEBUI_AUTH=false`), allowing instant access without account setup.

### Docker Build Notes

- Installs a **CPU-only build of `torch`** (via PyTorch's official CPU wheel index) to keep image size small for local embedding generation (`all-MiniLM-L6-v2`).
- Secrets in `.env` are excluded from image layers via `.dockerignore` and mounted securely at runtime.

---

## Quick Start (without Docker)

For local development on the backend without containers, see **[backend/README.md](backend/README.md)** for full setup, project structure, the tooling layer, and API usage details.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in credentials
uvicorn main:app --reload
```

You can interact with it via Open WebUI pointed at `http://localhost:8000/v1` or by calling `POST /api/query` directly.

---

## Supabase Setup (One-Time)

MARS uses Supabase both as the source-of-truth database and as the vector store (via the `pgvector` extension) on the `decision_cases` table:

In your Supabase project's SQL editor, run in order:

1. `backend/sql/001_pgvector_setup.sql` — enables `pgvector`, adds the `embedding` column (`vector(384)`) to `decision_cases`, and creates the `match_decision_cases` similarity-search function.
2. `backend/sql/002_bulk_update_embeddings.sql` — creates the `bulk_update_case_embeddings` function used to backfill embeddings in batches.

Then backfill embeddings for your case rows:

```bash
# from backend/, with dependencies installed locally, or via `docker compose exec mars-backend`
python -m app.storage.index_cases
```

Re-run this command any time rows in `decision_cases` are added or updated.

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
TAVILY_API_KEY=your_tavily_api_key       # powers live web-search tools; returns graceful fallback without it
OPENAI_API_KEY=your_openai_api_key       # only needed to enable openai:* models
ANTHROPIC_API_KEY=your_anthropic_api_key # only needed to enable anthropic:* models
SUPABASE_CASES_TABLE=decision_cases
API_HOST=0.0.0.0
API_PORT=8000

# Retrieval & Contextual Reranking Hyperparameters
RETRIEVAL_CANDIDATE_COUNT=25
RETRIEVAL_MIN_CASES=3
RETRIEVAL_MAX_CASES=10
RETRIEVAL_SIMILARITY_FLOOR=0.25
RETRIEVAL_MMR_LAMBDA=0.65
```

### Supported Models

MARS supports dynamic runtime model switching via LangChain `init_chat_model()`:
- `groq:openai/gpt-oss-120b` *(default)*
- `groq:openai/gpt-oss-20b`
- `groq:qwen/qwen3.6-27b`

---

## Learn More

See **[backend/README.md](backend/README.md)** for:
- Full architecture, intent routing, and per-agent MCP tooling layer
- Contextual reranking and MMR diversity filtering mechanics
- Project structure
- Native `POST /api/query` and `GET /api/models` documentation
