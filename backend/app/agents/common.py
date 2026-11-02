import json
<<<<<<< Updated upstream
import re
=======
import os
import random
import re
import threading
import time
>>>>>>> Stashed changes
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.reasoning.confidence import calculate_confidence, calculate_confidence_with_details
from app.reasoning.explainability import generate_explanation
from app.reasoning.outcome_analysis import analyze_outcomes
from app.reasoning.similarity import compute_similarity
from app.services.case_retrieval_service import get_similar_cases
from app.state import State

# ---------------------------------------------------------------------------
# Bound simultaneous provider requests across parallel department agents.
# ---------------------------------------------------------------------------
_LLM_MAX_CONCURRENCY = max(1, int(os.getenv("MARS_LLM_MAX_CONCURRENCY", "2")))
_LLM_SEMAPHORE = threading.Semaphore(_LLM_MAX_CONCURRENCY)

_llm_cache: Dict[str, Any] = {}

# ---------------------------------------------------------------------------
# Tool-name validation helpers
# ---------------------------------------------------------------------------

def _canonical_tool_names(tools: List[Any]) -> set:
    """Return the set of exact tool names as sent to the LLM in bind_tools."""
    return {getattr(t, "name", None) for t in tools if getattr(t, "name", None)}


def _is_valid_tool_name(name: Optional[str], registered: set) -> bool:
    """Return True only if `name` exactly matches a registered tool name."""
    return isinstance(name, str) and name in registered


def _get_required_args(tool: Any) -> set:
    """
    Return the set of required argument names for a tool object.
    Works with both LangChain StructuredTool (args_schema) and plain
    SimpleNamespace stubs used in tests.
    """
    schema = getattr(tool, "args_schema", None)
    if schema is None:
        return set()
    try:
        props = schema.schema().get("properties", {})
        required = schema.schema().get("required", list(props.keys()))
        return set(required)
    except Exception:
        return set()


def _tool_arguments_error(tool: Any, args: Any) -> Optional[str]:
    """Return a validation error for malformed or incomplete tool arguments."""
    if not isinstance(args, dict):
        return "arguments must be a JSON object"
    missing = _get_required_args(tool) - {
        key for key, value in args.items() if value is not None and value != ""
    }
    if missing:
        return f"missing required argument(s): {', '.join(sorted(missing))}"
    return None


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
        _llm_cache[resolved] = init_chat_model(resolved, max_retries=10)
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

    if cases:
        case_text = "\n\n".join([_format_case_for_prompt(case, i + 1) for i, case in enumerate(cases)])
    else:
        case_text = "No relevant cases found in dataset."
        warnings.append("no_similar_cases")

    return cases, case_text, warnings


def build_case_evidence(
    cases: List[dict],
    tools_used: Optional[List[str]] = None,
    reported_confidence: Optional[float] = None,
    query: Optional[str] = None,
    department: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute retrieval-side stats for the retrieved cases and attach a
    calibrated multi-factor case_based_confidence (see app.reasoning.confidence).

    Dynamically incorporates Query-Adaptive Weighting conditioned on the query
    and the specialist agent's domain mandate.

    Returns a dict meant to be merged into an agent's output, e.g.:
        parsed_output.update(build_case_evidence(cases, tools_used, query=query, department="finance"))
    """
    similarity = compute_similarity(cases)
    success_rate = analyze_outcomes(cases)

    # Only surface cases the agent actually considered useful for its answer.
    agent_used_cases = bool(cases) and similarity > 0.0

    case_based_confidence, weight_info = (
        calculate_confidence_with_details(cases=cases, query=query, department=department)
        if agent_used_cases
        else (0.0, {})
    )

    num_cases = len(cases) if agent_used_cases else 0

    slim_cases = (
        [
            {
                "case_id": c.get("metadata", {}).get("case_id"),
                "quarter": c.get("metadata", {}).get("quarter", ""),
                "department": c.get("metadata", {}).get("department", ""),
                "risk_level": c.get("metadata", {}).get("risk_level", ""),
                "outcome": c.get("metadata", {}).get("outcome", "unknown"),
                "similarity": c.get("metadata", {}).get("similarity"),
                "document": c.get("document", ""),
            }
            for c in cases
        ]
        if agent_used_cases
        else []
    )

    from app.reasoning.conformal_predictor import ConformalRiskController
    _conformal_controller = ConformalRiskController(alpha=0.05)
    conformal_bound = _conformal_controller.evaluate_decision_bound(
        point_confidence=case_based_confidence,
        cases_count=num_cases
    )

    final_conf = round(case_based_confidence, 4) if agent_used_cases else 0.0

    return {
        "num_cases_retrieved": num_cases,
        "avg_similarity": round(similarity, 4) if agent_used_cases else None,
        "historical_success_rate": round(success_rate, 4) if agent_used_cases else None,
        "confidence": final_conf,
        "case_based_confidence": final_conf,
        "dynamic_weights": weight_info.get("weights"),
        "weight_rationale": weight_info.get("rationale"),
        "weight_telemetry": weight_info,
        "conformal_bound": {
            "confidence_interval": list(conformal_bound.confidence_interval),
            "coverage_guarantee": conformal_bound.coverage_guarantee,
            "risk_level": conformal_bound.risk_level,
            "decision_policy": conformal_bound.decision_policy,
            "policy_rationale": conformal_bound.policy_rationale,
        },
        "tools_used": tools_used or [],
        "retrieved_cases": slim_cases,
        "explanation": generate_explanation(
            cases,
            case_based_confidence,
            tools_used,
            reported_confidence=reported_confidence,
            weight_rationale=weight_info.get("rationale"),
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
   - Treat the retrieved cases as organizational precedents (e.g. past decisions on pricing, compliance, platform updates, supply chain adjustments, or risk mitigation).
   - Synthesize lessons learned from these cases to answer the user query.
   - In your "reasoning", cite specific Case IDs/titles from the evidence that inform your recommendation.
3. Strict Refusal ONLY When Database is Empty:
   - ONLY if the evidence explicitly states "No relevant cases found in dataset." with zero cases:
     {{
       "response": "No historical evidences/decisions found.",
       "reasoning": "No historical cases were retrieved from the dataset for this query. Without prior historical precedent, no evidence-grounded recommendation can be provided."
     }}
   - If cases ARE present above, you MUST use them as precedents rather than returning "No historical evidences/decisions found".

Return ONLY valid JSON with this schema:
{{
  "response": "string",
  "reasoning": "string"
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


<<<<<<< Updated upstream
def _invoke_recovering_json_tool_error(llm_with_tools: Any, messages: Any) -> Any:
=======
def _invoke_with_rate_limit_retry(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """
    Invoke an LLM call with bounded exponential backoff + jitter for Groq
    per-minute rate limits (TPM/ITPM).

    - Daily limit (TPD): re-raised immediately; the department boundary marks
      that department unavailable.
    - Per-minute limit (429): exponential backoff with ±25 % jitter, capped
      at 20 s per wait and 4 total attempts.
    - A process-wide semaphore bounds concurrent provider calls.
    """
    _MAX_ATTEMPTS = 4
    _BASE_WAIT = 1.0
    _MAX_WAIT = 20.0

    for attempt in range(_MAX_ATTEMPTS):
        with _LLM_SEMAPHORE:
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                err_str = str(e)
                if "tokens per day" in err_str.lower() or "tpd" in err_str.lower():
                    raise

                if not ("429" in err_str or "rate limit" in err_str.lower() or "too many" in err_str.lower()):
                    raise

                # Parse "try again in Xs" hint from Groq response body if present
                match = re.search(r"try again in (\d+(?:\.\d+)?)\s*(s|m|h)?", err_str, re.IGNORECASE)
                if match:
                    hint_sec = float(match.group(1))
                    unit = (match.group(2) or "s").lower()
                    if unit == "m":
                        hint_sec *= 60
                    elif unit == "h":
                        hint_sec *= 3600
                    base = min(max(hint_sec, _BASE_WAIT), _MAX_WAIT)
                else:
                    # Exponential backoff: 1, 2, 4, 8 … capped at _MAX_WAIT
                    base = min(_BASE_WAIT * (2 ** attempt), _MAX_WAIT)

                # ±25 % jitter to de-correlate concurrent agent retries
                jitter = base * 0.25 * (2 * random.random() - 1)
                wait_sec = min(max(base + jitter, _BASE_WAIT), _MAX_WAIT)

                logger.warning(
                    "[Rate Limit] Waiting %.1fs before retry (attempt %d/%d)...",
                    wait_sec, attempt + 1, _MAX_ATTEMPTS,
                )

        # Sleep outside the semaphore so other agents can make progress.
        if attempt + 1 < _MAX_ATTEMPTS:
            time.sleep(wait_sec)

    raise RuntimeError(
        f"Exceeded maximum attempts ({_MAX_ATTEMPTS}) for LLM invocation due to rate limiting"
    )


def _invoke_recovering_json_tool_error(
    llm_with_tools: Any, messages: Any, fallback_llm: Any = None
) -> Any:
>>>>>>> Stashed changes
    """
    Call llm_with_tools.invoke(messages), transparently recovering from the
    gpt-oss synthetic-"json"-tool-call failure (see
    _recover_json_tool_error). On recovery, returns an AIMessage carrying the
    recovered answer as its content (with no tool_calls), so callers can
    treat it exactly like a normal final answer. Unknown-tool errors receive
    one direct-answer retry; unrelated exceptions are re-raised unchanged.
    """
    from langchain_core.messages import AIMessage, HumanMessage

    try:
        return llm_with_tools.invoke(messages)
    except Exception as exc:
        recovered = _recover_json_tool_error(exc)
        if recovered is not None:
            return AIMessage(content=json.dumps(recovered))

        # Groq validates a generated tool name before returning an AIMessage.
        # A malformed name therefore cannot reach the exact-name executor guard.
        error_text = str(exc).lower()
        if fallback_llm is not None and (
            "not in request.tools" in error_text
            or ("attempted to call tool" in error_text and "tool_use_failed" in error_text)
        ):
            if isinstance(messages, (list, tuple)):
                retry_messages = list(messages)
            else:
                retry_messages = [HumanMessage(content=str(messages))]
            retry_messages.append(
                HumanMessage(content=(
                    "The previous tool request used an invalid tool name and was not executed. "
                    "Answer the original request directly using only the supplied evidence. "
                    "Do not call tools. If evidence is insufficient, say so."
                ))
            )
            logger.warning("tool_call_recovery mode=direct_answer reason=unknown_tool_name")
            return fallback_llm.invoke(retry_messages)
        raise


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
        response = llm.invoke(prompt)
        return _normalize_content(getattr(response, "content", str(response))), [], response

    # Tool names are validated exactly after the provider returns a call. Some
    # Groq responses reject unknown model-generated names before that point.
    try:
        llm_with_tools = llm.bind_tools(tools, tool_choice="auto")
<<<<<<< Updated upstream
        ai_message = _invoke_recovering_json_tool_error(llm_with_tools, prompt)
=======
        ai_message = _invoke_with_rate_limit_retry(
            _invoke_recovering_json_tool_error, llm_with_tools, prompt, llm
        )
>>>>>>> Stashed changes
    except Exception as e:
        if "tool calling" in str(e).lower() or "not supported" in str(e).lower():
            response = llm.invoke(prompt)
            return _normalize_content(getattr(response, "content", str(response))), [], response
        raise e

    tool_calls = getattr(ai_message, "tool_calls", None) or []
    if not tool_calls:
        return _normalize_content(getattr(ai_message, "content", str(ai_message))), [], ai_message

    messages: List[Any] = [HumanMessage(content=prompt), ai_message]
    used_tools: List[str] = []

    # Build a lookup: exact registered name → tool object (for required-arg inspection)
    registered_names = _canonical_tool_names(tools)
    tool_by_name = {getattr(t, "name", None): t for t in tools}

    for call in tool_calls:
        tool_name = call.get("name")
        args = call.get("args", {})
        call_id = call.get("id") or (tool_name or "unknown")

        # ------------------------------------------------------------------
        # Guard 1 — invalid / hallucinated tool name
        # The model (especially Qwen/gpt-oss on Groq) occasionally emits a
        # space-mangled or truncated name such as "Com compliancechecker_tool"
        # that was never in request.tools. Executing or feeding this name back
        # to Groq would cause an HTTP 400 on the follow-up synthesis call.
        # Inject a ToolMessage error instead so the model can self-correct.
        # ------------------------------------------------------------------
        if not _is_valid_tool_name(tool_name, registered_names):
            logger.warning(
                "tool_call_invalid_name agent=%s name=%r registered=%s",
                agent_name, tool_name, sorted(registered_names),
            )
            invalid_msg = (
                f"Tool call rejected: '{tool_name}' is not a valid tool name. "
                f"Valid tools are: {sorted(registered_names)}. "
                "Please answer directly without calling a tool."
            )
            messages.append(ToolMessage(content=invalid_msg, tool_call_id=call_id))
            continue

        # ------------------------------------------------------------------
        # Guard 2 — malformed or missing required arguments. Never guess a
        # tool argument: return a tool error and let synthesis state the limit.
        # ------------------------------------------------------------------
        tool_obj = tool_by_name.get(tool_name)
        args_error = _tool_arguments_error(tool_obj, args)
        if args_error:
            logger.warning(
                "tool_call_invalid_arguments agent=%s tool=%s error=%s",
                agent_name, tool_name, args_error,
            )
            messages.append(ToolMessage(
                content=f"Tool call rejected: {args_error}. No tool was executed.",
                tool_call_id=call_id,
            ))
            continue

        result = execute_tool_call(agent_name, tool_name, args)
        used_tools.append(tool_name)

        tool_content = (
            str(result.get("result"))
            if result.get("status") == "success"
            else f"Tool error: {result.get('message')}"
        )
<<<<<<< Updated upstream
        messages.append(ToolMessage(content=tool_content, tool_call_id=call.get("id") or tool_name))
=======
        logger.info(f"[{agent_name}] Tool '{tool_name}' returned status={result.get('status')}")
        messages.append(ToolMessage(content=tool_content, tool_call_id=call_id))
>>>>>>> Stashed changes

    # Invoke base llm (without tools bound) so the model is forced to synthesize
    # the final structured JSON response rather than attempting another tool call.
    final_message = llm.invoke(messages)
    return _normalize_content(getattr(final_message, "content", str(final_message))), used_tools, final_message
<<<<<<< Updated upstream
=======


def execute_department_agent(
    state: State,
    department: str,
    agent_title: str,
    output_key: str,
    role_points: List[str],
    rules: List[str],
) -> Dict[str, Any]:
    """Generic runner for department specialist agents (finance, legal, operations, rd).

    Handles active department routing gating, case retrieval, tool binding,
    LLM invocation, structured output parsing, and evidence attachment.

    A failure inside any single department is caught here and returned as an
    explicit "unavailable" marker so the LangGraph aggregator can still
    collect outputs from the other departments.
    """
    dept_code = department.lower()
    active_depts = state.get("active_departments")
    if active_depts is not None and dept_code not in active_depts:
        return {output_key: None}

    logger.info("agent_started agent=%s", dept_code)
    messages = state.get("messages", []) or []

    try:
        messages, query = extract_messages_and_query(state)
        if not messages:
            return empty_agent_result(output_key, messages)

        logger.info("retrieval_started agent=%s", dept_code)
        cases, case_text, warnings = retrieve_case_context(query=query, domain=dept_code, k=5)
        logger.info("retrieval_finished agent=%s cases=%d warnings=%s", dept_code, len(cases), warnings)

        agent_name = f"{dept_code}_agent"
        from app.tools.tool_registry import get_tool_objects_for_agent
        tools = get_tool_objects_for_agent(agent_name)

        prompt = build_json_prompt(
            agent_title=agent_title,
            role_points=role_points,
            rules=rules,
            query=query,
            case_text=case_text,
            tool_names=[t.name for t in tools],
        )

        logger.info("llm_started agent=%s", dept_code)
        content, tools_used, final_message = run_llm_with_tools(
            get_llm(state.get("model")), prompt, tools, agent_name=agent_name
        )
        logger.info("llm_finished agent=%s tools_used=%s", dept_code, tools_used)

        parsed_output = parse_structured_output(content, preserve_legal_confidence=(dept_code == "legal"))
        parsed_output.update(
            build_case_evidence(
                cases,
                tools_used,
                reported_confidence=parsed_output.get("confidence"),
                query=query,
                department=dept_code,
            )
        )
        if dept_code == "legal":
            parsed_output.setdefault("historical_case_evidence", parsed_output.get("retrieved_cases", []))
            parsed_output.setdefault("legal_evidence", [])
            parsed_output.setdefault("judicial_evidence", [])
        if warnings:
            parsed_output["warnings"] = warnings
        logger.info("agent_finished agent=%s", dept_code)

        return {
            output_key: parsed_output,
            "messages": messages + [final_message],
        }

    except Exception as exc:
        err_str = str(exc)
        # All other failures: isolate this department and let the rest finish.
        logger.error(
            "agent_failed agent=%s — marking department unavailable, other departments unaffected: %s",
            dept_code, exc, exc_info=True,
        )
        return {
            output_key: {
                "status": "unavailable",
                "response": f"{agent_title} agent encountered an error and is unavailable for this query.",
                "reasoning": f"Agent failure isolated: {type(exc).__name__}: {err_str[:200]}",
                "confidence": 0.0,
                "warnings": [f"agent_failed:{type(exc).__name__}"],
                "num_cases_retrieved": 0,
                "tools_used": [],
            },
            "messages": messages,
        }
>>>>>>> Stashed changes
