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

memory = MemorySaver()


def master_router(state: State) -> Dict[str, Any]:
    """Fan-out node that forwards the incoming message stream to department agents."""
    return {"messages": state.get("messages", [])}


def _pick_route(state: State) -> str:
    """Read the route classify_intent decided on ("pipeline" or "chat")."""
    return state.get("route") or "pipeline"


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


def run_graph(user_input: str, thread_id: str = "default", model: str | None = None) -> str:
    """
    Execute the graph for one user query and return the final decision string.

    `model` is optional and, when given, is written into the thread's
    checkpointed state as "<provider>:<model>" (see settings.AVAILABLE_MODELS).
    It's deliberately only added to the state update when provided: if the
    caller omits it on a later turn, the previously-selected model for this
    thread_id carries over automatically via the LangGraph checkpointer,
    rather than being reset to the default.
    """
    initial_state: Dict[str, Any] = {"messages": [{"role": "user", "content": user_input}]}
    if model:
        initial_state["model"] = model

    config = {"configurable": {"thread_id": thread_id}}
    final_state = graph.invoke(initial_state, config=config)
    return final_state.get("final_output", "No output generated.")


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
