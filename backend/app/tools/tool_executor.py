"""
Tool execution bridge and agent allowlist for MARS agents.

Tool definitions and implementations live on the mars-tools FastMCP server
(app.mcp.server). This module enforces the per-agent allowlist and executes
calls over the live MCP session (app.mcp.client.call_tool_sync).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.mcp.client import call_tool_sync, get_langchain_tools_sync

logger = logging.getLogger(__name__)

# Source of truth: which tool names each agent is permitted to see and call
AGENT_TOOL_REGISTRY: Dict[str, List[str]] = {
    "finance_agent": ["FinancialDataTool", "MarketAnalysisTool"],
    "rd_agent": ["ResearchDatabaseTool", "ExperimentTrackerTool"],
    "legal_agent": ["LegalDatabaseTool", "ComplianceCheckerTool"],
    "operations_agent": ["OperationsDashboardTool", "SupplyChainAnalyzerTool"],
}


def get_tools_for_agent(agent_name: str) -> List[str]:
    """Return the tool names the specified agent is permitted to use."""
    return AGENT_TOOL_REGISTRY.get(agent_name, [])


def get_tool_objects_for_agent(agent_name: str) -> list:
    """Return LangChain-compatible tool objects from the MCP server for the agent."""
    allowed = set(get_tools_for_agent(agent_name))
    if not allowed:
        return []

    all_tools = get_langchain_tools_sync()
    return [t for t in all_tools if getattr(t, "name", None) in allowed]


def execute_tool_call(agent_name: str, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the specified tool call with parameters over the MCP session."""
    allowed = get_tools_for_agent(agent_name)
    if tool_name not in allowed:
        logger.warning("tool_call_rejected agent=%s tool=%s reason=not_allowed", agent_name, tool_name)
        return {
            "status": "error",
            "message": f"Tool '{tool_name}' is not registered for agent '{agent_name}'.",
        }

    try:
        logger.info("tool_execution_started agent=%s tool=%s", agent_name, tool_name)
        result = call_tool_sync(tool_name, parameters)
        logger.info("tool_execution_finished agent=%s tool=%s status=success", agent_name, tool_name)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.exception("tool_execution_failed agent=%s tool=%s", agent_name, tool_name)
        return {"status": "error", "message": str(e)}


__all__ = [
    "AGENT_TOOL_REGISTRY",
    "execute_tool_call",
    "get_tool_objects_for_agent",
    "get_tools_for_agent",
]
