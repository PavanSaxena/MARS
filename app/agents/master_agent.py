import os
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.state import State
from app.agents.finance_agent import finance_agent
from app.agents.rd_agent import rd_agent
from app.agents.legal_agent import legal_agent
from app.agents.operations_agent import operations_agent
from app.reasoning.aggregator import aggregator_agent


def master_router(state: State) -> dict:
    """
    Master agent: receives the user query and passes it through to all
    department agents in parallel. Acts as the entry/routing node.
    """
    return {"messages": state["messages"]}


def build_graph() -> StateGraph:
    """Build and compile the LangGraph agent graph."""
    builder = StateGraph(State)

    # Register all nodes
    builder.add_node("master", master_router)
    builder.add_node("finance", finance_agent)
    builder.add_node("rd", rd_agent)
    # builder.add_node("legal", legal_agent)
    # builder.add_node("operations", operations_agent)
    builder.add_node("aggregator", aggregator_agent)

    # Entry point
    builder.add_edge(START, "master")

    # Parallel fan-out from master to all department agents
    builder.add_edge("master", "finance")
    builder.add_edge("master", "rd")
    # builder.add_edge("master", "legal")
    # builder.add_edge("master", "operations")

    # Fan-in: all departments feed into aggregator
    builder.add_edge("finance", "aggregator")
    builder.add_edge("rd", "aggregator")
    # builder.add_edge("legal", "aggregator")
    # builder.add_edge("operations", "aggregator")

    # Aggregator is the terminal node
    builder.add_edge("aggregator", END)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


# Singleton graph instance
graph = build_graph()


def run_graph(user_input: str, thread_id: str = "default") -> str:
    """
    Run the compiled graph with a user query.
    Returns the final aggregated output.
    """
    config = {"configurable": {"thread_id": thread_id}}
    events = graph.stream(
        {"messages": [{"role": "user", "content": user_input}]},
        config=config,
        stream_mode="values",
    )

    final_state = None
    for event in events:
        final_state = event

    if final_state and "final_output" in final_state:
        return final_state["final_output"]

    return "No output generated."


if __name__ == "__main__":
    result = run_graph(
        "Should we invest in a new R&D initiative for AI-driven supply chain optimization?"
    )
    print(result)
