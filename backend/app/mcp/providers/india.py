"""India Code legislation search and optional eCourtsIndia judgment API."""
from datetime import datetime, timezone
from html.parser import HTMLParser
import os
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urljoin

import requests

from .base import LegalProvider, LegalProviderError


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, str]] = []
        self._href = ""
        self._text = ""
        self._in_anchor = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._text = ""
            self._in_anchor = True

    def handle_data(self, data: str) -> None:
        if self._in_anchor:
            self._text += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_anchor:
            title = " ".join(self._text.split())
            if title and self._href:
                self.rows.append({"title": title, "href": self._href})
            self._in_anchor = False


class IndiaCodeProvider(LegalProvider):
    jurisdiction = "India"
    authority_level = "authoritative"
    source_name = "India Code (Ministry of Law and Justice)"
    base_url = "https://www.indiacode.nic.in"
    search_path = "/handle/123456789/1362/simple-search"

    def __init__(self) -> None:
        self.timeout = 10
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

    def _search(self, query: str, *, label: str = "statute") -> list[Dict[str, Any]]:
        html = self._get(self.base_url + self.search_path,
                         {"query": query, "rpp": 10, "sort_by": "score", "order": "desc"})
        parser = _Links()
        parser.feed(html)
        results = []
        seen = set()
        for row in parser.rows:
            href = urljoin(self.base_url, row["href"])
            if "handle/" not in href or href in seen or row["title"].lower() in {"view", "view..."}:
                continue
            seen.add(href)
            results.append({"id": href.rsplit("/", 1)[-1], "title": row["title"],
                            "jurisdiction": self.jurisdiction, "type": label,
                            "status": "unknown", "effective_date": None,
                            "source": self.source_name, "source_url": href,
                            "relevant_provisions": [], "authority": "authoritative",
                            "retrieved_at": self._now()})
            if len(results) == 10:
                break
        return results

    def search_laws(self, query: str) -> list[Dict[str, Any]]:
        return self._search(query)

    def search_regulations(self, query: str) -> list[Dict[str, Any]]:
        return self._search(query, label="subordinate_legislation")

    def get_law(self, law_name_or_id: str) -> Optional[Dict[str, Any]]:
        results = self.search_laws(law_name_or_id)
        needle = law_name_or_id.strip().lower()
        match = next((r for r in results if r["id"] == law_name_or_id or r["title"].lower() == needle), None)
        if not match:
            return None
        html = self._get(match["source_url"])
        # Preserve the official page text without inferring missing status or dates.
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = " ".join(re.sub(r"&nbsp;", " ", text).split())
        match.update({"full_text": text[:100000], "sections": [], "provenance": "Fetched from the India Code official legislation portal."})
        return match

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
                 "authority": "secondary", "source_url": r.get("url"),
                 "retrieved_at": self._now(),
                 "note": "Third-party court-data API; verify against the court's official judgment record."}
                for r in rows if isinstance(r, dict)][:10]

    def get_judgment(self, judgment_id: str) -> Optional[Dict[str, Any]]:
        payload = self._judgment_request(f"/api/partner/case/{judgment_id}")
        result = payload.get("data", payload) if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            return None
        case_data = result.get("courtCaseData", {}) or {}
        files = result.get("files", {}) or {}
        file_items = files.get("files", []) if isinstance(files, dict) else files
        full_text = "\n\n".join(f.get("markdownContent", "") for f in file_items
                                 if isinstance(f, dict) and f.get("markdownContent")) if isinstance(file_items, list) else ""
        return {"type": "judgment", "id": judgment_id,
                "title": result.get("title") or case_data.get("caseTitle") or judgment_id,
                "court": case_data.get("courtName") or result.get("courtName") or result.get("court"),
                "date": case_data.get("decisionDate") or result.get("decisionDate"),
                "citations": case_data.get("provisions", result.get("citations", [])),
                "headnote": result.get("headnote"), "full_text": full_text or result.get("text") or result.get("orderText"),
                "jurisdiction": self.jurisdiction, "source": "eCourtsIndia API",
                "authority": "secondary", "source_url": result.get("url"),
                "retrieved_at": self._now(),
                "note": "Third-party court-data API; verify against the court's official judgment record."}
