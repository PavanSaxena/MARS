"""Failure-mode tests for the MCP/tool bridge."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# Ensure backend root is on sys.path so app imports work
current_dir = Path(__file__).resolve().parent
backend_root = current_dir.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("mcp") is None,
    reason="MCP runtime package is not installed in this Python environment.",
)


def test_tool_executor_rejects_unregistered_tool():
    from app.tools.tool_executor import execute_tool_call

    result = execute_tool_call("finance_agent", "ComplianceCheckerTool", {"query": "x"})
    assert result["status"] == "error"
    assert "not registered" in result["message"]


def test_tool_executor_wraps_mcp_exception(monkeypatch):
    import app.tools.tool_executor as tool_executor

    def boom(name, arguments):
        raise RuntimeError("synthetic timeout")

    monkeypatch.setattr(tool_executor, "call_tool_sync", boom)
    result = tool_executor.execute_tool_call("finance_agent", "FinancialDataTool", {"query": "x"})
    assert result == {"status": "error", "message": "synthetic timeout"}


def test_legal_tool_executor_accepts_jurisdiction_alias(monkeypatch):
    import app.tools.tool_executor as tool_executor

    seen = {}

    def fake_call(name, arguments):
        seen.update(name=name, arguments=arguments)
        return "{}"

    monkeypatch.setattr(tool_executor, "call_tool_sync", fake_call)
    result = tool_executor.execute_tool_call(
        "legal_agent", "search_judgments", {"query": "privacy", "jurisdiction": "India"}
    )
    assert result == {"status": "success", "result": "{}"}
    assert seen["arguments"] == {"query": "privacy", "country": "India"}


def test_run_llm_with_tools_feeds_tool_error_back_to_model(monkeypatch):
    import app.agents.common as common

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
    content, used_tools, _, _ = common.run_llm_with_tools(
        FakeLLM(),
        "prompt",
        tools=[SimpleNamespace(name="FinancialDataTool")],
        agent_name="finance_agent",
    )
    assert used_tools == ["FinancialDataTool"]
    assert "fallback used" in content


def test_legal_search_automatically_fetches_authoritative_act_text(monkeypatch):
    import json
    import app.agents.common as common
    import app.tools.tool_executor as tool_executor

    calls = []

    class FakeBoundLLM:
        def invoke(self, _prompt):
            return SimpleNamespace(content="", tool_calls=[{
                "name": "search_laws", "args": {"query": "DPDP Act", "country": "India"}, "id": "law-search"
            }])

    class FakeLLM:
        def bind_tools(self, tools, tool_choice="auto"):
            return FakeBoundLLM()

        def invoke(self, messages):
            assert any("official Act text" in getattr(message, "content", "") for message in messages)
            return SimpleNamespace(content='{"response":"Act checked","reasoning":"Text retrieved","confidence":0.8}')

    def fake_execute(_agent, tool_name, _args):
        calls.append(tool_name)
        if tool_name == "search_laws":
            return {"status": "success", "result": json.dumps({"results": [{
                "title": "Digital Personal Data Protection Act, 2023", "authority": "authoritative"
            }]})}
        return {"status": "success", "result": '{"full_text":"official Act text"}'}

    monkeypatch.setattr(tool_executor, "execute_tool_call", fake_execute)
    content, used_tools, _, tool_results = common.run_llm_with_tools(
        FakeLLM(), "current Indian data law", [SimpleNamespace(name="search_laws")], "legal_agent"
    )
    assert calls == ["search_laws", "get_law"]
    assert used_tools == ["search_laws", "get_law"]
    assert len(tool_results) == 2
    assert "Act checked" in content
