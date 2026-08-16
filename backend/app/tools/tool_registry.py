"""Per-agent tool allowlist. This is the source of truth both for what an
agent's LLM is allowed to call (get_tool_objects_for_agent, used with
llm.bind_tools()) and for what app.tools.tool_executor.execute_tool_call()
will permit."""
from typing import List

from app.tools.tool_executor import TOOLS_BY_NAME

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
    """Return the actual LangChain tool objects the specified agent is
    allowed to use, ready to pass to llm.bind_tools(...)."""
    return [TOOLS_BY_NAME[name] for name in get_tools_for_agent(agent_name) if name in TOOLS_BY_NAME]
