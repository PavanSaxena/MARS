"""India Code legislation search and optional eCourtsIndia judgment API."""
from datetime import datetime, timezone
import os
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import quote, urlparse

import requests

from .base import LegalProvider, LegalProviderError


class IndiaCodeProvider(LegalProvider):
    jurisdiction = "India"
    authority_level = "authoritative"
    source_name = "India Code (Ministry of Law and Justice)"
    base_url = "https://indiacode.gov.in"
    search_path = "/api/discover/search/objects"

    def __init__(self) -> None:
        self.timeout = 10
        self.base_url = os.getenv("MARS_INDIACODE_BASE_URL", type(self).base_url).rstrip("/")
        self._failures = 0
        self._opened_until = 0.0

    def _get(self, url: str, params: dict[str, Any] | None = None, *, json_expected: bool = False) -> Any:
        if time.monotonic() < self._opened_until:
            raise LegalProviderError("India legal provider circuit is open after repeated failures.")
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = requests.get(url, params=params, timeout=self.timeout,
                                        headers={"User-Agent": "MARS-Legal-Research/1.0"})
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                self._failures = 0
                return response.json() if json_expected else response.text
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.25 * (2 ** attempt))
        self._failures += 1
        if self._failures >= 3:
            self._opened_until = time.monotonic() + 30
            self._failures = 0
        raise LegalProviderError(f"India legal provider unavailable: {last_error}") from last_error

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _metadata_value(metadata: dict[str, Any], key: str) -> Any:
        values = metadata.get(key) or []
        if isinstance(values, list):
            return values[0].get("value") if values and isinstance(values[0], dict) else None
        return values

    @staticmethod
    def _search_objects(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        return (payload.get("_embedded", {}).get("searchResult", {})
                .get("_embedded", {}).get("objects", []))

    def _official_get(self, url: str, *, json_expected: bool = True) -> Any:
        expected_host = urlparse(self.base_url).netloc
        if urlparse(url).netloc != expected_host:
            raise LegalProviderError("India Code returned an unexpected document host.")
        return self._get(url, json_expected=json_expected)

    def _search(self, query: str, *, label: str = "statute") -> list[Dict[str, Any]]:
        server_base = self.base_url.rstrip("/") + "/server"
        payload = self._get(server_base + self.search_path,
                            {"query": query, "size": 10}, json_expected=True)
        results = []
        for wrapper in self._search_objects(payload):
            item = wrapper.get("_embedded", {}).get("indexableObject", {}) if isinstance(wrapper, dict) else {}
            metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
            if not item or not isinstance(metadata, dict):
                continue
            title = self._metadata_value(metadata, "dc.title") or item.get("name")
            handle = item.get("handle")
            if not title or not handle:
                continue
            collection = self._metadata_value(metadata, "dc.identifier.collection")
            if label == "statute" and collection and str(collection).upper() != "ACT":
                continue
            if label == "subordinate_legislation" and collection and str(collection).upper() == "ACT":
                continue
            act_id = self._metadata_value(metadata, "dc.identifier.act_id")
            issued = self._metadata_value(metadata, "dc.date.issued") or self._metadata_value(metadata, "dc.date.enact_date")
            results.append({"id": act_id or item.get("uuid") or item.get("id"), "title": title,
                            "jurisdiction": self.jurisdiction, "type": label,
                            "status": "unknown", "effective_date": self._metadata_value(metadata, "dc.date.effective"),
                            "introduced_date": issued,
                            "source": self.source_name,
                            "source_url": f"{self.base_url.rstrip('/')}/handle/{handle}",
                            "handle": handle, "item_uuid": item.get("uuid"),
                            "collection": collection,
                            "relevant_provisions": [], "authority": "authoritative",
                            "retrieved_at": self._now()})
            if len(results) == 10:
                break
        return results

    def search_laws(self, query: str) -> list[Dict[str, Any]]:
        return self._search(query)

    def search_regulations(self, query: str) -> list[Dict[str, Any]]:
        return self._search(query, label="subordinate_legislation")

    def _get_document(self, name_or_id: str, *, label: str) -> Optional[Dict[str, Any]]:
        results = self._search(name_or_id, label=label)
        needle = name_or_id.strip().lower()
        match = next((r for r in results if r["id"] == name_or_id or r.get("handle") == name_or_id
                      or r["title"].lower() == needle), None)
        if not match:
            return None
        server_base = self.base_url.rstrip("/") + "/server"
        item_uuid = match.get("item_uuid")
        if not item_uuid:
            return None
        item_url = f"{server_base}/api/core/items/{quote(str(item_uuid), safe='')}"
        item = self._official_get(item_url)
        if not isinstance(item, dict):
            raise LegalProviderError("India Code returned a malformed Act record.")
        bundles_url = item.get("_links", {}).get("bundles", {}).get("href")
        bundles = self._official_get(bundles_url) if bundles_url else {}
        bundle_rows = bundles.get("_embedded", {}).get("bundles", []) if isinstance(bundles, dict) else []
        text_bundle = next((b for b in bundle_rows if isinstance(b, dict) and b.get("name") == "TEXT"), None)
        bitstreams_url = text_bundle.get("_links", {}).get("bitstreams", {}).get("href") if text_bundle else None
        bitstreams = self._official_get(bitstreams_url) if bitstreams_url else {}
        bitstream_rows = bitstreams.get("_embedded", {}).get("bitstreams", []) if isinstance(bitstreams, dict) else []
        text_bitstream = next((b for b in bitstream_rows if isinstance(b, dict) and b.get("name", "").endswith(".txt")), None)
        content_url = text_bitstream.get("_links", {}).get("content", {}).get("href") if text_bitstream else None
        full_text = self._official_get(content_url, json_expected=False) if content_url else ""
        if not full_text:
            raise LegalProviderError("India Code Act record had no published text bitstream.")
        metadata = item.get("metadata", {})
        match.update({"full_text": full_text[:200000], "sections": [],
                      "effective_date": self._metadata_value(metadata, "dc.date.effective"),
                      "introduced_date": self._metadata_value(metadata, "dc.date.issued") or match.get("introduced_date"),
                      "provenance": f"Text fetched from the India Code official DSpace TEXT bitstream ({label}).",
                      "currentness": "official_text_retrieved; in-force status and later amendments not independently verified"})
        return match

    def get_law(self, law_name_or_id: str) -> Optional[Dict[str, Any]]:
        return self._get_document(law_name_or_id, label="statute")

    def get_regulation(self, regulation_name_or_id: str) -> Optional[Dict[str, Any]]:
        return self._get_document(regulation_name_or_id, label="subordinate_legislation")

    def _judgment_request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        token = os.getenv("ECOURTSINDIA_API_TOKEN")
        if not token:
            raise LegalProviderError("Judgment search requires ECOURTSINDIA_API_TOKEN; authoritative judgment verification is unavailable.")
        base = os.getenv("ECOURTSINDIA_API_BASE_URL", "https://webapi.ecourtsindia.com")
        url = base.rstrip("/") + path
        try:
            response = requests.get(url, params=params, timeout=self.timeout,
                                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise LegalProviderError(f"eCourtsIndia judgment service unavailable: {exc}") from exc

    def search_judgments(self, query: str) -> list[Dict[str, Any]]:
        payload = self._judgment_request("/api/partner/search", {"query": query, "pageSize": 10})
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        rows = data.get("results", data.get("items", [])) if isinstance(data, dict) else []
        return [{"type": "judgment", "id": str(r.get("cnr") or r.get("id") or ""),
                 "title": r.get("caseTitle") or r.get("title") or
                         (" vs ".join([" / ".join(r.get("petitioners", [])), " / ".join(r.get("respondents", []))]).strip(" vs ")) or "Untitled judgment",
                 "court": r.get("courtName") or r.get("court"), "date": r.get("decisionDate"),
                 "citations": r.get("citations", []), "headnote": r.get("headnote"),
                 "jurisdiction": self.jurisdiction, "source": "eCourtsIndia API",
                 "authority": "secondary", "source_url": r.get("url") or
                     f"{os.getenv('ECOURTSINDIA_API_BASE_URL', 'https://webapi.ecourtsindia.com').rstrip('/')}/api/partner/case/{quote(str(r.get('cnr') or r.get('id') or ''), safe='')}",
                 "retrieved_at": self._now(),
                 "note": "Third-party court-data API; verify against the court's official judgment record."}
                for r in rows if isinstance(r, dict)][:10]

    def get_judgment(self, judgment_id: str) -> Optional[Dict[str, Any]]:
        payload = self._judgment_request(f"/api/partner/case/{judgment_id}")
        result = payload.get("data", payload) if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            return None
        case_data = result.get("courtCaseData", {}) or {}
        descriptions = result.get("descriptions", {}) or {}
        enum_lookup = descriptions.get("enumLookup", {}) if isinstance(descriptions, dict) else {}
        court_names = enum_lookup.get("courtCode", {}) if isinstance(enum_lookup, dict) else {}
        petitioners = case_data.get("petitioners", []) or []
        respondents = case_data.get("respondents", []) or []
        parties = " vs ".join(parties for parties in (" / ".join(petitioners), " / ".join(respondents)) if parties)
        files = result.get("files", {}) or {}
        file_items = files.get("files", []) if isinstance(files, dict) else files
        full_text = "\n\n".join(f.get("markdownContent", "") for f in file_items
                                 if isinstance(f, dict) and f.get("markdownContent")) if isinstance(file_items, list) else ""
        judgment_orders = case_data.get("judgmentOrders", []) or []
        text_note = None
        if not full_text and judgment_orders:
            latest_order = max(judgment_orders, key=lambda order: order.get("orderDate") or "")
            filename = latest_order.get("orderUrl")
            if filename:
                try:
                    order_payload = self._judgment_request(
                        f"/api/partner/case/{quote(judgment_id, safe='')}/order-md/{quote(filename, safe='')}"
                    )
                    order_data = order_payload.get("data", {}) if isinstance(order_payload, dict) else {}
                    full_text = order_data.get("markdownContent") or ""
                except LegalProviderError as exc:
                    text_note = f"Order text could not be retrieved: {exc}"
        return {"type": "judgment", "id": judgment_id,
                "title": result.get("title") or case_data.get("caseTitle") or parties or judgment_id,
                "court": case_data.get("courtName") or court_names.get(str(case_data.get("courtCode"))) or result.get("courtName") or result.get("court"),
                "court_code": case_data.get("cnrCourtCode") or case_data.get("courtCode"),
                "date": case_data.get("decisionDate") or result.get("decisionDate"),
                "bench": case_data.get("judges", []),
                "citations": case_data.get("provisions", case_data.get("actsAndSections", result.get("citations", []))),
                "headnote": result.get("headnote"), "full_text": full_text or result.get("text") or result.get("orderText"),
                "text_note": text_note,
                "jurisdiction": self.jurisdiction, "source": "eCourtsIndia API",
                "authority": "secondary", "source_url": result.get("url") or
                    f"{os.getenv('ECOURTSINDIA_API_BASE_URL', 'https://webapi.ecourtsindia.com').rstrip('/')}/api/partner/case/{quote(judgment_id, safe='')}",
                "retrieved_at": self._now(),
                "note": "Third-party court-data API; verify against the court's official judgment record."}
