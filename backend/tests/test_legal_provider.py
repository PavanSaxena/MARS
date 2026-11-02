"""Offline tests for legal provider resolution and India provider mapping."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.mcp.providers import (  # noqa: E402
    list_supported_jurisdictions,
    normalize_country,
    resolve_country,
)
from app.mcp.providers.base import LegalProviderError  # noqa: E402
from app.mcp.providers.india import IndiaCodeProvider  # noqa: E402


def test_country_resolution_distinguishes_supported_unsupported_and_unknown():
    assert normalize_country("IN") == ("IN", "India")
    assert normalize_country("India") == ("IN", "India")
    assert normalize_country("DE") == ("DE", "Germany")
    assert normalize_country("UK") == ("GB", "United Kingdom")
    assert normalize_country("US") == ("US", "United States")
    assert resolve_country("India")["status"] == "supported"
    assert resolve_country("Antarctica")["status"] == "unsupported"
    assert resolve_country("Atlantis")["status"] == "unrecognized"


def test_supported_jurisdictions_does_not_claim_secondary_judgments_are_authoritative():
    data = list_supported_jurisdictions()
    assert [item["country"] for item in data["supported"]] == ["India"]
    assert data["supported"][0]["authority_level"] == "authoritative"
    assert "judgments" not in data["supported"][0]["covers"]
    assert data["fallback_available"] is True
    assert data["fallback_authority"] == "secondary"


def test_india_code_search_maps_authoritative_law_metadata(monkeypatch):
    provider = IndiaCodeProvider()
    provider.base_url = "https://indiacode.test"
    metadata = {
        "dc.title": [{"value": "The Example Act, 2024"}],
        "dc.identifier.act_id": [{"value": "act-2024-1"}],
        "dc.identifier.collection": [{"value": "ACT"}],
        "dc.date.enact_date": [{"value": "2024-02-01"}],
    }
    payload = {"_embedded": {"searchResult": {"_embedded": {"objects": [{
        "_embedded": {"indexableObject": {"metadata": metadata, "handle": "123456789/9876",
                                             "uuid": "test-item-uuid"}}
    }]}}}}
    monkeypatch.setattr("app.mcp.providers.india.requests.get", lambda *a, **k: SimpleNamespace(
        status_code=200, json=lambda: payload, raise_for_status=lambda: None,
    ))

    results = provider.search_laws("Example Act")
    assert len(results) == 1
    result = results[0]
    assert result["id"] == "act-2024-1"
    assert result["title"] == "The Example Act, 2024"
    assert result["jurisdiction"] == "India"
    assert result["authority"] == "authoritative"
    assert result["status"] == "unknown"
    assert result["source_url"] == "https://indiacode.test/handle/123456789/9876"
    assert result["introduced_date"] == "2024-02-01"
    assert result["retrieved_at"]


def test_get_law_retrieves_official_text_and_does_not_invent_dates(monkeypatch):
    provider = IndiaCodeProvider()
    provider.base_url = "https://indiacode.test"
    metadata = {"dc.title": [{"value": "The Example Act, 2024"}],
                "dc.identifier.act_id": [{"value": "act-2024-1"}],
                "dc.identifier.collection": [{"value": "ACT"}],
                "dc.date.enact_date": [{"value": "2024-02-01"}]}
    search_payload = {"_embedded": {"searchResult": {"_embedded": {"objects": [{
        "_embedded": {"indexableObject": {"metadata": metadata, "handle": "123456789/9876",
                                             "uuid": "test-item-uuid"}}
    }]}}}}
    item = {"metadata": metadata, "_links": {"bundles": {"href": "https://indiacode.test/server/bundles"}}}
    bundles = {"_embedded": {"bundles": [{"name": "TEXT", "_links": {"bitstreams": {
        "href": "https://indiacode.test/server/bitstreams"}}}]}}
    bitstreams = {"_embedded": {"bitstreams": [{"name": "act.txt", "_links": {"content": {
        "href": "https://indiacode.test/server/content"}}}]}}

    def fake_get(url, params=None, **kwargs):
        if params:
            return SimpleNamespace(status_code=200, json=lambda: search_payload, raise_for_status=lambda: None)
        if url.endswith("/items/test-item-uuid"):
            data, text = item, None
        elif url.endswith("/server/bundles"):
            data, text = bundles, None
        elif url.endswith("/server/bitstreams"):
            data, text = bitstreams, None
        else:
            data, text = None, "Section 1. Short title."
        return SimpleNamespace(status_code=200, json=lambda: data, text=text,
                               raise_for_status=lambda: None)

    monkeypatch.setattr("app.mcp.providers.india.requests.get", fake_get)
    law = provider.get_law("The Example Act, 2024")
    assert law is not None
    assert law["id"] == "act-2024-1"
    assert "Section 1. Short title." in law["full_text"]
    assert law["effective_date"] is None
    assert law["status"] == "unknown"
    assert "India Code official" in law["provenance"]


def test_india_provider_reports_unavailable_service(monkeypatch):
    provider = IndiaCodeProvider()

    def fail(*args, **kwargs):
        import requests
        raise requests.Timeout("timed out")

    monkeypatch.setattr("app.mcp.providers.india.requests.get", fail)
    monkeypatch.setattr("app.mcp.providers.india.time.sleep", lambda *_: None)
    with pytest.raises(LegalProviderError, match="provider unavailable"):
        provider.search_laws("Example Act")


def test_legal_agent_preloads_current_indian_data_protection_act(monkeypatch):
    from app.agents.legal_agent import _preload_india_data_protection_sources

    calls = []

    def fake_execute(_agent, tool, args):
        calls.append((tool, args))
        if tool == "search_laws":
            return {"status": "success", "result": json.dumps({"results": [{
                "title": "The Digital Personal Data Protection Act, 2023.",
                "authority": "authoritative", "source_url": "https://indiacode.gov.in/handle/act"
            }]})}
        return {"status": "success", "result": json.dumps({"result": {
            "title": "The Digital Personal Data Protection Act, 2023.",
            "source_url": "https://indiacode.gov.in/handle/act",
            "full_text": "BE it enacted by Parliament.\n4. Grounds for processing personal data.\nSection 4 verified text.\n8. General obligations of Data Fiduciary.\nSection 8 verified text."
        }})}

    monkeypatch.setattr("app.tools.tool_executor.execute_tool_call", fake_execute)
    records, context = _preload_india_data_protection_sources(
        "For a business in India planning customer-data analytics under current privacy law"
    )
    assert [call[0] for call in calls] == ["search_laws", "get_law"]
    assert [record["tool"] for record in records] == ["search_laws", "get_law"]
    assert "Section 4 verified text." in context
    assert "Section 8 verified text." in context
    assert "indiacode.gov.in/handle/act" in context


def test_ecourts_judgments_are_mapped_as_secondary(monkeypatch):
    provider = IndiaCodeProvider()
    monkeypatch.setenv("ECOURTSINDIA_API_TOKEN", "test-token")

    def fake_get(url, params=None, **kwargs):
        if url.endswith("/api/partner/search"):
            data = {"data": {"results": [{"cnr": "ABC123", "petitioners": ["A Ltd"],
                                           "respondents": ["B Ltd"], "courtName": "Example High Court",
                                           "decisionDate": "2024-01-01"}]}}
        else:
            data = {"data": {"cnr": "ABC123", "courtCaseData": {
                "courtName": "Example High Court", "decisionDate": "2024-01-01",
                "provisions": [{"act": "Example Act", "number": "1"}]},
                "files": {"files": [{"markdownContent": "Judgment text."}]}}}
        return SimpleNamespace(status_code=200, json=lambda: data,
                               raise_for_status=lambda: None)

    monkeypatch.setattr("app.mcp.providers.india.requests.get", fake_get)
    found = provider.search_judgments("contract dispute")
    assert found[0]["id"] == "ABC123"
    assert found[0]["title"] == "A Ltd vs B Ltd"
    assert found[0]["authority"] == "secondary"
    assert "third-party" in found[0]["note"].lower()

    judgment = provider.get_judgment("ABC123")
    assert judgment["full_text"] == "Judgment text."
    assert judgment["citations"][0]["act"] == "Example Act"
    assert judgment["authority"] == "secondary"


def test_legal_output_keeps_confidence_and_evidence_separate_from_case_evidence():
    from app.agents.common import _collect_legal_evidence, build_json_prompt, parse_structured_output

    parsed = parse_structured_output(json.dumps({
        "response": "No historical MARS cases were available; the statute provides relevant evidence.",
        "reasoning": "Based on the returned law text.",
        "confidence": 0.7,
        "legal_evidence": [{"id": "9876", "authority": "authoritative"}],
        "judicial_evidence": [],
    }), preserve_legal_confidence=True)
    assert parsed["confidence"] == 0.7
    assert parsed["legal_evidence"][0]["authority"] == "authoritative"
    assert parsed["judicial_evidence"] == []

    prompt = build_json_prompt("Legal Department", [], [], "query", "No relevant cases found.", [])
    assert "If no historical cases were retrieved but legal sources were found, answer using the legal sources" in prompt

    statutes, judgments, issues = _collect_legal_evidence([{
        "tool": "search_laws", "status": "success",
        "result": json.dumps({"results": [{"id": "22-2023", "title": "DPDP Act",
            "authority": "authoritative", "jurisdiction": "India", "source": "India Code"}]}),
    }])
    assert statutes[0]["title"] == "DPDP Act"
    assert statutes[0]["authority"] == "authoritative"
    assert judgments == []
    assert issues == []

    statutes, judgments, issues = _collect_legal_evidence([{
        "tool": "search_laws", "status": "success",
        "result": json.dumps({"error": "provider_unavailable", "message": "timeout"}),
    }])
    assert statutes == judgments == []
    assert issues == ["timeout"]
