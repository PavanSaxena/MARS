import re
import time
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agents.master_agent import run_graph, get_thread_model
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    thread_id: str = "default"
    model: str | None = None  # e.g. "groq:openai/gpt-oss-120b" — see GET /api/models.
    # Omit to keep using whatever model this thread_id was already on
    # (defaults to settings.DEFAULT_MODEL for a brand-new thread).

class ModelsResponse(BaseModel):
    models: list[str]
    default: str
    unavailable: list[str]  # models in `models` whose provider API key isn't configured

class ThreadModelResponse(BaseModel):
    thread_id: str
    model: str

class FinalDecision(BaseModel):
    decision: str
    risk_level: str | None = None
    roi: str | None = None
    notes: str | None = None

class QueryResponse(BaseModel):
    key_insights: list[str]
    conflicts: list[str]
    final_decision: FinalDecision
    explainability: str | None = None
    # Per-department list of the historical cases used to ground each agent's
    # reasoning. Keys are department names ("Finance", "R&D", "Legal",
    # "Operations"); each value is a list of slim case dicts.
    retrieved_cases: dict | None = None

_SECTION_NAMES = ["Key Insights", "Conflicts", "Final Decision", "Explainability"]
# Header lines are matched leniently: case-insensitive, optional markdown
# emphasis (** or __ around the name), and an optional trailing colon — the
# aggregator prompt asks for e.g. "Final Decision:" but LLM output doesn't
# always come back in exactly that literal form (different casing, bolded
# as "**Final Decision:**", etc.), and a strict literal match on the old
# parser silently dropped whichever sections didn't match, which produced
# an empty final_decision dict and failed response validation entirely.
_HEADER_RE = re.compile(
    r"^[ \t]*[*_]{0,2}[ \t]*(" + "|".join(re.escape(n) for n in _SECTION_NAMES) + r")[ \t]*[*_:]*[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)

def parse_result(text: str):
    """
    Header-based section parser (not blank-line based), so a multi-block
    Explainability section (one block per department, separated by blank
    lines) doesn't get chopped up or dropped.

    Header matching is intentionally lenient (see _HEADER_RE) since the
    aggregator's output is free-form LLM text, not a constrained format.
    If no recognizable "Final Decision" section is found at all, falls
    back to using the full raw text as the decision rather than returning
    an empty dict, since QueryResponse.final_decision.decision is required
    and a parsing miss shouldn't turn into a 500 for the caller.
    """
    data = {
        "key_insights": [],
        "conflicts": [],
        "final_decision": {},
        "explainability": None,
    }

    matches = list(_HEADER_RE.finditer(text))

    for i, match in enumerate(matches):
        name = match.group(1).strip().lower()
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()

        if name == "key insights":
            data["key_insights"] = [
                line.strip().lstrip("*-•").strip()
                for line in body.splitlines()
                if line.strip()
            ]

        elif name == "conflicts":
            data["conflicts"] = [
                line.strip().lstrip("*-•").strip()
                for line in body.splitlines()
                if line.strip() and line.strip().lower() != "none detected"
            ]

        elif name == "final decision":
            if body:
                data["final_decision"] = {"decision": body}

        elif name == "explainability":
            data["explainability"] = body or None

    if not data["final_decision"].get("decision"):
        fallback_text = text.strip()
        data["final_decision"] = {
            "decision": fallback_text or "The model did not return a final decision."
        }

    return data

@router.get("/models", response_model=ModelsResponse)
def list_models():
    """Models the frontend can offer in a switcher, plus which ones can't
    actually be used right now because their provider API key isn't set."""
    unavailable = [m for m in settings.AVAILABLE_MODELS if not settings.api_key_for_model(m)]
    return {
        "models": settings.AVAILABLE_MODELS,
        "default": settings.DEFAULT_MODEL,
        "unavailable": unavailable,
    }


@router.get("/threads/{thread_id}/model", response_model=ThreadModelResponse)
def thread_model(thread_id: str):
    """The model currently active for this thread (e.g. to restore a
    switcher's selection after a page reload)."""
    return {"thread_id": thread_id, "model": get_thread_model(thread_id)}


from app.core.errors import is_rate_limit_error, format_rate_limit_error


@router.post("/query", response_model=QueryResponse)
def query_system(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    if request.model is not None:
        if request.model not in settings.AVAILABLE_MODELS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown model '{request.model}'. See GET /api/models for valid options.",
            )
        if not settings.api_key_for_model(request.model):
            provider = request.model.split(":", 1)[0]
            raise HTTPException(
                status_code=400,
                detail=f"Model '{request.model}' requires a {provider.upper()}_API_KEY to be set in .env.",
            )

    logger.info(
        "query_received thread_id=%s model=%s query=%r",
        request.thread_id,
        request.model or "default",
        request.query[:120],
    )

    t_start = time.perf_counter()
    try:
        raw_result, retrieved_cases = run_graph(user_input=request.query, thread_id=request.thread_id, model=request.model)
    except Exception as exc:
        elapsed = round(time.perf_counter() - t_start, 3)
        if is_rate_limit_error(exc):
            logger.warning(
                "query_rate_limited thread_id=%s duration_s=%.3f",
                request.thread_id,
                elapsed,
            )
            raw_result = format_rate_limit_error(exc, model_name=request.model)
            retrieved_cases = {}
        else:
            logger.exception(
                "query_failed thread_id=%s duration_s=%.3f query=%r",
                request.thread_id,
                elapsed,
                request.query[:120],
            )
            raise exc

    elapsed = round(time.perf_counter() - t_start, 3)
    structured = parse_result(raw_result)
    structured["retrieved_cases"] = retrieved_cases or None

    dept_case_counts = {
        dept: len(cases)
        for dept, cases in (retrieved_cases or {}).items()
    }
    logger.info(
        "query_completed thread_id=%s duration_s=%.3f "
        "insights=%d conflicts=%d cases_by_dept=%s",
        request.thread_id,
        elapsed,
        len(structured.get("key_insights", [])),
        len(structured.get("conflicts", [])),
        dept_case_counts or "none",
    )

    return structured

