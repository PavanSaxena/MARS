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
2. Retrieves the top-5 most similar historical decisions directly from Supabase via the `match_decisions` Postgres function (pgvector cosine similarity, filtered by department), each already joined with its recorded outcome
3. Sends the query + cases to `llama-3.3-70b-versatile` (via Groq) with its two department-specific tools bound (see **Tooling Layer** below). The model decides whether it needs a tool; if it calls one, the tool executes and its result is fed back for a second, final LLM call
4. Returns `{response, reasoning, confidence, num_cases_retrieved, avg_similarity, historical_success_rate, case_based_confidence, tools_used, explanation}` into the shared LangGraph state

### Tooling Layer (MCP)

Department tools are served over a real **Model Context Protocol** server (`app/mcp/server.py`, built with the official `mcp` SDK's `FastMCP`), not imported as local Python functions. `app/mcp/client.py` spawns it once as a subprocess over stdio (`python -m app.mcp.server`) the first time any agent needs a tool, keeps that one session alive for the life of the backend process, and exposes it to the rest of the codebase as plain sync calls — `get_langchain_tools_sync()` for schema discovery and `call_tool_sync(name, args)` for execution. Because it's a standard MCP server, any other MCP-compatible client (Claude Desktop, another service) could talk to the same tools without changes.

`app/tools/tool_registry.py` and `app/tools/tool_executor.py` no longer hold any tool logic — they're a thin allowlist + execution bridge on top of the MCP client:

| Agent | Tools | Source |
|---|---|---|
| Finance | `FinancialDataTool`, `MarketAnalysisTool` | Supabase `decisions`/`outcomes` aggregate / live Tavily web search |
| R&D | `ResearchDatabaseTool`, `ExperimentTrackerTool` | Supabase `decisions`/`outcomes` aggregate |
| Legal | `LegalDatabaseTool`, `ComplianceCheckerTool` | Live Tavily web search / Supabase `decisions`/`outcomes` aggregate |
| Operations | `OperationsDashboardTool`, `SupplyChainAnalyzerTool` | Supabase `decisions`/`outcomes` aggregate / live Tavily web search |

- **Internal tools** (`FinancialDataTool`, `ResearchDatabaseTool`, `ExperimentTrackerTool`, `ComplianceCheckerTool`, `OperationsDashboardTool`) query `decisions` joined with `outcomes` for a department-level snapshot (action-type breakdown, most recent cases and what happened to them) — a plain filtered query, separate from the pgvector similarity search used for case retrieval.
- **External tools** (`MarketAnalysisTool`, `LegalDatabaseTool`, `SupplyChainAnalyzerTool`) run a live Tavily web search. If `TAVILY_API_KEY` isn't set, they return a clear "unavailable" message instead of failing.

The LLM decides per-query whether to call a tool at all — see the "Retrieved Evidence... you also have these tools available" section of the prompt in `app/agents/common.py:build_json_prompt`, where the bound tools now come from `app/tools/tool_registry.py:get_tool_objects_for_agent`, which in turn calls `app/mcp/client.py:get_langchain_tools_sync` and filters to that agent's allowlist. If the LLM calls one, `app/tools/tool_executor.py:execute_tool_call` re-checks the same allowlist, then forwards the call to `app/mcp/client.py:call_tool_sync` — a real MCP `CallToolRequest` round trip to the server subprocess — and the result is appended as a `ToolMessage` before the final answer is generated. Which tools were actually called (if any) is tracked in `tools_used` and surfaced in the per-department `explanation`.

For manual inspection, the MCP server can be run standalone: `python -m app.mcp.server` (stdio transport — pair it with any MCP inspector/client).

> **Note on confidence:** `confidence` is the LLM's own self-reported score. `case_based_confidence` is a **placeholder** for a planned multi-factor score (`similarity + recency + past_success`) — the weighting formula is still being researched, so this field is currently always `null`. See `app/reasoning/confidence.py`.

The Aggregator ranks departments by their reported confidence (highest first), uses a fixed priority order (Legal > Finance > Operations > R&D) only as a tiebreaker, and appends a per-department explainability trail to the final output.

**There is no separate vector database.** Decision data and its embeddings both live in Supabase — decisions are stored in the `decisions` table (Postgres), and a `vector` column on that same table (via the `pgvector` extension) is queried directly for similarity search. Outcomes live in a separate `outcomes` table (one row per `decisions.case_id`), joined in server-side by the `match_decisions` RPC.

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
│   └── 001_setup.sql              # ONE-TIME: run in Supabase's SQL editor
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
    │   ├── embedder.py                    # get_embedding() / get_embeddings()
    │   ├── retriever.py                   # retrieve_cases() — calls match_decisions RPC
    │   └── sync_decisions_to_supabase.py  # Imports dataset/ CSVs + writes embeddings into Supabase
    │
    ├── mcp/
    │   ├── server.py                  # Real MCP server (FastMCP) — the 8 tool implementations live here
    │   └── client.py                  # Owns the server subprocess/session; get_langchain_tools_sync() + call_tool_sync()
    │
    ├── tools/
    │   ├── tool_executor.py           # execute_tool_call() — allowlist check + forwards to app.mcp.client
    │   └── tool_registry.py           # Per-agent tool allowlist + get_tool_objects_for_agent()
    │
    └── api/
        └── routes.py                 # POST /api/query
```

---

## Setup

> **Docker users:** if you're running via `docker compose up` (see the top-level [README](../README.md)), step 1 below is handled for you by the `Dockerfile` — you still need to do steps 2–4 yourself. `docker compose exec mars-backend python -m app.storage.sync_decisions_to_supabase` runs step 4 inside the running container.

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

Open the Supabase SQL editor for your project and run `sql/001_setup.sql`. It:

- Enables the `pgvector` extension
- Creates `decisions` (18 columns: title, description, documented action, action type, rationale, quantitative signals, department, tags, cross-department impact, an `embedding vector(384)` column — 384 = `all-MiniLM-L6-v2`'s output size — and more) and `outcomes` (one row per `decisions.case_id`, with `outcome_label`, `observation_date`, and the observed evidence)
- Creates an `hnsw` index on `decisions.embedding` for fast approximate nearest-neighbour search
- Creates a trigger enforcing that every outcome's `observation_date` is strictly after its decision's `decision_date`
- Creates the `match_decisions` Postgres function that `app/storage/retriever.py` calls via `supabase.rpc(...)`, and the `bulk_update_decision_embeddings` / `get_decisions_corpus_summary` helper functions
- Enables row-level security: anyone can read, only the `service_role` key can write

### 4. Import the dataset and compute embeddings

```bash
python -m app.storage.sync_decisions_to_supabase
```

This reads `dataset/Decisions/decisions.csv` and `dataset/Outcome/outcomes.csv`, computes an embedding for every decision, and upserts both tables by `case_id` — all in one pass. Requires `SUPABASE_KEY` to be a service_role key (see step 3's RLS note). Re-run any time the dataset changes.

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
