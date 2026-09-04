# MARS Backend

FastAPI + LangGraph multi-agent decision system. Given a strategic business query, MARS fans out to four department agents (Finance, R&D, Legal, Operations) in parallel, retrieves similar historical cases per department directly from **Supabase (pgvector)**, then aggregates all four assessments into one final decision with an explainability trail.

---

## Architecture

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

Each department agent:
1. Embeds the query with `all-MiniLM-L6-v2`
2. Retrieves the top-5 most similar historical cases directly from Supabase via the `match_decision_cases` Postgres function (pgvector cosine similarity, filtered by department)
3. Sends the query + cases to `llama-3.3-70b-versatile` (via Groq) with its two department-specific tools bound (see **Tooling Layer** below). The model decides whether it needs a tool; if it calls one, the tool executes and its result is fed back for a second, final LLM call
4. Returns `{response, reasoning, confidence, num_cases_retrieved, avg_similarity, historical_success_rate, case_based_confidence, tools_used, explanation}` into the shared LangGraph state

### Tooling Layer

Each department agent has two tools bound to its LLM call (`app/tools/tool_registry.py` controls which):

| Agent | Tools | Source |
|---|---|---|
| Finance | `FinancialDataTool`, `MarketAnalysisTool` | Supabase `decision_cases` aggregate / live Tavily web search |
| R&D | `ResearchDatabaseTool`, `ExperimentTrackerTool` | Supabase `decision_cases` aggregate |
| Legal | `LegalDatabaseTool`, `ComplianceCheckerTool` | Live Tavily web search / Supabase `decision_cases` aggregate |
| Operations | `OperationsDashboardTool`, `SupplyChainAnalyzerTool` | Supabase `decision_cases` aggregate / live Tavily web search |

- **Internal tools** (`FinancialDataTool`, `ResearchDatabaseTool`, `ExperimentTrackerTool`, `ComplianceCheckerTool`, `OperationsDashboardTool`) query `decision_cases` directly for a department-level snapshot (risk-level breakdown, most recent cases) — a plain filtered query, separate from the pgvector similarity search used for case retrieval.
- **External tools** (`MarketAnalysisTool`, `LegalDatabaseTool`, `SupplyChainAnalyzerTool`) run a live Tavily web search. If `TAVILY_API_KEY` isn't set, they return a clear "unavailable" message instead of failing.

The LLM decides per-query whether to call a tool at all — see the "Retrieved Evidence... you also have these tools available" section of the prompt in `app/agents/common.py:build_json_prompt`. If it does, `app/tools/tool_executor.py:execute_tool_call` runs it (re-checking the same per-agent allowlist as `tool_registry.py`), and the result is appended as a `ToolMessage` before the final answer is generated. Which tools were actually called (if any) is tracked in `tools_used` and surfaced in the per-department `explanation`.

> **Note on confidence:** `confidence` is the LLM's own self-reported score. `case_based_confidence` is a **placeholder** for a planned multi-factor score (`similarity + recency + past_success`) — the weighting formula is still being researched, so this field is currently always `null`. See `app/reasoning/confidence.py`.

The Aggregator ranks departments by their reported confidence (highest first), uses a fixed priority order (Legal > Finance > Operations > R&D) only as a tiebreaker, and appends a per-department explainability trail to the final output.

**There is no separate vector database.** Case data and its embeddings both live in Supabase — cases are stored in the `decision_cases` table (Postgres), and a `vector` column on that same table (via the `pgvector` extension) is queried directly for similarity search. This removes the two-database sync problem that existed with ChromaDB.

---

## Project Structure

```
backend/
├── main.py                          # FastAPI app entry point (CORS, router)
├── requirements.txt
├── pyproject.toml
├── .env                              # not committed — see .env.example
├── .env.example
├── sql/
│   ├── 001_pgvector_setup.sql         # ONE-TIME: run in Supabase's SQL editor
│   └── 002_bulk_update_embeddings.sql # ONE-TIME: run after 001, backs index_cases.py's batched writes
│
└── app/
    ├── state.py                      # Shared LangGraph State (TypedDict)
    │
    ├── core/
    │   └── config.py                 # Centralized settings (env vars), loaded once
    │
    ├── agents/
    │   ├── master_agent.py           # Graph builder + run_graph()
    │   ├── common.py                 # Shared helpers: prompt building, output parsing, case evidence
    │   ├── finance_agent.py
    │   ├── rd_agent.py
    │   ├── legal_agent.py
    │   └── operations_agent.py
    │
    ├── reasoning/
    │   ├── aggregator.py             # Confidence-ranked aggregator node
    │   ├── confidence.py             # Multi-factor confidence — PLACEHOLDER, returns None
    │   ├── similarity.py             # Average vector similarity
    │   ├── outcome_analysis.py       # Historical success rate
    │   └── explainability.py         # Human-readable explanation generator
    │
    ├── services/
    │   ├── supabase_client.py        # Shared Supabase client (singleton)
    │   └── case_retrieval_service.py # get_similar_cases() + CaseRetrievalService
    │
    ├── storage/
    │   ├── embedder.py               # get_embedding()
    │   ├── retriever.py              # retrieve_cases() — calls match_decision_cases RPC
    │   └── index_cases.py            # Computes + writes embeddings into Supabase
    │
    ├── tools/
    │   ├── tool_executor.py           # 8 real tool implementations + execute_tool_call()
    │   └── tool_registry.py           # Per-agent tool allowlist + get_tool_objects_for_agent()
    │
    └── api/
        └── routes.py                 # POST /api/query
```

---

## Setup

> **Docker users:** if you're running via `docker compose up` (see the top-level [README](../README.md)), steps 1 and 5 below are handled for you by the `Dockerfile` and `docker-compose.yml` — you still need to do steps 2–4 (env vars + one-time Supabase setup) yourself. `docker compose exec mars-backend python -m app.storage.index_cases` runs step 4 inside the running container.

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Then fill in:

```env
GROQ_API_KEY=your_groq_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
TAVILY_API_KEY=your_tavily_api_key   # optional — powers MarketAnalysisTool, LegalDatabaseTool,
                                      # SupplyChainAnalyzerTool. Without it those three tools
                                      # just return an "unavailable" message instead of failing.
```

All settings are loaded once via `app/core/config.py` — see that file for the full list and defaults.

### 3. One-time Supabase setup (pgvector)

Open the Supabase SQL editor for your project and run `sql/001_pgvector_setup.sql`, then `sql/002_bulk_update_embeddings.sql`.

`001_pgvector_setup.sql`:
- Enables the `pgvector` extension
- Adds an `embedding vector(384)` column to `decision_cases` (384 = `all-MiniLM-L6-v2`'s output size — if you change embedding models later, update this)
- Creates an `ivfflat` index for fast approximate nearest-neighbour search
- Creates the `match_decision_cases` Postgres function that `app/storage/retriever.py` calls via `supabase.rpc(...)`

`002_bulk_update_embeddings.sql`:
- Creates the `bulk_update_case_embeddings` Postgres function that `app/storage/index_cases.py` calls to write embeddings back in batches. It does a real, set-based `UPDATE` (never an `INSERT`), so a `case_id` that doesn't match an existing row is simply skipped rather than creating a malformed new row.

### 4. Backfill embeddings (only needed once, or when Supabase case rows change)

```bash
python -m app.storage.index_cases
```

This computes an embedding for **every** row currently in `decision_cases` (existing rows and any new ones you've added since the last run) and writes it into the `embedding` column in place, in batches of 100 with progress printed after each batch. There's no trigger or automation — the `001_pgvector_setup.sql` migration only adds the empty `embedding` column, it does not populate it. Re-run this command any time you add or edit case rows in Supabase, otherwise those rows will have `embedding = null` and get silently excluded from `match_decision_cases` results.

### 5. Run the API server

```bash
uvicorn main:app --reload
```

The API is available at `http://localhost:8000`.

---

## Model Switching

Every LLM call (all 4 department agents + the aggregator) goes through `app.agents.common.get_llm(model_id)`, so which model is used is a per-request choice, not a hardcoded one. Model ids are `"<provider>:<model>"` strings, matching LangChain's `init_chat_model()` convention — e.g. `openai:gpt-5.6-terra` or `anthropic:claude-sonnet-5` once those providers are added below. Only models actually listed in `settings.AVAILABLE_MODELS` (`app/core/config.py`) are usable — right now that's the three Groq models shown there; add an OpenAI/Anthropic entry to that list (and set the matching API key) to enable it.

Each provider needs its own key in `.env` (`GROQ_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) — only set the ones for models you actually want available. `GET /api/models` tells you which configured models are actually usable right now vs. blocked on a missing key.

**Context carries over automatically.** Model choice is stored in the LangGraph state alongside the message history, both checkpointed per `thread_id`. If a request omits `model`, the thread's previously-selected model (or `DEFAULT_MODEL` for a brand-new thread) is reused — you only need to pass `model` on the turn where the user actually switches it.

- `GET /api/models` — list available models, the default, and which ones are currently unusable (missing API key).
- `GET /api/threads/{thread_id}/model` — the model currently active for a thread (e.g. to restore a switcher's state after reload).
- `POST /api/query` — pass `model` to switch (or start) a thread on a specific model; omit it to keep using whatever that thread was already on.

```bash
curl -s -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Should we invest in X?", "thread_id": "t1", "model": "groq:openai/gpt-oss-20b"}' | jq
```

## API Usage

### `POST /api/query`

```bash
curl -s -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Should we invest in an AI-driven supply chain optimization initiative this quarter?", "thread_id": "test-1"}' | jq
```

`model` is optional here too — see **Model Switching** above.

**Response:**
```json
{
  "key_insights": ["string", "..."],
  "conflicts": ["string", "..."],
  "final_decision": { "decision": "string" },
  "explainability": "string | null"
}
```

`explainability` contains one block per department (retrieved case count, historical outcomes observed, and the case-based confidence placeholder note).
