# MARS Frontend (planned)

Reserved for the future web UI. Not started yet.

Once built, it will talk to the backend API at `http://localhost:8000/api` (see
`../backend/app/api/routes.py`). The backend already has CORS configured for
local dev origins (`http://localhost:3000`, `http://localhost:5173`) in
`backend/app/core/config.py` — update `CORS_ORIGINS` there once the frontend's
dev server port is known.

Suggested request/response shape (see `POST /api/query`):

```json
// Request
{ "query": "string", "thread_id": "string" }

// Response
{
  "key_insights": ["string"],
  "conflicts": ["string"],
  "final_decision": { "decision": "string" },
  "explainability": "string | null"
}
```
