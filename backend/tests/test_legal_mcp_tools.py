"""End-to-end MCP bridge checks using a local India Code HTTP fixture."""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_legal_tools_execute_through_live_mcp_server(monkeypatch):
    from app.tools.tool_executor import execute_tool_call

    class IndiaCodeFixture(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            query = parse_qs(urlparse(self.path).query).get("query", [""])[0]
            metadata = {
                "dc.title": [{"value": "The Example Act, 2024"}],
                "dc.identifier.act_id": [{"value": "9876"}],
                "dc.identifier.collection": [{"value": "RULE" if "Rule" in query else "ACT"}],
            }
            if path.endswith("/search/objects"):
                body = {"_embedded": {"searchResult": {"_embedded": {"objects": [{
                    "_embedded": {"indexableObject": {"metadata": metadata,
                        "handle": "123456789/9876", "uuid": "test-item-uuid"}}
                }]}}}}
                content_type = "application/json"
            elif path.endswith("/items/test-item-uuid"):
                body = {"metadata": metadata, "_links": {"bundles": {
                    "href": f"http://127.0.0.1:{self.server.server_port}/server/bundles"}}}
                content_type = "application/json"
            elif path.endswith("/server/bundles"):
                body = {"_embedded": {"bundles": [{"name": "TEXT", "_links": {"bitstreams": {
                    "href": f"http://127.0.0.1:{self.server.server_port}/server/bitstreams"}}}]}}
                content_type = "application/json"
            elif path.endswith("/server/bitstreams"):
                body = {"_embedded": {"bitstreams": [{"name": "act.txt", "_links": {"content": {
                    "href": f"http://127.0.0.1:{self.server.server_port}/server/content"}}}]}}
                content_type = "application/json"
            else:
                body = "Section 1. Official test text."
                content_type = "text/plain; charset=utf-8"
            encoded = json.dumps(body).encode() if isinstance(body, dict) else body.encode()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, _format, *_args):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), IndiaCodeFixture)
    worker = Thread(target=http.serve_forever, daemon=True)
    worker.start()
    monkeypatch.setenv("MARS_INDIACODE_BASE_URL", f"http://127.0.0.1:{http.server_port}")
    # An empty inherited value overrides any developer-local .env token, so
    # the unsupported-jurisdiction check cannot call a metered web API.
    monkeypatch.setenv("TAVILY_API_KEY", "")
    # Keep the test deterministic and prevent accidental paid court API calls.
    monkeypatch.setenv("ECOURTSINDIA_API_TOKEN", "")
    monkeypatch.chdir(BACKEND_ROOT)
    try:
        disallowed = execute_tool_call("finance_agent", "search_laws", {"query": "Example Act", "country": "India"})
        assert disallowed["status"] == "error"
        assert "not registered" in disallowed["message"]

        search = execute_tool_call("legal_agent", "search_laws", {"query": "Example Act", "country": "India"})
        assert search["status"] == "success"
        payload = json.loads(search["result"])
        assert payload["authority"] == "authoritative"
        assert payload["results"][0]["id"] == "9876"
        assert payload["results"][0]["source_url"].startswith("http://127.0.0.1:")

        retrieval = execute_tool_call("legal_agent", "get_law", {
            "law_name_or_id": "The Example Act, 2024", "country": "India"
        })
        assert retrieval["status"] == "success"
        law = json.loads(retrieval["result"])["result"]
        assert law["authority"] == "authoritative"
        assert "Section 1. Official test text." in law["full_text"]

        regulations = execute_tool_call("legal_agent", "search_regulations", {
            "query": "Example Rule", "country": "India"
        })
        assert regulations["status"] == "success"
        assert json.loads(regulations["result"])["results"][0]["type"] == "subordinate_legislation"

        jurisdictions = execute_tool_call("legal_agent", "list_supported_jurisdictions", {})
        assert jurisdictions["status"] == "success"
        supported = json.loads(jurisdictions["result"])
        assert [row["country"] for row in supported["supported"]] == ["India"]

        for tool_name, arguments in (
            ("search_judgments", {"query": "Example judgment", "country": "India"}),
            ("get_judgment", {"judgment_id": "EXAMPLE-CNR", "country": "India"}),
        ):
            result = execute_tool_call("legal_agent", tool_name, arguments)
            assert result["status"] == "success"
            unavailable = json.loads(result["result"])
            assert unavailable["error"] == "provider_unavailable"
            assert "ECOURTSINDIA_API_TOKEN" in unavailable["message"]

        unsupported = execute_tool_call("legal_agent", "search_laws", {
            "query": "Example statute", "country": "Antarctica"
        })
        assert unsupported["status"] == "success"
        fallback = json.loads(unsupported["result"])
        assert fallback["authority"] == "secondary"
        assert fallback["authoritative_verification"] == "unavailable"
    finally:
        http.shutdown()
        http.server_close()
        worker.join(timeout=2)
