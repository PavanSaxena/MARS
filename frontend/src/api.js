// Thin client for the FastAPI backend in backend/app/api/routes.py.
// Every function here maps 1:1 to one endpoint; nothing here should need
// to change unless the backend's routes/response shapes change.

export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (networkErr) {
    throw new ApiError(
      `Couldn't reach the backend at ${API_BASE}. Is it running?`,
      0
    );
  }

  if (!res.ok) {
    // FastAPI's HTTPException body is {"detail": "..."} — surface that
    // directly since it's already a human-readable message (see routes.py).
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* body wasn't JSON, fall back to statusText */
    }
    throw new ApiError(detail, res.status);
  }

  return res.json();
}

/** GET /api/models — { models, default, unavailable } */
export function listModels() {
  return request("/models");
}

/** GET /api/threads/{thread_id}/model — { thread_id, model } */
export function getThreadModel(threadId) {
  return request(`/threads/${encodeURIComponent(threadId)}/model`);
}

/**
 * POST /api/query — the main entry point.
 * @param {{ query: string, threadId: string, model?: string }} params
 * @returns {Promise<{
 *   key_insights: string[],
 *   conflicts: string[],
 *   final_decision: { decision: string, risk_level: string|null, roi: string|null, notes: string|null },
 *   explainability: string|null,
 * }>}
 */
export function submitQuery({ query, threadId, model }) {
  return request("/query", {
    method: "POST",
    body: JSON.stringify({
      query,
      thread_id: threadId,
      ...(model ? { model } : {}),
    }),
  });
}

export { ApiError };
