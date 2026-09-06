"""
MCP server for MARS's department tools.

This is what "the MCP Tool Layer" from the Phase-3 roadmap actually is: the
8 department tools (previously plain Python functions imported straight
into the agent process) are exposed here as a standardized Model Context
Protocol server, so agents access them over the same tool-call protocol any
other MCP client (Claude Desktop, another service, etc.) would use — not
via a direct import.

Two kinds of tools:
  - "Internal" tools (FinancialDataTool, ResearchDatabaseTool,
    ExperimentTrackerTool, ComplianceCheckerTool, OperationsDashboardTool)
    pull an aggregate department snapshot straight from the `decisions` /
    `outcomes` tables in Supabase — separate from the pgvector similarity
    search in app/storage/retriever.py, this is a plain filtered query
    (action-type breakdown, most recent cases + their outcomes) for a
    department.
  - "External" tools (MarketAnalysisTool, LegalDatabaseTool,
    SupplyChainAnalyzerTool) run a live Tavily web search for information
    that isn't in the case database at all.

Run standalone for debugging / manual inspection:
    python -m app.mcp.server

In normal operation this file is never run directly by a human — it's
spawned as a subprocess over stdio by app.mcp.client the first time any
agent needs a tool, and stays alive for the life of the backend process.
"""
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from app.core.config import settings
from app.services.supabase_client import get_supabase_client

mcp = FastMCP("mars-tools")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _department_case_snapshot(department: str, limit: int = 20) -> Dict[str, Any]:
    """Fetch recent `decisions` rows for a department, joined with their
    `outcomes`, and summarize them."""
    supabase = get_supabase_client()
    table = settings.SUPABASE_DECISIONS_TABLE  # "decisions"
    outcomes_table = settings.SUPABASE_OUTCOMES_TABLE  # "outcomes"

    rows = (
        supabase.table(table)
        .select(f"decision_title, action_type, decision_date, {outcomes_table}(outcome_label, observation_excerpt)")
        .eq("department", department)
        .order("decision_date", desc=True)
        .limit(limit)
        .execute()
        .data
    )

    action_counts: Dict[str, int] = {}
    for row in rows:
        action = row.get("action_type") or "Unknown"
        action_counts[action] = action_counts.get(action, 0) + 1

    def _outcome_text(row: Dict[str, Any]) -> str:
        outcome = row.get(outcomes_table)
        # Embedded FK select comes back as a dict (one-to-one) or a list
        # depending on client version/relationship shape — handle both.
        if isinstance(outcome, list):
            outcome = outcome[0] if outcome else None
        if not outcome:
            return "unresolved"
        return outcome.get("observation_excerpt") or outcome.get("outcome_label") or "unresolved"

    return {
        "department": department,
        "case_count": len(rows),
        "action_type_breakdown": action_counts,
        "recent_cases": [
            {
                "title": row.get("decision_title"),
                "quarter": row.get("decision_date"),
                "outcome": _outcome_text(row),
            }
            for row in rows[:5]
        ],
    }


def _format_snapshot(snapshot: Dict[str, Any], label: str) -> str:
    if snapshot["case_count"] == 0:
        return f"No {label.lower()} found in decisions for department={snapshot['department']}."

    lines = [
        f"{label} for {snapshot['department']} ({snapshot['case_count']} historical cases):",
        f"Action type breakdown: {snapshot['action_type_breakdown']}",
        "Most recent cases:",
    ]
    for c in snapshot["recent_cases"]:
        lines.append(f"  - [{c['quarter']}] {c['title']}: {c['outcome']}")
    return "\n".join(lines)


def _web_search(query: str, label: str) -> str:
    """Run a live web search via Tavily. Degrades gracefully if no API key is set."""
    if not settings.TAVILY_API_KEY:
        return (
            f"{label} unavailable: TAVILY_API_KEY is not configured, so no live web "
            f"search could be run for '{query}'."
        )

    try:
        from langchain_tavily import TavilySearch

        search = TavilySearch(max_results=4, tavily_api_key=settings.TAVILY_API_KEY)
        results = search.invoke({"query": query})
        items = results.get("results", []) if isinstance(results, dict) else results
        if not items:
            return f"{label}: no relevant web results found for '{query}'."

        lines = [f"{label} (live web search results for '{query}'):"]
        for item in items[:4]:
            title = item.get("title", "Untitled")
            content = (item.get("content") or "").strip().replace("\n", " ")[:280]
            url = item.get("url", "")
            lines.append(f"  - {title}: {content}... ({url})")
        return "\n".join(lines)
    except Exception as exc:  # network/API errors shouldn't crash the agent
        return f"{label} failed: {exc}"


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------

@mcp.tool(name="FinancialDataTool")
def financial_data_tool(query: str) -> str:
    """Look up historical Finance-department decision cases (risk levels, past
    outcomes) relevant to the query, pulled directly from the case database."""
    snapshot = _department_case_snapshot("Finance")
    return _format_snapshot(snapshot, "Internal financial case data")


@mcp.tool(name="MarketAnalysisTool")
def market_analysis_tool(query: str) -> str:
    """Run a live web search for current market trends, competitor activity, or
    industry data relevant to the query."""
    return _web_search(query, "Market analysis")


# ---------------------------------------------------------------------------
# R&D
# ---------------------------------------------------------------------------

@mcp.tool(name="ResearchDatabaseTool")
def research_database_tool(query: str) -> str:
    """Look up historical R&D-department decision cases (technical readiness,
    prior research outcomes) relevant to the query."""
    snapshot = _department_case_snapshot("R&D")
    return _format_snapshot(snapshot, "Internal R&D case data")


@mcp.tool(name="ExperimentTrackerTool")
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

@mcp.tool(name="LegalDatabaseTool")
def legal_database_tool(query: str) -> str:
    """Run a live web search for relevant laws, regulations, or legal
    precedent related to the query."""
    return _web_search(query, "Legal/regulatory research")


@mcp.tool(name="ComplianceCheckerTool")
def compliance_checker_tool(query: str) -> str:
    """Look up historical Legal-department decision cases and flag past
    compliance/regulatory risk levels relevant to the query."""
    snapshot = _department_case_snapshot("Legal")
    return _format_snapshot(snapshot, "Internal compliance case history")


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

@mcp.tool(name="OperationsDashboardTool")
def operations_dashboard_tool(query: str) -> str:
    """Look up historical Operations-department decision cases (execution
    risk, delivery outcomes) relevant to the query."""
    snapshot = _department_case_snapshot("Operations")
    return _format_snapshot(snapshot, "Internal operations case data")


@mcp.tool(name="SupplyChainAnalyzerTool")
def supply_chain_analyzer_tool(query: str) -> str:
    """Run a live web search for current supply chain risks, disruptions, or
    logistics data relevant to the query."""
    return _web_search(query, "Supply chain analysis")


if __name__ == "__main__":
    mcp.run(transport="stdio")
