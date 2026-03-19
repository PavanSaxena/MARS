from typing import Annotated
import os
from langchain_tavily import TavilySearch
from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict
from IPython.display import Image, display
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(env_path)

llm = init_chat_model("groq:llama-3.3-70b-versatile")

class State(TypedDict):
    messages: Annotated[list, add_messages]
    route: str

search_tool = TavilySearch(max_results=3)
tools = [search_tool]

tools_llm = llm.bind_tools(tools)

def determine_route(response):
    content = response.content.lower()
    if "search" in content:
        return "retrieval_agent"
    elif "analyze" in content:
        return "reasoning_agent"
    else:
        return "final"

def retrieval_node(state: State):
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
graph = builder.compile(checkpointer=memory)
png_bytes = graph.get_graph().draw_mermaid_png()
with open("/Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/public/graph.png", "wb") as f:
    f.write(png_bytes)

user_input = "What are the latest trends in AI research?"
config = {"configurable": {"thread_id": "1"}}
events = graph.stream(
    {"messages": [{"role": "user", "content": user_input}]},
    config=config,
    stream_mode="values"
)
for event in events:
    if "messages" in event:
        event["messages"][-1].pretty_print()