import json
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.reasoning.confidence import calculate_confidence
from app.reasoning.explainability import generate_explanation
from app.reasoning.outcome_analysis import analyze_outcomes
from app.reasoning.similarity import compute_similarity
from app.services.case_retrieval_service import get_similar_cases
from app.state import State
from app.core.logging_config import get_logger

logger = get_logger("agents.common")

_llm_cache: Dict[str, Any] = {}


def _normalize_content(content: Any) -> str:
    """Convert LLM response content to a plain string.

    Gemini returns content as a list of dicts like
    [{'type': 'text', 'text': '...', 'extras': {...}}] while other providers
    return a plain string. This normalises both to a string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", str(item)))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def get_llm(model_id: Optional[str] = None):
    """
    Return a cached chat model for the given "<provider>:<model>" id (see
    settings.AVAILABLE_MODELS), falling back to settings.DEFAULT_MODEL if
    model_id is None/unrecognized. This is the single place that turns a
    model id into a live LangChain chat model — every agent + the aggregator
    call this instead of hardcoding a provider/model.
    """
    from langchain.chat_models import init_chat_model

    resolved = model_id if model_id in settings.AVAILABLE_MODELS else settings.DEFAULT_MODEL

    if resolved not in _llm_cache:
        logger.info("llm_initializing model=%s", resolved)
        provider = resolved.split(":", 1)[0] if ":" in resolved else ""
        kwargs: Dict[str, Any] = {"max_retries": 10}
        if provider == "ollama":
            # When running inside Docker, localhost inside the container is the
            # container itself — not the host where Ollama listens. Use the
            # configured OLLAMA_BASE_URL (defaults to host.docker.internal:11434)
            # so the request escapes the container and reaches the host process.
            kwargs["base_url"] = settings.OLLAMA_BASE_URL
            logger.info(f"[get_llm] Ollama model '{resolved}' → base_url={settings.OLLAMA_BASE_URL}")
        _llm_cache[resolved] = init_chat_model(resolved, **kwargs)
    else:
        logger.info("llm_reused model=%s", resolved)
    return _llm_cache[resolved]


def extract_messages_and_query(state: State) -> Tuple[List[Any], str]:
    """Extract message history and current query from graph state."""
    messages = state.get("messages", [])
    if not messages:
        return messages, ""

    last_message = messages[-1]
    query = getattr(last_message, "content", "") or str(last_message)
    return messages, query


def empty_agent_result(output_key: str, messages: List[Any]) -> Dict[str, Any]:
    """Build a consistent fallback result when no input messages are present."""
    return {
        output_key: {
            "response": "No user message was provided.",
            "reasoning": "The agent received an empty message history.",
            "confidence": 0.0,
            "warnings": ["empty_messages"],
        },
        "messages": messages,
    }


def _format_case_for_prompt(case: dict, idx: int) -> str:
    metadata = case.get("metadata", {})
    case_id = metadata.get("case_id", idx)
    quarter = metadata.get("quarter", "")
    outcome = metadata.get("outcome") or case.get("outcome", "unknown")
    doc = case.get("document", "") or ""
    
    header = f"--- Case #{idx} [ID: {case_id}, Quarter: {quarter}, Outcome: {outcome}] ---"
    return f"{header}\n{doc}"


def _case_outcome_category(case: dict) -> str:
    """Return a conservative category from the explicit outcome label.

    Outcome prose is intentionally not keyword-classified here: it may contain
    both positive and negative observations, and the structured outcome label
    is the source of truth for contrastive prompt grouping.
    """
    metadata = case.get("metadata", {}) or {}
    label = metadata.get("outcome_label")
    if label is None:
        # Compatibility for callers and legacy data that already provide a
        # label in the older outcome field. Never infer from free-text prose.
        label = metadata.get("outcome") or case.get("outcome")

    normalized = str(label or "").strip().lower()
    if normalized in {"success", "failure", "unresolved", "mixed"}:
        return normalized
    return "unknown"


def _format_contrastive_case_context(cases: List[dict]) -> str:
    """Render each retrieved case once, grouped by its structured outcome."""
    group_specs = (
        ("success", "HISTORICAL SUCCESS PRECEDENTS (strategies to consider)"),
        ("failure", "HISTORICAL FAILURE WARNINGS (pitfalls and safeguards)"),
        ("mixed", "MIXED OR UNCERTAIN OUTCOMES"),
        ("unresolved", "UNRESOLVED OUTCOMES"),
        ("unknown", "OUTCOME NOT CLASSIFIED"),
    )
    grouped = {category: [] for category, _ in group_specs}
    for idx, case in enumerate(cases, start=1):
        grouped[_case_outcome_category(case)].append(_format_case_for_prompt(case, idx))

    sections = []
    for category, heading in group_specs:
        rendered = grouped[category]
        contents = "\n\n".join(rendered) if rendered else "No retrieved cases in this category."
        sections.append(f"=== {heading} ===\n{contents}")
    return "\n\n".join(sections)


def retrieve_case_context(
    query: str,
    domain: str,
    candidate_count: Optional[int] = None,
    min_cases: Optional[int] = None,
    max_cases: Optional[int] = None,
    k: Optional[int] = None,
) -> Tuple[List[dict], str, List[str]]:
    """Retrieve similar cases and return cases, rendered case text, and warning flags."""
    warnings: List[str] = []

    try:
        logger.info("retrieval_started domain=%s", domain)
        cases = get_similar_cases(
            query=query,
            domain=domain,
            candidate_count=candidate_count,
            min_cases=min_cases,
            max_cases=max_cases,
            k=k,
        )
    except Exception as e:
        cases = []
        warnings.append(f"retrieval_failed: {e}")
        logger.error(f"[{domain.upper()}] Case retrieval failed: {e}", exc_info=True)
        logger.exception("retrieval_failed domain=%s", domain)

    if cases:
        case_text = _format_contrastive_case_context(cases)
        logger.info(f"[{domain.upper()}] Retrieved {len(cases)} relevant cases")
    else:
        case_text = "No relevant cases found in dataset."
        warnings.append("no_similar_cases")
        logger.warning(f"[{domain.upper()}] No similar cases found for query")

    return cases, case_text, warnings


def build_case_evidence(
    cases: List[dict],
    tools_used: Optional[List[str]] = None,
    reported_confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute retrieval-side stats for the retrieved cases and attach a
    case_based_confidence placeholder (see app.reasoning.confidence).

    Returns a dict meant to be merged into an agent's output, e.g.:
        parsed_output.update(build_case_evidence(cases, tools_used, reported_confidence=parsed_output.get("confidence")))
    """
    similarity = compute_similarity(cases)
    success_rate = analyze_outcomes(cases)

    # Placeholder — always None until the weighting formula is finalized.
    case_based_confidence = calculate_confidence(
        similarity=similarity,
        past_success=success_rate,
    )

    # Only surface cases the agent actually considered useful for its answer.
    # When the agent reports confidence 0.0 it means it looked at the retrieved
    # records and decided none were relevant enough to ground a recommendation.
    # Showing those cases in the frontend would be misleading — it would imply
    # they informed the decision when they explicitly did not.
    agent_used_cases = (reported_confidence is None or reported_confidence > 0.0) and bool(cases)

    num_cases = len(cases) if agent_used_cases else 0

    slim_cases = (
        [
            {
                "case_id": c.get("metadata", {}).get("case_id"),
                "quarter": c.get("metadata", {}).get("quarter", ""),
                "department": c.get("metadata", {}).get("department", ""),
                "risk_level": c.get("metadata", {}).get("risk_level", ""),
                "outcome": c.get("metadata", {}).get("outcome", "unknown"),
                "outcome_label": c.get("metadata", {}).get("outcome_label"),
                "similarity": c.get("metadata", {}).get("similarity"),
                "document": c.get("document", ""),
            }
            for c in cases
        ]
        if agent_used_cases
        else []
    )

    return {
        "num_cases_retrieved": num_cases,
        "avg_similarity": round(similarity, 4) if agent_used_cases else None,
        "historical_success_rate": round(success_rate, 4) if agent_used_cases else None,
        "case_based_confidence": case_based_confidence,  # placeholder, TODO
        "tools_used": tools_used or [],
        "retrieved_cases": slim_cases,
        "explanation": generate_explanation(
            cases,
            case_based_confidence,
            tools_used,
            reported_confidence=reported_confidence,
        ),
    }


def build_json_prompt(
    agent_title: str,
    role_points: List[str],
    rules: List[str],
    query: str,
    case_text: str,
    tool_names: Optional[List[str]] = None,
) -> str:
    """Build a standardized JSON-only prompt for department agents."""
    role_block = "\n".join([f"- {item}" for item in role_points])
    rules_block = "\n".join([f"{idx}. {rule}" for idx, rule in enumerate(rules, start=1)])

    tools_block = ""
    if tool_names:
        tools_block = (
            "\nYou also have these tools available: "
            + ", ".join(tool_names)
            + ". Call one only if the retrieved cases and query alone aren't "
            "enough to answer well; otherwise answer directly without calling a tool.\n"
        )

    return f"""
You are a {agent_title} AI Agent.

Your role:
{role_block}

User Query:
{query}

Retrieved Historical Evidence from Dataset:
<<<CASE_EVIDENCE_START
{case_text}
<<<CASE_EVIDENCE_END>>>
{tools_block}
GROUNDING AND PRECEDENT DIRECTIVES:
1. Evidence-Based Reasoning: Base your assessment strictly on the historical precedents, analogous decisions, and outcomes provided in the Retrieved Evidence above.
2. Precedent Application:
   - Treat success cases as examples of strategies to consider and failure cases as warnings that may inform safeguards; neither category proves that an action will succeed or fail in the current situation.
   - Treat mixed, unresolved, and unclassified outcomes as uncertain. Do not use them as success or failure evidence.
   - Synthesize only lessons relevant to the current query from the retrieved cases.
   - In your "reasoning", cite specific Case IDs/titles from the evidence that inform your recommendation.
3. Strict Refusal ONLY When Database is Empty:
   - ONLY if the evidence explicitly states "No relevant cases found in dataset." with zero cases:
     {{
       "response": "No historical evidences/decisions found.",
       "reasoning": "No historical cases were retrieved from the dataset for this query. Without prior historical precedent, no evidence-grounded recommendation can be provided.",
       "confidence": 0.0
     }}
   - If cases ARE present above, you MUST use them as precedents rather than returning "No historical evidences/decisions found".
4. Confidence Score:
   - Set "confidence" between 0.0 and 1.0 reflecting the relevance and historical success rate of the retrieved cases.

Return ONLY valid JSON with this schema:
{{
  "response": "string",
  "reasoning": "string",
  "confidence": 0.0
}}

Rules:
{rules_block}
"""



def parse_structured_output(text: str) -> Dict[str, Any]:
    """Parse LLM output with JSON-first parsing and robust fallback."""
    try:
        parsed_json = _extract_json_object(text)
        if parsed_json is not None:
            return _normalize_output(parsed_json)
        return _normalize_output(_parse_sections_fallback(text))
    except Exception:
        return {"response": text, "reasoning": "Parsing failed", "confidence": 0.5}


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    stripped = text.strip()

    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", stripped)
    if not match:
        return None

    try:
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _parse_sections_fallback(text: str) -> Dict[str, Any]:
    sections: Dict[str, Any] = {"response": "", "reasoning": "", "confidence": 0.5}
    current_key: Optional[str] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()

        if lower.startswith("response"):
            current_key = "response"
            inline = _extract_inline_value(line)
            if inline:
                sections["response"] += inline + " "
            continue

        if lower.startswith("reasoning"):
            current_key = "reasoning"
            inline = _extract_inline_value(line)
            if inline:
                sections["reasoning"] += inline + " "
            continue

        if lower.startswith("confidence"):
            current_key = "confidence"
            inline = _extract_inline_value(line)
            parsed = _parse_confidence(inline or line)
            if parsed is not None:
                sections["confidence"] = parsed
            continue

        if current_key == "confidence":
            parsed = _parse_confidence(line)
            if parsed is not None:
                sections["confidence"] = parsed
        elif current_key in ("response", "reasoning"):
            sections[current_key] += line + " "

    # If no structured sections were found at all, treat the entire string as response & reasoning
    if not sections["response"] and not sections["reasoning"] and text.strip():
        sections["response"] = text.strip()
        sections["reasoning"] = text.strip()
        if any(phrase in text.lower() for phrase in ("no historical", "no evidence", "no relevant cases", "not found")):
            sections["confidence"] = 0.0

    return sections


def _extract_inline_value(line: str) -> str:
    parts = line.split(":", 1)
    return parts[1].strip() if len(parts) == 2 else ""


def _parse_confidence(value: str) -> Optional[float]:
    if not value:
        return None

    try:
        return float(value)
    except ValueError:
        match = re.search(r"[-+]?\d*\.?\d+", value)
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None


def _normalize_output(data: Dict[str, Any]) -> Dict[str, Any]:
    response = str(data.get("response", "")).strip()
    reasoning = str(data.get("reasoning", "")).strip()

    raw_confidence = data.get("confidence", 0.5)
    parsed_confidence = _parse_confidence(str(raw_confidence))
    
    # If the response explicitly states no historical evidence was found, confidence must be 0.0
    combined_text = f"{response} {reasoning}".lower()
    if any(phrase in combined_text for phrase in ("no historical", "no evidence", "no relevant cases", "no prior historical")):
        confidence = 0.0
    else:
        confidence = 0.5 if parsed_confidence is None else max(0.0, min(1.0, parsed_confidence))

    return {
        "response": response,
        "reasoning": reasoning,
        "confidence": confidence,
    }



def _recover_json_tool_error(exc: Exception) -> Optional[Dict[str, Any]]:
    """
    gpt-oss models on Groq (Harmony response format) sometimes encode their
    final JSON answer as a synthetic tool call named "json" instead of
    returning plain content — this happens when real tools are also bound,
    regardless of tool_choice. Groq's API rejects the synthetic call with
    tool_use_failed / "attempted to call tool 'json' which was not in
    request.tools", but the model's actual answer survives intact inside the
    error's `failed_generation` field. This pulls it back out instead of
    losing the turn.

    Returns the recovered {"response", "reasoning", "confidence"} dict, or
    None if `exc` doesn't match this shape (in which case the caller should
    re-raise the original exception).
    """
    body = getattr(exc, "body", None)
    if not isinstance(body, dict):
        return None

    error = body.get("error")
    if not isinstance(error, dict) or error.get("code") != "tool_use_failed":
        return None

    failed_generation = error.get("failed_generation")
    if not isinstance(failed_generation, str):
        return None

    try:
        generation = json.loads(failed_generation)
    except Exception:
        return None

    if not isinstance(generation, dict):
        return None

    # Expected shape: {"name": "json", "arguments": {"response": ..., ...}}
    # The synthetic tool name's casing isn't stable across gpt-oss runs
    # (observed both "json" and "JSON"), so match it case-insensitively
    # rather than assuming one fixed spelling.
    name = generation.get("name")
    arguments = generation.get("arguments")
    if isinstance(name, str) and name.lower() == "json" and isinstance(arguments, dict):
        return arguments

    # Fallback: some variants may emit the arguments dict directly.
    if "response" in generation:
        return generation

    return None


def _invoke_recovering_json_tool_error(llm_with_tools: Any, messages: Any) -> Any:
    """
    Call llm_with_tools.invoke(messages), transparently recovering from the
    gpt-oss synthetic-"json"-tool-call failure (see
    _recover_json_tool_error). On recovery, returns an AIMessage carrying the
    recovered answer as its content (with no tool_calls), so callers can
    treat it exactly like a normal final answer. Any other exception is
    re-raised unchanged.
    """
    from langchain_core.messages import AIMessage

    try:
        return llm_with_tools.invoke(messages)
    except Exception as exc:
        recovered = _recover_json_tool_error(exc)
        if recovered is None:
            raise
        return AIMessage(content=json.dumps(recovered))


def run_llm_with_tools(
    llm: Any,
    prompt: str,
    tools: List[Any],
    agent_name: str,
) -> Tuple[str, List[str], Any]:
    """
    Bind `tools` to `llm`, let it optionally call one of them, execute any
    tool calls via app.tools.tool_executor.execute_tool_call (respecting the
    same per-agent allowlist as app.tools.tool_registry), feed the result(s)
    back to the model, and return the final answer.

    This is the "Agent Specific Tool Call" step from the architecture
    diagram: the department agent decides whether it needs a tool, the tool
    executes, and the result flows back into that agent's decision output.

    Returns:
        (final_text, tool_names_used, final_message)
        final_message is the AIMessage-like object to append to graph state.
    """
    from langchain_core.messages import HumanMessage, ToolMessage
    from app.tools.tool_executor import execute_tool_call

    if not tools:
        logger.info("llm_tool_phase_skipped agent=%s", agent_name)
        logger.info(f"[{agent_name}] Running LLM inference (no tools bound)")
        response = llm.invoke(prompt)
        return _normalize_content(getattr(response, "content", str(response))), [], response

    # tool_choice="auto" is explicit here (langchain's bind_tools default is
    # already "auto" on every provider we use) for clarity, but note it does
    # NOT prevent the gpt-oss synthetic-"json"-tool-call failure below — that
    # is the model's own choice of how to encode its final answer under
    # Harmony's JSON-constraint mechanism, not a matter of whether a tool
    # call happens at all. See _recover_json_tool_error for the actual fix.
    try:
        logger.info(f"[{agent_name}] Running LLM inference with {len(tools)} tools: {[t.name for t in tools]}")
        logger.info("llm_tool_decision_started agent=%s", agent_name)
        llm_with_tools = llm.bind_tools(tools, tool_choice="auto")
        ai_message = _invoke_recovering_json_tool_error(llm_with_tools, prompt)
    except Exception as e:
        if "tool calling" in str(e).lower() or "not supported" in str(e).lower():
            logger.warning(f"[{agent_name}] Tool calling not supported by provider ({e}), falling back to direct prompt")
            response = llm.invoke(prompt)
            return _normalize_content(getattr(response, "content", str(response))), [], response
        logger.error(f"[{agent_name}] Error during tool-bound LLM invocation: {e}", exc_info=True)
        raise e

    tool_calls = getattr(ai_message, "tool_calls", None) or []
    if not tool_calls:
        logger.info("llm_tool_decision_finished agent=%s tool_calls=0", agent_name)
        logger.info(f"[{agent_name}] Model decided not to call any tools; returning direct answer")
        return _normalize_content(getattr(ai_message, "content", str(ai_message))), [], ai_message

    logger.info("llm_tool_decision_finished agent=%s tool_calls=%d", agent_name, len(tool_calls))
    messages: List[Any] = [HumanMessage(content=prompt), ai_message]
    used_tools: List[str] = []

    for call in tool_calls:
        tool_name = call.get("name")
        args = call.get("args", {}) or {}

        logger.info(f"[{agent_name}] Executing tool call '{tool_name}' with args: {args}")
        logger.info("tool_call_requested agent=%s tool=%s", agent_name, tool_name)
        result = execute_tool_call(agent_name, tool_name, args)
        logger.info("tool_call_finished agent=%s tool=%s status=%s", agent_name, tool_name, result.get("status"))
        used_tools.append(tool_name)

        tool_content = (
            str(result.get("result"))
            if result.get("status") == "success"
            else f"Tool error: {result.get('message')}"
        )
        logger.info(f"[{agent_name}] Tool '{tool_name}' returned status={result.get('status')}")
        messages.append(ToolMessage(content=tool_content, tool_call_id=call.get("id") or tool_name))

    # Invoke base llm (without tools bound) so the model is forced to synthesize
    # the final structured JSON response rather than attempting another tool call.
    logger.info(f"[{agent_name}] Synthesizing final answer after {len(used_tools)} tool call(s)")
    logger.info("llm_tool_follow_up_started agent=%s", agent_name)
    final_message = llm.invoke(messages)
    logger.info("llm_tool_follow_up_finished agent=%s", agent_name)
    return _normalize_content(getattr(final_message, "content", str(final_message))), used_tools, final_message
