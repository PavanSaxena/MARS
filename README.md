# MARS — Multi-Agent Reasoning System

A multi-agent AI strategic decision system built with **LangGraph**, **LangChain**, **Supabase (pgvector)**, and **FastAPI**, with **Open WebUI** as the chat frontend.

Given a strategic business query, MARS classifies the intent and either routes conversational follow-ups to a contextual chat agent or fans out to four department specialist agents (Finance, R&D, Legal, Operations) in parallel. Each department agent grounds its analysis in historical precedent cases retrieved from Supabase and live tool executions, followed by aggregation into an evidence-backed recommendation with complete explainability.

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
│   ├── sql/                  # pgvector & schema setup scripts (001_setup.sql)
│   ├── Dockerfile            # Container definition (PyTorch CPU + dependencies)
│   ├── docker-compose.yml    # Backend + Open WebUI stack
│   └── requirements.txt
│
├── dataset/                  # Verified empirical enterprise dataset
│   ├── Decisions/            # Historical decision records across 4 departments
│   └── Outcome/              # Observed real-world outcomes & validation metrics
│
├── evaluation/               # Research-grade benchmark suite (BEIR & G-Eval)
│   ├── run_benchmark.py      # Automated benchmark runner (Retrieval + Generation)
│   ├── eval_retrieval.py     # BEIR protocol (Rec@k, MRR, nDCG@5, DeptPrec)
│   ├── eval_generation.py    # Frontier G-Eval (Groq 27B) + Deterministic NLP (ROUGE, Sim)
│   ├── benchmark_dataset.py  # Stratified chronological dataset loader
│   └── BENCHMARK_REPORT.md   # Published evaluation benchmarks and empirical findings
│
└── .gitignore
```

There is no separate custom frontend codebase needed — the chat interface is [Open WebUI](https://github.com/open-webui/open-webui), deployed via container and connected to MARS's native OpenAI-compatible API (`backend/app/api/openai_compat.py`).

---

## Quick Start (Docker)

This is the recommended way to run MARS — it brings up the backend and Open WebUI together.

```bash
cd backend
cp .env.example .env   # fill in your keys (SUPABASE_URL, SUPABASE_KEY, etc.)
docker compose up --build
```

Then run the one-time Supabase setup (see **Supabase Setup** below) before sending queries.

Once up:

| Service | URL | Purpose |
|---|---|---|
| **Open WebUI** | `http://localhost:3000` | Chat UI — open in your browser (`WEBUI_AUTH=false` pre-set) |
| **MARS Backend** | `http://localhost:8000` | Native REST API (`/api/*`) + OpenAI-compatible API (`/v1/*`) |

Open WebUI connects automatically to the backend container over `OPENAI_API_BASE_URL=http://mars-backend:8000/v1`. Authentication is disabled (`WEBUI_AUTH=false`), allowing instant access.

### Docker Build Notes

- Installs a **CPU-only build of `torch`** (via PyTorch's official CPU wheel index) to keep image size small for local embedding generation (`all-MiniLM-L6-v2`).
- Secrets in `.env` are excluded from image layers via `.dockerignore` and mounted securely at runtime.

---

## Quick Start (without Docker)

For local development on the backend without containers:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # configure environment variables
uvicorn main:app --reload
```

See **[backend/README.md](backend/README.md)** for detailed setup, testing instructions, and architecture specifications.

---

## Supabase Setup (One-Time)

MARS utilizes Supabase as its source of truth and vector database via `pgvector`. Decisions and outcomes are stored in the `decisions` and `outcomes` relational tables:

1. In your Supabase SQL Editor, run `backend/sql/001_setup.sql`. This:
   - Enables the `vector` extension.
   - Creates the `decisions` and `outcomes` tables with foreign keys and chronological constraint triggers.
   - Configures the `match_decisions` pgvector similarity search RPC.
   - Sets Row Level Security (RLS) policies.

2. Populate the database and pre-compute normalized 384-dimensional embeddings:
   ```bash
   python -m app.storage.sync_decisions_to_supabase
   ```

Re-run this sync script whenever the underlying CSV dataset is updated.

---

## Configuration

All configuration is centralized in `backend/app/core/config.py` and loaded from `backend/.env`.

```env
# Required for Vector Database & Cases Storage
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key

# Model Providers (configure whichever you use)
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Optional Search Tools
TAVILY_API_KEY=your_tavily_api_key       # Enables live market, legal, and supply-chain web search
```

### Supported Models

MARS supports dynamic runtime model switching via LangChain `init_chat_model()`:
- `ollama:qwen2.5:3b` *(default — runs locally at zero inference cost)*
- `google_genai:gemini-3.8-flash`
- `groq:qwen/qwen3.8-27b`
- `groq:openai/gpt-oss-120b`
- `groq:openai/gpt-oss-20b`

---

## Evaluation & Benchmarks

MARS includes a research-standard evaluation suite adhering to **BEIR (NeurIPS 2021)** and **G-Eval (EMNLP 2023)** protocols:

```bash
# Run both retrieval and generation benchmarks
python -m evaluation.run_benchmark
```

- **Retrieval Benchmark:** Evaluates BM25, Dense Vector, and MARS Hybrid+MMR across 640 verified enterprise decision cases (`evaluation/eval_retrieval.py`).
- **Generation Benchmark:** Evaluates Zero-Shot LLM, Naive RAG, and MARS Multi-Agent synthesis using Frontier LLM judges (Groq 27B) along with deterministic ROUGE-L, semantic cosine similarity, and citation precision metrics (`evaluation/eval_generation.py`).
- See **[evaluation/BENCHMARK_REPORT.md](evaluation/BENCHMARK_REPORT.md)** for detailed metrics and empirical results.

---

## Learn More

Consult **[backend/README.md](backend/README.md)** for:
- Detailed breakdown of department tools and MCP server integration
- Contextual reranking and MMR diversity algorithms
- Native REST endpoints (`POST /api/query`, `GET /api/models`)
- Intent routing and state persistence
