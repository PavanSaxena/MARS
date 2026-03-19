from fastapi import FastAPI
from app.api.routes import router

app = FastAPI()

prompt = f"""
You are a strategic decision system.

Inputs:
Finance: {finance}
R&D: {rd}
Legal: {legal}
Operations: {ops}

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

graph = builder.compile()

app.include_router(router)