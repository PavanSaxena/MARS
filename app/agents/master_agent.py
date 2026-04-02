from pathlib import Path
from typing import Any, Dict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.finance_agent import finance_agent
from app.agents.legal_agent import legal_agent
from app.agents.operations_agent import operations_agent
from app.agents.rd_agent import rd_agent
from app.reasoning.aggregator import aggregator_agent
from app.state import State

memory = MemorySaver()


def master_router(state: State) -> Dict[str, Any]:
    """Entry node that forwards the incoming message stream to department agents."""
    return {"messages": state.get("messages", [])}


def build_graph():
    """Build and compile the multi-agent decision graph."""
    builder = StateGraph(State)

    builder.add_node("master", master_router)
    builder.add_node("finance", finance_agent)
    # builder.add_node("rd", rd_agent)
    # builder.add_node("legal", legal_agent)
    # builder.add_node("operations", operations_agent)
    builder.add_node("aggregator", aggregator_agent)

    builder.add_edge(START, "master")

    builder.add_edge("master", "finance")
    # builder.add_edge("master", "rd")
    # builder.add_edge("master", "legal")
    # builder.add_edge("master", "operations")

    builder.add_edge("finance", "aggregator")
    # builder.add_edge("rd", "aggregator")
    # builder.add_edge("legal", "aggregator")
    # builder.add_edge("operations", "aggregator")

    builder.add_edge("aggregator", END)

    return builder.compile(checkpointer=memory)


graph = build_graph()


def run_graph(user_input: str, thread_id: str = "default") -> str:
    """Execute the graph for one user query and return the final decision string."""
    initial_state = {"messages": [{"role": "user", "content": user_input}]}
    config = {"configurable": {"thread_id": thread_id}}
    final_state = graph.invoke(initial_state, config=config)
    return final_state.get("final_output", "No output generated.")


def save_graph_visualization(output_path: str = "graph.png") -> str:
    """Render the graph diagram to a PNG file and return the absolute path."""
    png_bytes = graph.get_graph().draw_mermaid_png()
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(png_bytes)
    return str(target)
