"""
Tool execution bridge for the department agents.

Tool *definitions and implementations* both live on the mars-tools MCP
server now (app.mcp.server) — this module no longer contains any tool
logic itself. It enforces the same per-agent allowlist that
app.tools.tool_registry used to advertise to the LLM, then forwards the
call over the live MCP session (app.mcp.client.call_tool_sync), exactly
the path any other MCP client would take.
"""
from typing import Any, Dict

from app.mcp.client import call_tool_sync


def execute_tool_call(agent_name: str, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the specified tool with given parameters and return the result.

    Enforces the same per-agent allowlist as app.tools.tool_registry, even
    though in normal operation the LLM only ever sees the tools it was bound
    to via get_tool_objects_for_agent(). The call itself is a real MCP
    tool-call round trip to the mars-tools server subprocess, not a direct
    Python function call.
    """
    from app.tools.tool_registry import get_tools_for_agent

    allowed = get_tools_for_agent(agent_name)
    if tool_name not in allowed:
        return {
            "status": "error",
            "message": f"Tool '{tool_name}' is not registered for agent '{agent_name}'.",
        }

    try:
        result = call_tool_sync(tool_name, parameters)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
