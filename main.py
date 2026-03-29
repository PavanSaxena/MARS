from fastapi import FastAPI
from app.api.routes import router
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.agents.master_agent import master_router, State
from app.agents.finance_agent import finance_agent
from app.agents.rd_agent import rd_agent
from app.agents.legal_agent import legal_agent
from app.agents.operations_agent import operations_agent
from app.reasoning.aggregator import aggregator_agent

app = FastAPI()
memory = MemorySaver()

prompt = f"""
    You are a strategic decision system.

    Inputs:
        Finance: {finance_agent}
        R&D: {rd_agent}
        Legal: {legal_agent}
        Operations: {operations_agent}

    Steps:
        1. Identify agreements
        2. Identify conflicts
        3. Resolve conflicts logically
        4. Produce final plan

    Output format:
        - Key Insights
        - Conflicts
        - Final Strategy
"""

builder = StateGraph(State)

# Nodes
builder.add_node("master", master_router)
builder.add_node("finance", finance_agent)
builder.add_node("rd", rd_agent)
builder.add_node("legal", legal_agent)
builder.add_node("operations", operations_agent)
builder.add_node("aggregator", aggregator_agent)

# Flow
builder.add_edge(START, "master")

# Parallel fan-out
builder.add_edge("master", "finance")
builder.add_edge("master", "rd")
builder.add_edge("master", "legal")
builder.add_edge("master", "operations")

# Fan-in (all must complete)
builder.add_edge("finance", "aggregator")
builder.add_edge("rd", "aggregator")
builder.add_edge("legal", "aggregator")
builder.add_edge("operations", "aggregator")

builder.add_edge("aggregator", END)

graph = builder.compile(checkpointer=memory)

png_bytes = graph.get_graph().draw_mermaid_png()
with open("/Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/public/graph.png", "wb") as f:
    f.write(png_bytes)

app.include_router(router)

print("System initialized. Ready to process queries.")
print("Graph visualization saved to public/graph.png")
print("Enter query: ")
input_query = input()
initial_state = {"messages": [{"role": "user", "content": input_query}]}
final_state = graph.invoke(initial_state)
print("Final Output:")
print(final_state.get("final_output", "No output generated."))
