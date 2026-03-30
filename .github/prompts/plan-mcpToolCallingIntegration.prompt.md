## Plan: MCP And Tool-Calling Integration

Introduce LangChain tool-calling and MCP server support in incremental phases that keep current behavior stable, preserve passing tests, and add traceability for audit-ready decisions.

**Steps**
1. Foundation: create a standalone tool layer in app/tools with domain-safe wrappers around existing retrieval and scoring logic. This includes a tool registry plus execution middleware with uniform result envelopes. This is isolated from current agents and can be validated independently.
2. State Extension: add optional tool-trace fields to app/state.py for tool_calls, tool_results, agent_citations, and runtime tool_config so existing flows remain backward compatible. *depends on 1*
3. Agent Runtime Binding: add an agent factory that lazy-binds tools to each agent model at runtime and introduce a feature flag (USE_TOOL_CALLING) to allow fallback to current prompt-only behavior. Refactor finance, rd, operations, and legal agents to use the same tool-call loop pattern. *depends on 1,2*
4. Aggregator Evidence Upgrade: update aggregator prompt construction to consume agent_citations and selected tool results so final decisions reference evidence sources. Keep existing output contract while enriching rationale quality. *depends on 2,3*
5. API Trace Controls: extend /api/query response shape with optional trace metadata and add include_trace input controls so debugging/audit data is opt-in and non-breaking. *depends on 2,3*
6. MCP Server Layer: add app/mcp/server.py and app/mcp/main.py to expose project tools over MCP (stdio first, optional SSE next), reusing the same tool registry and executor to avoid duplicate logic. *depends on 1*
7. MCP Client Path (Optional): add app/mcp/client.py for calling external MCP servers from agents where needed, behind config flags and timeout/retry guards. *parallel with 6*
8. Hardening And Observability: add structured logging for tool lifecycle events, timeout/retry policies, and error categorization; add docs for operations and troubleshooting. *depends on 3,6*
9. Rollout Strategy: ship in dark mode (feature flag off), run shadow traces, enable tool-calling for finance first, then rd/operations/legal after quality gates. *depends on 3,4,5*

**Relevant files**
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/agents/master_agent.py — preserve graph topology; inject config and runtime flags for tool-calling and tracing
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/agents/common.py — keep shared parsing and prompt helpers; extend for tool-loop utilities
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/agents/finance_agent.py — first rollout target for tool-calling path
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/agents/rd_agent.py — adopt same runtime tool binding pattern as finance
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/agents/operations_agent.py — adopt same runtime tool binding pattern as finance
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/agents/legal_agent.py — replace placeholder-only behavior with tool-aware legal workflow
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/reasoning/aggregator.py — include citations/tool evidence in synthesis prompt
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/state.py — optional trace fields for tool execution and citations
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/api/routes.py — add include_trace controls and optional trace payload output
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/services/case_retrieval_service.py — keep retrieval normalization and expose stable utility for tool wrappers
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/storage/retriever.py — source for retrieval tool implementation
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/main.py — no orchestration logic changes; retain bootstrap only
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/tests/test_agents.py — add tool-loop and fallback-path tests
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/tests/test_api.py — add include_trace response tests
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/tests/test_reasoning.py — verify citation-aware final outputs
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/tests/test_services.py — keep retrieval contract stable
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/tests/tests.py — maintain legacy compatibility wrapper
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/tools/tool_definitions.py — new tool definitions around retrieval/scoring/business utilities
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/tools/tool_registry.py — new per-agent tool registration and lookup
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/tools/tool_executor.py — new execution middleware with retry/timeout envelope
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/agents/agent_factory.py — new runtime LLM+tools binder
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/mcp/server.py — new MCP server tool exposure
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/mcp/main.py — new MCP server startup entrypoint
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/app/mcp/client.py — optional external MCP client connector
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/tests/test_tools.py — new tests for tool definitions/execution
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/tests/test_state.py — new tests for backward-compatible state schema
- /Users/pavansaxena/MyData/PES_Files/CapstoneProject/Team-176-Capstone/tests/test_mcp.py — new tests for list_tools/call_tool behavior

**Verification**
1. Baseline gate: run .venv/bin/python -m pytest tests -v before changes and save pass count.
2. Phase gates: after each phase, run targeted test files plus full suite.
3. Backward compatibility: with USE_TOOL_CALLING disabled, verify behavior and outputs match current expectations.
4. Tool runtime validation: with USE_TOOL_CALLING enabled for finance only, verify tool_calls and tool_results appear in final state without breaking API.
5. API contract validation: verify /api/query still returns result string by default; include_trace returns trace metadata only when requested.
6. MCP server validation: start MCP server and validate list_tools and call_tool on at least retrieval and confidence tools.
7. Performance gate: ensure end-to-end query stays within acceptable latency budget after tool integration.
8. Rollout gate: enable tool-calling per agent one-by-one, monitoring trace completeness and error rates.

**Decisions**
- Include in scope: LangChain tool-calling integration and first-party MCP server exposure for internal tools.
- Include in scope: optional API trace payload for observability.
- Exclude from first release: external third-party MCP dependencies in critical path.
- Exclude from first release: changing final API result default format.
- Rollback strategy: feature flag keeps prompt-only path available per agent.

**Further Considerations**
1. Trace retention policy recommendation: return traces only on request and avoid persisting full tool payloads in production logs unless required.
2. Legal agent recommendation: implement policy/constraint tools first so legal reasoning is grounded before full free-form LLM expansion.
3. Security recommendation: whitelist callable tools by agent and validate tool args with strict schemas before execution.
