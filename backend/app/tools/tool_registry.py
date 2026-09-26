"""Per-agent tool allowlist. This is the source of truth both for what an
agent's LLM is allowed to call (get_tool_objects_for_agent, used with
llm.bind_tools()) and for what app.tools.tool_executor.execute_tool_call()
will permit.

Tool *objects* themselves are no longer imported directly from a local
Python module — they're fetched from the mars-tools MCP server
(app.mcp.server) via app.mcp.client, the same way any other MCP client
would discover them. This module's only remaining job is the allowlist:
which tool *names* each agent is permitted to see and call.
"""
from typing import List

from app.mcp.client import get_langchain_tools_sync

_REGISTRY = {
    "finance_agent": ["FinancialDataTool", "MarketAnalysisTool"],
    "rd_agent": ["ResearchDatabaseTool", "ExperimentTrackerTool"],
    "legal_agent": ["LegalDatabaseTool", "ComplianceCheckerTool"],
    "operations_agent": ["OperationsDashboardTool", "SupplyChainAnalyzerTool"],
}


def get_tools_for_agent(agent_name: str) -> List[str]:
    """Return the tool *names* the specified agent is allowed to use."""
    return _REGISTRY.get(agent_name, [])


def get_tool_objects_for_agent(agent_name: str) -> list:
    """Return the LangChain-compatible tool objects (backed by the MCP
    session) the specified agent is allowed to use, ready to pass to
    llm.bind_tools(...). Filters the full tool list the MCP server
    advertises down to this agent's allowlist."""
    allowed = set(get_tools_for_agent(agent_name))
    if not allowed:
        return []

    all_tools = get_langchain_tools_sync()
    return [t for t in all_tools if getattr(t, "name", None) in allowed]
