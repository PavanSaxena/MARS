"""
Real tool implementations for the department agents.

Two kinds of tools:
  - "Internal" tools (FinancialDataTool, ResearchDatabaseTool, ExperimentTrackerTool,
    ComplianceCheckerTool, OperationsDashboardTool) pull aggregate stats straight
    from the `decision_cases` table in Supabase — separate from the pgvector
    similarity search in app/storage/retriever.py, this is a plain filtered
    query (risk-level breakdown, most recent cases) for a department.
  - "External" tools (MarketAnalysisTool, LegalDatabaseTool, SupplyChainAnalyzerTool)
    run a live Tavily web search for information that isn't in the case
    database at all (current market/regulatory/supply-chain context).

Each tool is a LangChain @tool so agents can bind them directly via
llm.bind_tools(...) — see app.agents.common.run_llm_with_tools.
"""
import logging
from typing import Any, Dict, List

from langchain_core.tools import tool

from app.core.config import settings
from app.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

def _department_case_snapshot(department: str, limit: int = 20) -> Dict[str, Any]:
    """Fetch recent decision_cases rows for a department and summarize them."""
    logger.info("department_snapshot_started department=%s limit=%d", department, limit)
    supabase = get_supabase_client()
    table = settings.SUPABASE_CASES_TABLE

    rows = (
        supabase.table(table)
        .select("decision_title, risk_level, outcome_summary, quarter")
        .eq("department", department)
        .order("quarter", desc=True)
        .limit(limit)
        .execute()
        .data
    )

    risk_counts: Dict[str, int] = {}
    for row in rows:
        risk = row.get("risk_level") or "Unknown"
        risk_counts[risk] = risk_counts.get(risk, 0) + 1

    snapshot = {
        "department": department,
        "case_count": len(rows),
        "risk_level_breakdown": risk_counts,
        "recent_cases": [
            {
                "title": row.get("decision_title"),
                "quarter": row.get("quarter"),
                "outcome": row.get("outcome_summary"),
            }
            for row in rows[:5]
        ],
    }
    logger.info("department_snapshot_finished department=%s cases=%d", department, len(rows))
    return snapshot


def _format_snapshot(snapshot: Dict[str, Any], label: str) -> str:
    if snapshot["case_count"] == 0:
        return f"No {label.lower()} found in decision_cases for department={snapshot['department']}."

    lines = [
        f"{label} for {snapshot['department']} ({snapshot['case_count']} historical cases):",
        f"Risk level breakdown: {snapshot['risk_level_breakdown']}",
        "Most recent cases:",
    ]
    for c in snapshot["recent_cases"]:
        lines.append(f"  - [{c['quarter']}] {c['title']}: {c['outcome']}")
    return "\n".join(lines)


def _web_search(query: str, label: str) -> str:
    """Run a live web search via Tavily. Degrades gracefully if no API key is set."""
    if not settings.TAVILY_API_KEY:
        logger.warning("web_search_skipped label=%s reason=missing_api_key", label)
        return (
            f"{label} unavailable: TAVILY_API_KEY is not configured, so no live web "
            f"search could be run for '{query}'."
        )

    try:
        logger.info("web_search_started label=%s", label)
        from langchain_tavily import TavilySearch

        search = TavilySearch(max_results=4, tavily_api_key=settings.TAVILY_API_KEY)
        results = search.invoke({"query": query})
        items = results.get("results", []) if isinstance(results, dict) else results
        if not items:
            logger.info("web_search_finished label=%s results=0", label)
            return f"{label}: no relevant web results found for '{query}'."

        lines = [f"{label} (live web search results for '{query}'):"]
        for item in items[:4]:
            title = item.get("title", "Untitled")
            content = (item.get("content") or "").strip().replace("\n", " ")[:280]
            url = item.get("url", "")
            lines.append(f"  - {title}: {content}... ({url})")
        logger.info("web_search_finished label=%s results=%d", label, len(items))
        return "\n".join(lines)
    except Exception as exc:  # network/API errors shouldn't crash the agent
        logger.exception("web_search_failed label=%s", label)
        return f"{label} failed: {exc}"


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------

@tool("FinancialDataTool")
def financial_data_tool(query: str) -> str:
    """Look up historical Finance-department decision cases (risk levels, past
    outcomes) relevant to the query, pulled directly from the case database."""
    snapshot = _department_case_snapshot("Finance")
    return _format_snapshot(snapshot, "Internal financial case data")


@tool("MarketAnalysisTool")
def market_analysis_tool(query: str) -> str:
    """Run a live web search for current market trends, competitor activity, or
    industry data relevant to the query."""
    return _web_search(query, "Market analysis")


# ---------------------------------------------------------------------------
# R&D
# ---------------------------------------------------------------------------

@tool("ResearchDatabaseTool")
def research_database_tool(query: str) -> str:
    """Look up historical R&D-department decision cases (technical readiness,
    prior research outcomes) relevant to the query."""
    snapshot = _department_case_snapshot("R&D")
    return _format_snapshot(snapshot, "Internal R&D case data")


@tool("ExperimentTrackerTool")
def experiment_tracker_tool(query: str) -> str:
    """Look up recorded experiment/pilot outcomes for past R&D initiatives
    relevant to the query."""
    snapshot = _department_case_snapshot("R&D")
    if snapshot["case_count"] == 0:
        return "No recorded experiment outcomes found for R&D."
    lines = ["Recorded experiment outcomes:"]
    for c in snapshot["recent_cases"]:
        lines.append(f"  - [{c['quarter']}] {c['title']}: {c['outcome']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Legal
# ---------------------------------------------------------------------------

@tool("LegalDatabaseTool")
def legal_database_tool(query: str) -> str:
    """Run a live web search for relevant laws, regulations, or legal
    precedent related to the query."""
    return _web_search(query, "Legal/regulatory research")


@tool("ComplianceCheckerTool")
def compliance_checker_tool(query: str) -> str:
    """Look up historical Legal-department decision cases and flag past
    compliance/regulatory risk levels relevant to the query."""
    snapshot = _department_case_snapshot("Legal")
    return _format_snapshot(snapshot, "Internal compliance case history")


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

@tool("OperationsDashboardTool")
def operations_dashboard_tool(query: str) -> str:
    """Look up historical Operations-department decision cases (execution
    risk, delivery outcomes) relevant to the query."""
    snapshot = _department_case_snapshot("Operations")
    return _format_snapshot(snapshot, "Internal operations case data")


@tool("SupplyChainAnalyzerTool")
def supply_chain_analyzer_tool(query: str) -> str:
    """Run a live web search for current supply chain risks, disruptions, or
    logistics data relevant to the query."""
    return _web_search(query, "Supply chain analysis")


TOOLS_BY_NAME = {
    "FinancialDataTool": financial_data_tool,
    "MarketAnalysisTool": market_analysis_tool,
    "ResearchDatabaseTool": research_database_tool,
    "ExperimentTrackerTool": experiment_tracker_tool,
    "LegalDatabaseTool": legal_database_tool,
    "ComplianceCheckerTool": compliance_checker_tool,
    "OperationsDashboardTool": operations_dashboard_tool,
    "SupplyChainAnalyzerTool": supply_chain_analyzer_tool,
}


def execute_tool_call(agent_name: str, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the specified tool with given parameters and return the result.

    Enforces the same per-agent allowlist as app.tools.tool_registry, even
    though in normal operation the LLM only ever sees the tools it was bound
    to via get_tool_objects_for_agent().
    """
    from app.tools.tool_registry import get_tools_for_agent

    allowed = get_tools_for_agent(agent_name)
    if tool_name not in allowed:
        logger.warning("tool_call_rejected agent=%s tool=%s reason=not_allowed", agent_name, tool_name)
        return {
            "status": "error",
            "message": f"Tool '{tool_name}' is not registered for agent '{agent_name}'.",
        }

    tool_fn = TOOLS_BY_NAME.get(tool_name)
    if not tool_fn:
        logger.warning("tool_call_rejected agent=%s tool=%s reason=not_found", agent_name, tool_name)
        return {"status": "error", "message": f"Tool '{tool_name}' not found."}

    try:
        logger.info("tool_execution_started agent=%s tool=%s", agent_name, tool_name)
        result = tool_fn.invoke(parameters)
        logger.info("tool_execution_finished agent=%s tool=%s status=success", agent_name, tool_name)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.exception("tool_execution_failed agent=%s tool=%s", agent_name, tool_name)
        return {"status": "error", "message": str(e)}
