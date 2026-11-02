import time
from pathlib import Path
from typing import Any, Dict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.chat_agent import chat_agent
from app.agents.finance_agent import finance_agent
from app.agents.legal_agent import legal_agent
from app.agents.operations_agent import operations_agent
from app.agents.rd_agent import rd_agent
from app.agents.router import classify_intent
from app.reasoning.aggregator import aggregator_agent
from app.state import State
from app.core.logging_config import get_logger

logger = get_logger("agents.master")
memory = MemorySaver()


def master_router(state: State) -> Dict[str, Any]:
    """Fan-out node that forwards the incoming message stream to department agents."""
    logger.info("[Master] Fanning out request to department agents: Finance, R&D, Legal, Operations")
    return {"messages": state.get("messages", [])}


def _pick_route(state: State) -> str:
    """Read the route classify_intent decided on ("pipeline" or "chat")."""
    return state.get("route") or "pipeline"


def _fallback_agent_response(state: State) -> str:
    """Return department findings if the aggregator produced an empty answer.

    This keeps useful specialist work visible to API clients when a model
    returns an empty synthesis (for example, after a rate-limit retry).
    """
    sections = []
    for label, key in (
        ("Finance", "finance_output"),
        ("Legal", "legal_output"),
        ("Operations", "operations_output"),
        ("R&D", "rd_output"),
    ):
        output = state.get(key) or {}
        response = str(output.get("response") or "").strip()
        if response:
            sections.append(f"{label} assessment: {response}")
        for evidence_key, evidence_label in (("legal_evidence", "Legal sources"),
                                             ("judicial_evidence", "Judicial sources")):
            evidence_rows = output.get(evidence_key) or []
            for item in evidence_rows:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("id") or "Untitled source"
                source_url = item.get("source_url") or ""
                authority = item.get("authority") or "authority unknown"
                suffix = f" — {source_url}" if source_url else ""
                sections.append(f"{evidence_label}: {title} ({authority}){suffix}")

    if not sections:
        sections.append("No department assessment or source evidence was returned.")
    decision = "\n\n".join(sections)
    return (
        "Key Insights:\n"
        "- The synthesis model returned an empty response; the available department findings are shown below.\n\n"
        "Final Decision:\n"
        f"{decision}\n\n"
        "This is an unsynthesized fallback. Review the department findings and cited sources directly."
    )


def _verified_dpdp_response(state: State) -> str | None:
    """Render a bounded India DPDP response only when official Act text exists."""
    legal = state.get("legal_output") or {}
    source = next((item for item in legal.get("legal_evidence", [])
                   if isinstance(item, dict)
                   and item.get("authority") == "authoritative"
                   and "digital personal data protection act" in str(item.get("title", "")).lower()
                   and item.get("full_text")), None)
    if not source:
        return None

    title = source.get("title") or "The Digital Personal Data Protection Act, 2023"
    url = source.get("source_url") or "India Code source URL unavailable"
    return f"""## India customer-data analytics: legal verification checklist

The Legal Agent retrieved the authoritative text of **{title}** from India Code. The text is marked as consolidated through **19 November 2025**. Use the official source below to confirm amendments, commencement notifications, and applicable Rules before launch.

- **Scope (section 3):** Confirm the data is digital personal data and check whether processing in India—or processing outside India connected to offering goods or services to people in India—falls within the Act.
- **Processing basis, notice, and consent (sections 4–7):** Document the lawful purpose and applicable basis. Where consent is used, check the notice and consent requirements, withdrawal process, and whether a specific legitimate-use ground applies instead.
- **Data-fiduciary controls (section 8):** Check security safeguards, processor contracts, breach notification, accuracy where data informs decisions or is disclosed, retention/deletion, and a grievance process.
- **Additional conditions (sections 9–10):** Apply the child-data requirements where relevant. The additional Significant Data Fiduciary duties apply only if the Central Government designates the organization in that category; verify the designation before treating those duties as applicable.
- **People’s rights (sections 11–14):** Provide the applicable access, correction/erasure, grievance, and nomination processes.
- **Cross-border processing and penalties (sections 16 and 33):** Check current government restrictions on transfers. Review the Schedule for the penalty that corresponds to any identified breach.

**Verification limits:** This lookup retrieved the Act text, but did not retrieve current commencement notifications or the Digital Personal Data Protection Rules. It also did not retrieve court judgments. Historical MARS cases are organizational precedents and do not establish these legal requirements.

**Authoritative source:** [{title}]({url})"""


def build_graph():
    """
    Build and compile the multi-agent decision graph.

    Every turn first passes through `router`, which decides whether the
    message needs the full Legal/Finance/Operations/R&D analysis ("pipeline")
    or is ordinary conversation / a follow-up on a decision already made
    ("chat"). Without this, every message — including "hi", "test", or "go
    into more detail" — re-ran all four department agents from scratch each
    time, since each agent only ever looked at the latest message. Now only
    genuinely new decisions re-run the full pipeline; everything else gets a
    normal conversational reply that has access to the full thread history.
    """
    builder = StateGraph(State)

    builder.add_node("router", classify_intent)
    builder.add_node("master", master_router)
    builder.add_node("finance", finance_agent)
    builder.add_node("rd", rd_agent)
    builder.add_node("legal", legal_agent)
    builder.add_node("operations", operations_agent)
    builder.add_node("aggregator", aggregator_agent)
    builder.add_node("chat", chat_agent)

    builder.add_edge(START, "router")

    builder.add_conditional_edges(
        "router",
        _pick_route,
        {"pipeline": "master", "chat": "chat"},
    )

    builder.add_edge("master", "finance")
    builder.add_edge("master", "rd")
    builder.add_edge("master", "legal")
    builder.add_edge("master", "operations")

    builder.add_edge("finance", "aggregator")
    builder.add_edge("rd", "aggregator")
    builder.add_edge("legal", "aggregator")
    builder.add_edge("operations", "aggregator")

    builder.add_edge("aggregator", END)
    builder.add_edge("chat", END)

    return builder.compile(checkpointer=memory)


graph = build_graph()


from app.core.errors import is_rate_limit_error, format_rate_limit_error


def run_graph(
    user_input: str,
    thread_id: str = "default",
    model: str | None = None,
    force_pipeline: bool = False,
    raise_on_rate_limit: bool = False,
) -> tuple[str, dict]:
    """
    Execute the graph for one user query and return (final_decision_str, retrieved_cases_dict).

    `model` is optional and, when given, is written into the thread's
    checkpointed state as "<provider>:<model>" (see settings.AVAILABLE_MODELS).
    `force_pipeline`: when True, forces execution through the multi-agent decision pipeline.
    `raise_on_rate_limit`: when True, re-raises RateLimitError instead of returning formatted markdown.
    """
    start_time = time.time()
    preview = user_input.replace("\n", " ")[:60]
    logger.info(f"[Graph] Starting execution (thread='{thread_id}', model='{model or 'default'}', query=\"{preview}\")")

    initial_state: Dict[str, Any] = {"messages": [{"role": "user", "content": user_input}]}
    if model:
        initial_state["model"] = model
    if force_pipeline:
        initial_state["route"] = "pipeline"
        initial_state["active_departments"] = ["finance", "rd", "legal", "operations"]

    config = {"configurable": {"thread_id": thread_id}}
    try:
        final_state = graph.invoke(initial_state, config=config)
        output_text = final_state.get("final_output") or final_state.get("final_decision")
        if not output_text or not str(output_text).strip():
            logger.warning("[Graph] Aggregator returned no content; using department-response fallback")
            output_text = _fallback_agent_response(final_state)
        retrieved_cases = final_state.get("retrieved_cases") or {}
        elapsed = time.time() - start_time
        route = final_state.get("route", "pipeline")
        logger.info(f"[Graph] Execution completed in {elapsed:.2f}s (route='{route}')")
        return output_text, retrieved_cases
    except Exception as exc:
        elapsed = time.time() - start_time
        if is_rate_limit_error(exc):
            logger.warning(f"[Graph] Rate limit encountered after {elapsed:.2f}s: {exc}")
            if raise_on_rate_limit:
                raise exc
            return format_rate_limit_error(exc, model_name=model), {}
        logger.error(f"[Graph] Execution failed after {elapsed:.2f}s: {exc}", exc_info=True)
        raise exc


def get_thread_model(thread_id: str) -> str:
    """Return the model currently active for a thread (falls back to the
    default if the thread hasn't set one yet, e.g. first message)."""
    from app.core.config import settings

    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    model = (snapshot.values or {}).get("model") if snapshot else None
    return model or settings.DEFAULT_MODEL


def save_graph_visualization(output_path: str = "graph.png") -> str:
    """Render the graph diagram to a PNG file and return the absolute path."""
    png_bytes = graph.get_graph().draw_mermaid_png()
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(png_bytes)
    return str(target)
