"""
Regression tests for tool-call failure recovery in app.agents.common.

Covers:
  - Invalid / hallucinated tool names (e.g. "Com compliancechecker_tool")
  - Missing required tool arguments (e.g. FinancialDataTool called without `query`)
  - Valid ComplianceCheckerTool call end-to-end (allowlist + execution path)
  - Rate-limit retry with exponential backoff + jitter
  - Department failure isolation (one crashed agent must not crash the graph)
"""
from __future__ import annotations

import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend root is importable
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ---------------------------------------------------------------------------
# Helpers — minimal fakes that match the interface used by run_llm_with_tools
# ---------------------------------------------------------------------------

def _make_ai_message(tool_calls: List[Dict[str, Any]]):
    """Fake AIMessage with tool_calls attribute."""
    return SimpleNamespace(content="", tool_calls=tool_calls)


def _make_final_message(content: str):
    return SimpleNamespace(content=content, tool_calls=[])


class _BoundLLM:
    """Fake bound-LLM that returns a canned AIMessage on first invoke."""

    def __init__(self, ai_msg):
        self._ai_msg = ai_msg

    def invoke(self, _prompt):
        return self._ai_msg


class _LLM:
    """Fake base LLM used for the synthesis follow-up call."""

    def __init__(self, final_content: str, bound_msg=None):
        self._final = final_content
        self._bound_msg = bound_msg
        self.invocations = []

    def bind_tools(self, tools, tool_choice="auto"):
        if self._bound_msg is None:
            return _BoundLLM(_make_ai_message([]))
        return _BoundLLM(self._bound_msg)

    def invoke(self, _messages):
        self.invocations.append(_messages)
        return _make_final_message(self._final)


@contextmanager
def _patched_tool_executor(execute_tool_call):
    """Stub the MCP-backed executor so these unit tests need no MCP install."""
    module = ModuleType("app.tools.tool_executor")
    module.execute_tool_call = execute_tool_call
    module.AGENT_TOOL_REGISTRY = {}
    module.get_tool_objects_for_agent = lambda _agent: []
    module.get_tools_for_agent = lambda _agent: []
    with patch.dict(sys.modules, {"app.tools.tool_executor": module}):
        yield


# ---------------------------------------------------------------------------
# Test 1 — invalid tool name is rejected; model receives an informative error
# ---------------------------------------------------------------------------

def test_invalid_tool_name_is_rejected_not_executed():
    """
    When the LLM emits a hallucinated tool name that was not in request.tools
    (e.g. "Com compliancechecker_tool"), run_llm_with_tools must:
      - NOT call execute_tool_call with the bad name
      - inject a ToolMessage error explaining the valid tool names
      - continue to the synthesis call and return the model's final answer
    """
    import app.agents.common as common

    bad_call = {"name": "Com compliancechecker_tool", "args": {"query": "test"}, "id": "call_bad"}
    bound_msg = _make_ai_message([bad_call])

    execute_calls: List[str] = []

    def fake_execute(agent, tool, args):
        execute_calls.append(tool)
        return {"status": "success", "result": "data"}

    with _patched_tool_executor(fake_execute):
        llm = _LLM(
            final_content='{"response":"recovered","reasoning":"invalid tool","confidence":0.5}',
            bound_msg=bound_msg,
        )
        content, used_tools, _ = common.run_llm_with_tools(
            llm,
            "test prompt",
            tools=[SimpleNamespace(name="ComplianceCheckerTool", args_schema=None)],
            agent_name="legal_agent",
        )

    # The bad tool must never have been executed
    assert "Com compliancechecker_tool" not in execute_calls, (
        "Hallucinated tool name was forwarded to execute_tool_call — it must not be"
    )
    assert used_tools == [], "used_tools must be empty when all tool names were invalid"
    assert "recovered" in content


# ---------------------------------------------------------------------------
# Test 2 — missing required args are filled with query fallback
# ---------------------------------------------------------------------------

def test_missing_required_args_are_rejected_without_execution():
    """
    When the model emits a tool call without required arguments,
    run_llm_with_tools must not invent an argument or execute the tool.
    """
    import app.agents.common as common

    # FinancialDataTool call with no args at all
    missing_args_call = {"name": "FinancialDataTool", "args": {}, "id": "call_missing"}
    bound_msg = _make_ai_message([missing_args_call])

    captured_args: List[Dict] = []

    def fake_execute(agent, tool, args):
        captured_args.append(args)
        return {"status": "success", "result": "finance data"}

    # Build a minimal args_schema that reports `query` as required
    class FakeSchema:
        @staticmethod
        def schema():
            return {"properties": {"query": {"type": "string"}}, "required": ["query"]}

    tool_stub = SimpleNamespace(name="FinancialDataTool", args_schema=FakeSchema)

    with _patched_tool_executor(fake_execute):
        llm = _LLM(
            final_content='{"response":"ok","reasoning":"args filled","confidence":0.7}',
            bound_msg=bound_msg,
        )
        content, used_tools, _ = common.run_llm_with_tools(
            llm,
            "test prompt for fallback",
            tools=[tool_stub],
            agent_name="finance_agent",
        )

    assert captured_args == [], "Malformed calls must never execute"
    assert used_tools == []
    assert "ok" in content


# ---------------------------------------------------------------------------
# Test 3 — valid ComplianceCheckerTool call is allowed and executed
# ---------------------------------------------------------------------------

def test_valid_compliance_checker_tool_call_is_executed():
    """
    A correctly-named ComplianceCheckerTool call with required args present
    must pass validation, be executed via execute_tool_call, and its result
    fed to the synthesis LLM.
    """
    import app.agents.common as common

    valid_call = {"name": "ComplianceCheckerTool", "args": {"query": "compliance check"}, "id": "call_valid"}
    bound_msg = _make_ai_message([valid_call])

    execute_calls: List[Dict] = []

    def fake_execute(agent, tool, args):
        execute_calls.append({"tool": tool, "args": args})
        return {"status": "success", "result": "compliance data returned"}

    class FakeSchema:
        @staticmethod
        def schema():
            return {"properties": {"query": {"type": "string"}}, "required": ["query"]}

    tool_stub = SimpleNamespace(name="ComplianceCheckerTool", args_schema=FakeSchema)

    with _patched_tool_executor(fake_execute):
        llm = _LLM(
            final_content='{"response":"compliant","reasoning":"tool worked","confidence":0.8}',
            bound_msg=bound_msg,
        )
        content, used_tools, _ = common.run_llm_with_tools(
            llm,
            "compliance query",
            tools=[tool_stub],
            agent_name="legal_agent",
        )

    assert len(execute_calls) == 1
    assert execute_calls[0]["tool"] == "ComplianceCheckerTool"
    assert execute_calls[0]["args"]["query"] == "compliance check"
    assert "ComplianceCheckerTool" in used_tools
    assert "compliant" in content


# ---------------------------------------------------------------------------
# Test 4 — rate-limit retry respects _MAX_RETRIES and uses jitter
# ---------------------------------------------------------------------------

def test_rate_limit_retry_bounded_and_uses_jitter():
    """
    _invoke_with_rate_limit_retry must:
      - retry on 429 errors
      - not exceed _MAX_RETRIES (8)
      - eventually raise RuntimeError when all retries exhausted
      - use different wait times across retries (jitter present)
    """
    import app.agents.common as common

    call_count = 0
    wait_times: List[float] = []

    def always_429():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("HTTP 429 rate limit exceeded")

    def fake_sleep(sec):
        wait_times.append(sec)

    with patch("time.sleep", side_effect=fake_sleep), patch(
        "app.agents.common.random.random", side_effect=[0.0, 0.5, 1.0, 0.5]
    ):
        with pytest.raises(RuntimeError, match="Exceeded maximum attempts"):
            common._invoke_with_rate_limit_retry(always_429)

    assert call_count == 4
    assert len(wait_times) == 3
    assert wait_times == [1.0, 2.0, 5.0]


def test_rate_limit_retry_succeeds_after_transient_429():
    import app.agents.common as common

    call_count = 0

    def succeeds_after_two_limits():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("HTTP 429 rate limit exceeded")
        return "ok"

    with patch("time.sleep") as sleep, patch("app.agents.common.random.random", return_value=0.5):
        result = common._invoke_with_rate_limit_retry(succeeds_after_two_limits)

    assert result == "ok"
    assert call_count == 3
    assert sleep.call_count == 2


def test_llm_semaphore_bounds_concurrent_calls():
    import app.agents.common as common

    active = 0
    peak = 0
    lock = threading.Lock()

    def tracked_call():
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.02)
        with lock:
            active -= 1
        return "ok"

    with patch.object(common, "_LLM_SEMAPHORE", threading.Semaphore(1)):
        workers = [threading.Thread(
            target=common._invoke_with_rate_limit_retry, args=(tracked_call,)
        ) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

    assert peak == 1


def test_groq_rejected_unknown_name_retries_without_tools():
    """Groq can reject an unknown model-generated name before a tool message exists."""
    import app.agents.common as common

    class RejectingBoundLLM:
        def invoke(self, _messages):
            raise RuntimeError(
                "tool_use_failed: attempted to call tool 'Com compliancechecker_tool' "
                "which was not in request.tools"
            )

    class RejectingLLM(_LLM):
        def bind_tools(self, tools, tool_choice="auto"):
            return RejectingBoundLLM()

    llm = RejectingLLM(
        final_content='{"response":"recovered directly","reasoning":"no tool ran","confidence":0.4}'
    )
    execute = MagicMock()
    with _patched_tool_executor(execute):
        content, used_tools, _ = common.run_llm_with_tools(
            llm,
            "legal query",
            tools=[SimpleNamespace(name="ComplianceCheckerTool", args_schema=None)],
            agent_name="legal_agent",
        )

    execute.assert_not_called()
    assert used_tools == []
    assert "recovered directly" in content
    assert len(llm.invocations) == 1


def test_rate_limit_retry_reraises_daily_limit_immediately():
    """Daily TPD limit must be re-raised without any retry."""
    import app.agents.common as common

    call_count = 0

    def daily_limit():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("tokens per day limit reached (TPD)")

    with patch("time.sleep"):
        with pytest.raises(RuntimeError, match="tokens per day"):
            common._invoke_with_rate_limit_retry(daily_limit)

    assert call_count == 1, "Must re-raise immediately on TPD — no retries"


# ---------------------------------------------------------------------------
# Test 5 — department failure isolation
# ---------------------------------------------------------------------------

def test_department_agent_failure_does_not_propagate():
    """
    When execute_department_agent raises an unexpected exception (e.g. from
    a bad LLM call), it must return an "unavailable" dict rather than
    propagating the exception to LangGraph.
    """
    import app.agents.common as common

    fake_state = {
        "messages": [SimpleNamespace(content="should this merger proceed?")],
        "active_departments": ["legal"],
        "model": None,
    }

    def boom_retrieval(*args, **kwargs):
        raise ConnectionError("Supabase unreachable")

    with patch.object(common, "retrieve_case_context", side_effect=boom_retrieval):
        result = common.execute_department_agent(
            state=fake_state,
            department="legal",
            agent_title="Legal Department",
            output_key="legal_output",
            role_points=["Analyze legal risks"],
            rules=["Be accurate"],
        )

    assert "legal_output" in result
    out = result["legal_output"]
    assert out is not None, "Must not return None — must return explicit failure marker"
    assert out["status"] == "unavailable"
    assert out["confidence"] == 0.0
    assert any("agent_failed" in w for w in out.get("warnings", []))
    # Exception must NOT propagate
    assert "messages" in result


def test_daily_rate_limit_is_isolated_as_department_unavailable():
    """
    A failed department must be represented as unavailable so parallel
    departments and the aggregator can still complete.
    """
    import app.agents.common as common

    fake_state = {
        "messages": [SimpleNamespace(content="test query")],
        "active_departments": ["finance"],
        "model": None,
    }

    def tpd_error(*args, **kwargs):
        raise RuntimeError("tokens per day limit reached (TPD)")

    with patch.object(common, "retrieve_case_context", side_effect=tpd_error):
        result = common.execute_department_agent(
            state=fake_state,
            department="finance",
            agent_title="Finance Department",
            output_key="finance_output",
            role_points=["Analyze finances"],
            rules=["Be accurate"],
        )

    assert result["finance_output"]["confidence"] == 0.0
    assert result["finance_output"]["warnings"] == ["agent_failed:RuntimeError"]


# ---------------------------------------------------------------------------
# Test 6 — _canonical_tool_names and _is_valid_tool_name helpers
# ---------------------------------------------------------------------------

def test_canonical_tool_names_returns_exact_registered_set():
    import app.agents.common as common

    tools = [
        SimpleNamespace(name="ComplianceCheckerTool"),
        SimpleNamespace(name="search_laws"),
        SimpleNamespace(name=None),  # edge case — nameless tool
    ]
    names = common._canonical_tool_names(tools)
    assert names == {"ComplianceCheckerTool", "search_laws"}


@pytest.mark.parametrize("name,registered,expected", [
    ("ComplianceCheckerTool", {"ComplianceCheckerTool"}, True),
    ("Com compliancechecker_tool", {"ComplianceCheckerTool"}, False),
    ("compliancecheckertool", {"ComplianceCheckerTool"}, False),  # case mismatch
    (None, {"ComplianceCheckerTool"}, False),
    ("", {"ComplianceCheckerTool"}, False),
    ("FinancialDataTool", {"ComplianceCheckerTool"}, False),  # wrong agent's tool
])
def test_is_valid_tool_name(name, registered, expected):
    import app.agents.common as common
    assert common._is_valid_tool_name(name, registered) == expected

