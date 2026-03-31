def get_tools_for_agent(agent_name: str) -> list:
    """Return a list of tool names that the specified agent can use."""
    registry = {
        "finance_agent": ["FinancialDataTool", "MarketAnalysisTool"],
        "rd_agent": ["ResearchDatabaseTool", "ExperimentTrackerTool"],
        "legal_agent": ["LegalDatabaseTool", "ComplianceCheckerTool"],
        "operations_agent": ["OperationsDashboardTool", "SupplyChainAnalyzerTool"],
    }
    return registry.get(agent_name, [])