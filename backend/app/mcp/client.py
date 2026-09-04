"""
MCP client for the department-agent tool layer.

Tool definitions and execution both live behind the real MCP server in
app.mcp.server, spawned as a subprocess over stdio the first time any tool
is needed and kept alive (one subprocess, one session) for the life of the
backend process — not re-spawned per call. Everything else in the codebase
(app.tools.tool_registry, app.tools.tool_executor) only ever talks to this
module; nothing outside app/mcp imports the tool implementations directly
anymore.

The rest of the codebase is synchronous (FastAPI request handlers, the
LangGraph nodes), but the MCP SDK's ClientSession is async-only, so this
module owns a single background thread running its own asyncio event loop
and exposes plain sync functions (get_langchain_tools_sync, call_tool_sync)
that hop onto that loop via asyncio.run_coroutine_threadsafe.
"""
import asyncio
import atexit
import sys
import threading
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class _MCPClientThread:
    """Owns the background event loop + the single long-lived MCP session."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._session: Optional[ClientSession] = None
        self._ready = threading.Event()
        self._start_lock = threading.Lock()
        self._stop_event: Optional[asyncio.Event] = None
        self._start_error: Optional[BaseException] = None

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._main())
        except BaseException as exc:  # surfaced to the caller of start()
            self._start_error = exc
            self._ready.set()

    async def _main(self) -> None:
        # Spawns `python -m app.mcp.server` as a child process and talks to
        # it over stdio — the standard MCP transport for an in-process
        # server that doesn't need to be reachable over the network.
        server_params = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp.server"])
        self._stop_event = asyncio.Event()
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self._session = session
                self._ready.set()
                await self._stop_event.wait()

    def start(self) -> None:
        """Idempotent: spawns the server subprocess on first call, no-op after."""
        with self._start_lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, daemon=True, name="mcp-client")
                self._thread.start()
        if not self._ready.wait(timeout=30):
            raise RuntimeError("MCP client timed out waiting for the mars-tools server to start.")
        if self._start_error is not None:
            raise RuntimeError(f"MCP client failed to start: {self._start_error}") from self._start_error
        if self._session is None:
            raise RuntimeError("MCP client failed to start (no session established).")

    def stop(self) -> None:
        if self._loop is not None and self._stop_event is not None:
            self._loop.call_soon_threadsafe(self._stop_event.set)

    def run_coro(self, coro):
        self.start()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=60)

    @property
    def session(self) -> ClientSession:
        self.start()
        return self._session


_client = _MCPClientThread()
atexit.register(_client.stop)


def call_tool_sync(name: str, arguments: Dict[str, Any]) -> str:
    """Call an MCP tool by name over the live session and return its text
    result. Raises RuntimeError if the tool call itself errored."""

    async def _call() -> str:
        result = await _client.session.call_tool(name, arguments)
        text = "\n".join(getattr(c, "text", "") for c in result.content if hasattr(c, "text"))
        if result.isError:
            raise RuntimeError(text or f"MCP tool '{name}' returned an error.")
        return text

    return _client.run_coro(_call())


def get_langchain_tools_sync() -> List[Any]:
    """Return every tool exposed by the mars-tools MCP server as
    LangChain-compatible tool objects (name, description, args_schema),
    ready to pass to llm.bind_tools(...). Invoking one of these objects
    round-trips through the MCP session exactly like call_tool_sync does —
    this is only used for advertising tool schemas to the LLM; actual
    execution still goes through app.tools.tool_executor.execute_tool_call
    so the per-agent allowlist is enforced in one place."""
    from langchain_mcp_adapters.tools import load_mcp_tools

    return _client.run_coro(load_mcp_tools(_client.session))
