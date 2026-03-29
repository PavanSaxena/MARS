import os
from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict
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

def reasoning_node(state: State):
    return {"messages": state["messages"]}

def final_node(state: State):
    return {"messages": state["messages"]}

def master_router(state: State):
    return state

def master_agent_node(state: State):
    """
    Master agent:
    - interprets user query
    - decides next query
    - routes execution
    """
    response = tools_llm.invoke(state["messages"])
    return {
        "messages": state["messages"] + [response],
        "route": determine_route(response)
    }

memory = MemorySaver()