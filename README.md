# MARS — Multi-Agent Reasoning System

A multi-agent AI decision system built with **LangGraph**, **LangChain**, **ChromaDB**, **Supabase**, and **FastAPI**.

Given a strategic business query, MARS fans out to four specialist agents (Finance, R&D, Legal, Operations) in parallel, then aggregates their outputs into a single, conflict-resolved recommendation.

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
                 │ Aggregator │  (conflict resolution + final plan)
                 └────────────┘
                        │
                        ▼
                  Final Decision
```

Each department agent:
1. Embeds the query with `all-MiniLM-L6-v2`
2. Retrieves the top-5 most similar historical cases from ChromaDB (filtered by department)
3. Sends the query + cases to `llama-3.3-70b-versatile` (via Groq) for structured reasoning
4. Returns a parsed `{response, reasoning, confidence}` dict into the shared LangGraph state

The Aggregator then synthesises all four outputs and resolves conflicts with the priority order: **Legal > Finance > Operations > R&D**.

---

## Project Structure

```
.
├── main.py                          # FastAPI app entry point
├── pyproject.toml
├── requirements.txt
├── .env                             # GROQ_API_KEY, SUPABASE_URL, SUPABASE_KEY
├── chroma_db                        # Stores case based embeddings
│
└── app/
    ├── state.py                     # Shared LangGraph State (TypedDict)
    │
    ├── agents/
    │   ├── master_agent.py          # Graph builder + run_graph()
    │   ├── finance_agent.py
    │   ├── rd_agent.py
    │   ├── legal_agent.py
    │   └── operations_agent.py
    │
    ├── reasoning/
    │   ├── aggregator.py            # Conflict-resolving aggregator node
    │   ├── confidence.py            # Weighted confidence scorer
    │   ├── similarity.py            # Average vector similarity
    │   ├── outcome_analysis.py      # Historical success rate
    │   └── explainability.py        # Human-readable explanation generator
    │
    ├── services/
    │   └── case_retrieval_service.py  # get_similar_cases() + CaseRetrievalService
    │
    ├── storage/
    │   └── chroma_store/
    │       ├── chroma_client.py     # get_collection()
    │       ├── embedder.py          # get_embedding()
    │       ├── retriever.py         # retrieve_cases()
    │       └── index_cases.py       # One-time Supabase → ChromaDB indexing script
    │
    └── api/
        └── routes.py                # POST /api/query

```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
TAVILY_API_KEY=your_tavily_api_key   # optional, used by master agent search tool
```

### 3. Index cases into ChromaDB

Open new Terminal and run the ChromaDB instance:

```bash
chroma run --path ./chroma_db --port 8001
```

Then run case base indexers (this only needs to be run once or whenever your Supabase data changes):

```bash
python -m app.storage.index_cases
```

### 4. Run the API server

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

---

## API Usage

### `POST /api/query`

Submit a strategic query to the multi-agent system.

**Request body:**
```json
curl -s -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Should we invest in an AI-driven supply chain optimization initiative this quarter?", "thread_id": "test-1"}' | jq
```

**Response:**
```json
{
  "key_insights": [
    "The Finance department recommends caution and a thorough analysis of ROI, implementation costs, and feasibility before investing in an AI-driven supply chain optimization initiative.",
    "The R&D department advises against investment at this time due to uncertainty in technical feasibility, innovation potential, and technology risks.",
    "Lack of relevant case evidence and specific data hinders decision-making across departments.",
    "The Legal and Operations departments did not provide input, which may impact the completeness of the assessment."
  ],
  "conflicts": [
    "None detected, as there is no direct contradiction between the Finance and R&D departments' recommendations. The Finance department suggests a cautious approach with further analysis, while the R&D department recommends not investing at this time."
  ],
  "final_decision": {
    "decision": "Given the cautious recommendation from the Finance department and the R&D department's advice against investment, coupled with the absence of input from Legal and Operations, the recommended course of action is to postpone the investment decision in the AI-driven supply chain optimization initiative until further analysis and assessments can be conducted. This includes gathering more specific data on potential ROI, implementation costs, technical feasibility, and obtaining input from the Legal and Operations departments to ensure a comprehensive understanding of the initiative's implications."
  }
}
```
