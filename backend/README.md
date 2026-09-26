# MARS Backend

FastAPI + LangGraph multi-agent decision system. Given a strategic business query, MARS classifies user intent, routes conversational messages to a chat agent, or fans out to four department agents (Finance, R&D, Legal, Operations) in parallel. Each department agent retrieves relevant historical cases directly from **Supabase (pgvector)**, scores and reranks them with MMR diversity filtering, executes MCP tools where needed, and feeds into an aggregator node that synthesizes a final strategic recommendation with complete explainability.

---

## Architecture

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

### Turn Lifecycle & Retrieval Pipeline

1. **Intent Classification (`router.py`)**:
   - Queries are evaluated for conversational context vs. full strategic decision requests.
   - Follow-up questions, clarifications, and conversational inquiries route to `chat_agent`, preserving conversation history without unnecessarily re-running all 4 agents.
   - Complex business/investment queries route to the multi-agent decision pipeline.

2. **Precedent Retrieval & Contextual Reranking (`case_retrieval_service.py`)**:
   - **Candidate Pool:** Fetches top candidate cases (default: 25) from Supabase via `match_decisions` pgvector cosine similarity.
   - **Composite Scoring:** Combines dense vector similarity with tokenized lexical matching across titles, triggers, and rationales.
   - **Relevance Floor:** Drops candidates below `RETRIEVAL_SIMILARITY_FLOOR` (default: 0.25).
   - **Maximal Marginal Relevance (MMR):** Selects between 3 and 10 diverse cases (`RETRIEVAL_MIN_CASES` to `RETRIEVAL_MAX_CASES`) using `RETRIEVAL_MMR_LAMBDA` (0.65) to eliminate redundant precedents.

3. **Agent Deliberation & Tool Execution**:
   - Each department agent runs with its specialized system prompt, retrieved precedents, and two department-specific tools bound over the **Model Context Protocol (MCP)**.
   - The LLM decides whether a tool invocation is warranted. If requested, tools execute via MCP and results feed back into a follow-up completion.
   - Returns `{response, reasoning, confidence, num_cases_retrieved, avg_similarity, historical_success_rate, tools_used, explanation}` into graph state.

4. **Strategic Aggregator (`aggregator.py`)**:
   - Collects all four department outputs.
   - Ranks departments by reported confidence (Legal > Finance > Operations > R&D serves as a tiebreaker).
   - Synthesizes findings, identifies inter-departmental conflicts, and delivers an evidence-grounded final decision with complete per-department explainability.

---

### Tooling Layer (MCP)

Department tools are served over a real **Model Context Protocol** server (`app/mcp/server.py`, built with `FastMCP`). `app/mcp/client.py` maintains an active session over stdio subprocess (`python -m app.mcp.server`), exposing sync helpers `get_langchain_tools_sync()` and `call_tool_sync(name, args)` to the agents.

| Agent | Tools | Data Source |
|---|---|---|
| **Finance** | `FinancialDataTool`, `MarketAnalysisTool` | Supabase `decisions`/`outcomes` aggregate / Live Tavily web search |
| **R&D** | `ResearchDatabaseTool`, `ExperimentTrackerTool` | Supabase `decisions`/`outcomes` aggregate |
| **Legal** | `LegalDatabaseTool`, `ComplianceCheckerTool` | Live Tavily web search / Supabase `decisions`/`outcomes` aggregate |
| **Operations** | `OperationsDashboardTool`, `SupplyChainAnalyzerTool` | Supabase `decisions`/`outcomes` aggregate / Live Tavily web search |

- **Internal tools** perform direct relational queries on `decisions` and `outcomes` for departmental action-type distributions and historical success rates.
- **External search tools** invoke Tavily web search when `TAVILY_API_KEY` is present, or return a graceful fallback status if unconfigured.

---

## Project Structure

```
backend/
├── main.py                          # FastAPI app entry point (middleware, routers, CLI demo)
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env                              # Application environment variables (not committed)
├── .env.example
├── sql/
│   └── 001_setup.sql                 # One-time Supabase setup: pgvector, tables, RPCs, RLS
│
└── app/
    ├── state.py                      # Shared LangGraph State (TypedDict)
    │
    ├── core/
    │   ├── config.py                 # Centralized pydantic settings & provider sync
    │   ├── errors.py                 # Provider rate limit handling & error formatting
    │   └── logging_config.py
    │
    ├── agents/
    │   ├── router.py                 # Intent classifier (pipeline vs chat routing)
    │   ├── master_agent.py           # LangGraph workflow builder, runner, and checkpointer
    │   ├── chat_agent.py             # Conversational follow-up agent
    │   ├── common.py                 # Shared prompt builders, parsers, LLM client cache
    │   ├── finance_agent.py
    │   ├── rd_agent.py
    │   ├── legal_agent.py
    │   └── operations_agent.py
    │
    ├── reasoning/
    │   ├── aggregator.py             # Confidence-ranked strategic aggregator node
    │   ├── confidence.py             # Multi-factor confidence scoring algorithms
    │   ├── similarity.py             # Vector similarity calculations
    │   ├── outcome_analysis.py       # Empirical success rate analysis
    │   └── explainability.py         # Human-readable audit trail generator
    │
    ├── services/
    │   ├── supabase_client.py        # Reusable Supabase client singleton
    │   └── case_retrieval_service.py # MMR diversity retrieval & candidate scoring
    │
    ├── storage/
    │   ├── embedder.py               # Local SentenceTransformer (all-MiniLM-L6-v2) embeddings
    │   ├── retriever.py              # pgvector RPC invocation interface
    │   └── sync_decisions_to_supabase.py # Dataset CSV importer with batched embedding upsert
    │
    ├── mcp/
    │   ├── server.py                 # FastMCP server exposing the 8 departmental tools
    │   └── client.py                 # Client managing MCP subprocess communication
    │
    ├── tools/
    │   ├── tool_executor.py          # Allowlist enforcement & execution dispatcher
    │   └── tool_registry.py          # Per-agent tool allowlists & schema provider
    │
    └── api/
        ├── routes.py                 # Native REST API (/api/query, /api/models, /api/threads)
        └── openai_compat.py          # OpenAI-compatible /v1/chat/completions for Open WebUI
```

---

## Setup & Installation

### 1. Install Dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Configure your credentials in `.env`:

```env
# Supabase (Source of Truth & pgvector)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key

# Model Providers
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Search Tools (Optional)
TAVILY_API_KEY=your_tavily_api_key

# Retrieval Hyperparameters (Optional - defaults shown)
RETRIEVAL_CANDIDATE_COUNT=25
RETRIEVAL_MIN_CASES=3
RETRIEVAL_MAX_CASES=10
RETRIEVAL_SIMILARITY_FLOOR=0.25
RETRIEVAL_MMR_LAMBDA=0.65
```

### 3. One-Time Database Setup

Execute `sql/001_setup.sql` in the Supabase SQL Editor. This script:
- Enables the `vector` extension.
- Creates `decisions` (with `embedding vector(384)`) and `outcomes` relational tables.
- Creates an HNSW vector index for cosine similarity search.
- Defines the `match_decisions` similarity-search stored procedure and chronology verification triggers.

### 4. Ingest Dataset & Generate Embeddings

```bash
python -m app.storage.sync_decisions_to_supabase
```

This parses `dataset/Decisions/decisions.csv` and `dataset/Outcome/outcomes.csv`, embeds all cases with `all-MiniLM-L6-v2`, and upserts them to Supabase in batches.

### 5. Run the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## Model Selection & Runtime Switching

All agents instantiate models dynamically via LangChain's `init_chat_model()` inside `app/agents/common.py:get_llm(model_id)`.

Supported model IDs:
- `ollama:qwen2.5:3b` *(default — local zero-cost inference)*
- `google_genai:gemini-3.8-flash`
- `groq:qwen/qwen3.8-27b`
- `groq:openai/gpt-oss-120b`
- `groq:openai/gpt-oss-20b`

Model preference is saved in LangGraph memory checkpoints per `thread_id`. If `model` is omitted in subsequent queries within the same thread, the thread's active model is automatically preserved.

---

## API Documentation

### Native REST API (`/api`)

#### 1. Strategic Decision Query
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Should we invest in expanding dual-sourcing for critical hardware components this quarter?",
    "thread_id": "session-1",
    "model": "google_genai:gemini-3.8-flash"
  }'
```

**Response Schema:**
```json
{
  "key_insights": [
    "Operations indicates supply disruption risks can be mitigated via secondary suppliers."
  ],
  "conflicts": [
    "Finance notes upfront qualification costs; Legal recommends accelerated compliance audits."
  ],
  "final_decision": {
    "decision": "Proceed with dual-sourcing for tier-1 components subject to margin thresholds."
  },
  "explainability": "[Finance]\nFound 3 relevant historical cases...\n[Operations]\n...",
  "retrieved_cases": {
    "Operations": [
      {
        "document": "...",
        "metadata": { "case_id": "1031", "similarity": 0.68 }
      }
    ]
  }
}
```

#### 2. Models Discovery
- `GET /api/models` — Returns supported models and identifies which are currently available based on configured API keys.
- `GET /api/threads/{thread_id}/model` — Returns the model configured for a given thread.

### OpenAI-Compatible API (`/v1`)

MARS exposes full OpenAI-compatible chat endpoints (`/v1/chat/completions` and `/v1/models`) designed for instant integration with **Open WebUI**, LangChain, or any OpenAI SDK client.
