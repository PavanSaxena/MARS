"""Failure-mode tests for the MCP/tool bridge."""

from __future__ import annotations

import importlib.util
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("mcp") is None,
    reason="MCP runtime package is not installed in this Python environment.",
)


def test_tool_executor_rejects_unregistered_tool():
    from backend.app.tools.tool_executor import execute_tool_call

    result = execute_tool_call("finance_agent", "ComplianceCheckerTool", {"query": "x"})
    assert result["status"] == "error"
    assert "not registered" in result["message"]


def test_tool_executor_wraps_mcp_exception(monkeypatch):
    import backend.app.tools.tool_executor as tool_executor

    def boom(name, arguments):
        raise RuntimeError("synthetic timeout")

    monkeypatch.setattr(tool_executor, "call_tool_sync", boom)
    result = tool_executor.execute_tool_call("finance_agent", "FinancialDataTool", {"query": "x"})
    assert result == {"status": "error", "message": "synthetic timeout"}


def test_run_llm_with_tools_feeds_tool_error_back_to_model(monkeypatch):
    import backend.app.agents.common as common

    class FakeBoundLLM:
        def invoke(self, prompt):
            return SimpleNamespace(
                content="",
                tool_calls=[{"name": "FinancialDataTool", "args": {"query": "x"}, "id": "call_1"}],
            )

    class FakeLLM:
        def bind_tools(self, tools, tool_choice="auto"):
            return FakeBoundLLM()

        def invoke(self, messages):
            assert any("Tool error: synthetic failure" in getattr(m, "content", "") for m in messages)
            return SimpleNamespace(content='{"response":"fallback used","reasoning":"tool failed","confidence":0.1}')

    def fake_execute(agent_name, tool_name, args):
        return {"status": "error", "message": "synthetic failure"}

    monkeypatch.setattr("app.tools.tool_executor.execute_tool_call", fake_execute)
    content, used_tools, _ = common.run_llm_with_tools(
        FakeLLM(),
        "prompt",
        tools=[SimpleNamespace(name="FinancialDataTool")],
        agent_name="finance_agent",
    )
    assert used_tools == ["FinancialDataTool"]
    assert "fallback used" in content
