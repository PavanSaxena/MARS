"""
OpenAI-compatible adapter for Open WebUI (or any OpenAI-client-compatible
frontend).

MARS's native API (POST /api/query, GET /api/models in app/api/routes.py)
returns a structured decision object, not an OpenAI chat completion. Open
WebUI only knows how to speak the OpenAI (or Ollama) wire format, so this
router translates between the two without touching any of the LangGraph /
agent logic underneath.

Mount this in main.py alongside the existing router:

    from app.api.openai_compat import router as openai_router
    app.include_router(openai_router)   # no "/api" prefix - OpenAI clients
                                         # expect routes at /v1/...

Then in Open WebUI: Admin Settings -> Connections -> OpenAI API
  URL:  http://<this-backend-host>:8000/v1
  Key:  any non-empty string (MARS doesn't check it; see note below)
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.master_agent import run_graph
from app.api.routes import parse_result
from app.core.config import settings

router = APIRouter()


# --------------------------------------------------------------------------- #
# OpenAI wire schema (only the fields Open WebUI actually sends/reads)
# --------------------------------------------------------------------------- #


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    # Open WebUI/OpenAI clients send other fields (temperature, max_tokens,
    # etc.) - MARS's graph doesn't take them, so they're accepted and
    # silently ignored rather than rejected.
    temperature: float | None = None
    max_tokens: int | None = None
    # Not part of the OpenAI schema. Open WebUI's connection layer doesn't
    # expose a way to add a custom outbound header per-request, but a Filter
    # function's inlet() *can* stick an extra key straight onto the request
    # body before it's sent - see the mars-chat-id-filter Function. Declared
    # explicitly here so pydantic keeps it instead of silently dropping it;
    # the x-chat-id header (below) still takes priority when both are sent.
    chat_id: str | None = None


class ModelCard(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "mars"


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelCard]


# --------------------------------------------------------------------------- #
# GET /v1/models
# --------------------------------------------------------------------------- #


@router.get("/v1/models", response_model=ModelList)
def list_models_openai():
    """Only advertise models that actually have a provider API key configured
    - listing an unusable model just gives Open WebUI's user a 400 later."""
    usable = [m for m in settings.AVAILABLE_MODELS if settings.api_key_for_model(m)]
    return {"data": [{"id": m} for m in usable]}


# --------------------------------------------------------------------------- #
# POST /v1/chat/completions
# --------------------------------------------------------------------------- #


def _thread_id_for(messages: list[ChatMessage]) -> str:
    """Open WebUI has no concept of MARS's thread_id - it just resends the
    full message history every turn. Derive a stable id from the first user
    message in the conversation so the same chat keeps hitting the same
    LangGraph checkpoint thread across turns, while a different chat (a
    different first message) lands on a different thread.

    This is a pragmatic default, not a perfect one: editing/deleting the
    first message in Open WebUI will start a "new" thread on the backend.
    Only used when neither the `x-chat-id` header nor a `chat_id` field in
    the body was supplied - see chat_completions() below.
    """
    first_user = next((m.content for m in messages if m.role == "user"), "")
    digest = hashlib.sha256(first_user.encode("utf-8")).hexdigest()[:16]
    return f"openwebui-{digest}"


def _latest_user_message(messages: list[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    raise HTTPException(status_code=400, detail="No user message found in request.")


# Matches the "[Department]" markers aggregator_agent() writes at the start
# of each explainability block (see app/reasoning/aggregator.py) so they can
# be turned into real markdown subheadings instead of literal bracket text.
_DEPT_MARKER_RE = re.compile(r"^\[([^\]]+)\]", re.MULTILINE)


def _format_markdown(structured: dict[str, Any]) -> str:
    """Flatten MARS's structured decision (key_insights / conflicts /
    final_decision / explainability) into a single, clean markdown string,
    since Open WebUI only renders chat message text - no raw brackets or
    ambiguous spacing that could render oddly."""
    parts: list[str] = []

    fd = structured.get("final_decision") or {}
    if fd.get("decision"):
        parts.append(f"### Final Decision\n{fd['decision'].strip()}")
    meta_bits = []
    if fd.get("risk_level"):
        meta_bits.append(f"**Risk level:** {fd['risk_level']}")
    if fd.get("roi"):
        meta_bits.append(f"**ROI:** {fd['roi']}")
    if meta_bits:
        parts.append("  \n".join(meta_bits))
    if fd.get("notes"):
        parts.append(f"**Notes:** {fd['notes']}")

    if structured.get("key_insights"):
        bullets = "\n".join(f"- {i}" for i in structured["key_insights"])
        parts.append(f"### Key Insights\n{bullets}")

    if structured.get("conflicts"):
        bullets = "\n".join(f"- {c}" for c in structured["conflicts"])
        parts.append(f"### Conflicts\n{bullets}")

    if structured.get("explainability"):
        # "[Finance]\n...text..." -> "#### Finance\n...text..." so each
        # department renders as its own subheading instead of plain
        # bracketed text sitting in one undifferentiated block.
        body = _DEPT_MARKER_RE.sub(r"#### \1", structured["explainability"].strip())
        parts.append(f"### Explainability\n{body}")

    return "\n\n".join(parts) if parts else "The model did not return a decision."


def _format_evidence_block(retrieved_cases: dict) -> str:
    """Render the per-department retrieved cases as a collapsible markdown
    section. Each case shows its ID, quarter, similarity score, risk level,
    outcome, and the key text the agent used to ground its reasoning."""
    if not retrieved_cases:
        return ""

    lines = ["---", "### Evidence Used",
             "*Historical cases retrieved from the dataset that grounded each agent's reasoning.*"]
    for dept, cases in retrieved_cases.items():
        if not cases:
            continue
        lines.append(f"\n#### {dept}")
        for c in cases:
            cid = c.get("case_id", "—")
            quarter = c.get("quarter", "")
            sim = c.get("similarity")
            sim_str = f"{sim:.2f}" if isinstance(sim, (int, float)) else "—"
            risk = c.get("risk_level", "")
            outcome = c.get("outcome", "")
            doc = (c.get("document") or "").strip()
            if doc:
                formatted_lines = []
                for line in doc.split("\n"):
                    line_str = line.strip()
                    if not line_str:
                        continue
                    if ":" in line_str:
                        key, val = line_str.split(":", 1)
                        formatted_lines.append(f"  > **{key.strip()}:**{val}")
                    else:
                        formatted_lines.append(f"  > {line_str}")
                formatted_doc = "\n".join(formatted_lines)
            else:
                formatted_doc = "  > *No details provided.*"

            lines.append(
                f"- **Case {cid}** ({quarter}) | Similarity: {sim_str} | Risk: {risk} | Outcome: {outcome}\n"
                f"{formatted_doc}\n"
            )
    return "\n".join(lines)


def _chat_completion_payload(model: str, content: str) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        # MARS doesn't track token counts - zeros keep the field present
        # without lying about real usage.
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _sse_stream(model: str, content: str):
    """Fake a single-chunk stream: MARS has no token-level streaming
    (run_graph blocks until all four agents + the aggregator finish), so the
    whole answer is sent as one SSE delta. Open WebUI's stream parser
    accepts this fine - it just renders the chunk as soon as it arrives."""
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    delta_payload = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": content},
                "finish_reason": None,
            }
        ],
    }
    yield f"data: {json.dumps(delta_payload)}\n\n"

    stop_payload = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(stop_payload)}\n\n"
    yield "data: [DONE]\n\n"


from app.core.errors import is_rate_limit_error, format_rate_limit_error


@router.post("/v1/chat/completions")
def chat_completions(
    request: ChatCompletionRequest,
    x_chat_id: str | None = Header(default=None, alias="x-chat-id"),
):
    if request.model not in settings.AVAILABLE_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{request.model}'. See GET /v1/models for valid options.",
        )
    if not settings.api_key_for_model(request.model):
        provider = request.model.split(":", 1)[0]
        raise HTTPException(
            status_code=400,
            detail=f"Model '{request.model}' requires a {provider.upper()}_API_KEY to be set in .env.",
        )

    user_input = _latest_user_message(request.messages)
    # Priority: an explicit x-chat-id header, then a chat_id the Open WebUI
    # filter stuck in the body, then the content-hash fallback. Header takes
    # precedence since it's the more deliberate/explicit of the two.
    thread_id = x_chat_id or request.chat_id or _thread_id_for(request.messages)

    try:
        raw_result, retrieved_cases = run_graph(
            user_input=user_input, thread_id=thread_id, model=request.model
        )
    except Exception as exc:
        if is_rate_limit_error(exc):
            raw_result = format_rate_limit_error(exc, model_name=request.model)
            retrieved_cases = {}
        else:
            raise exc

    if "Provider Rate Limit Reached" in raw_result or "Rate limit" in raw_result:
        content = raw_result
    else:
        structured = parse_result(raw_result)
        content = _format_markdown(structured)
        evidence = _format_evidence_block(retrieved_cases)
        if evidence:
            content = f"{content}\n\n{evidence}"

    if request.stream:
        return StreamingResponse(
            _sse_stream(request.model, content),
            media_type="text/event-stream",
        )

    return _chat_completion_payload(request.model, content)
