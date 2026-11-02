import json
import re
from typing import Any, Dict

from app.agents.common import execute_department_agent, parse_structured_output
from app.state import State


def _india_legal_search_plan(query: str) -> dict[str, list[str]] | None:
    """Select focused official-law, regulation, and judgment searches for India."""
    lower = query.lower()
    if not any(term in lower for term in ("india", "indian", "bharat")):
        return None

    plans = [
        (("personal data", "data protection", "data-protection", "privacy"),
         ["Digital Personal Data Protection Act 2023"], ["Digital Personal Data Protection Rules"],
         ["Indian data protection law relevant judgments"]),
        (("employment", "labour", "labor", "termination", "misconduct", "disciplinary",
          "dismissal", "workman", "worker", "industrial relations", "standing order"),
         ["Industrial Relations Code 2020"], ["Industrial Relations Code Central Rules"],
         ["termination for misconduct without disciplinary inquiry India judgments"]),
        (("sexual harassment", "posh", "workplace harassment"),
         ["Sexual Harassment of Women at Workplace Act 2013"],
         ["Sexual Harassment of Women at Workplace Rules 2013"],
         ["Indian workplace sexual harassment law judgments"]),
        (("consumer", "defective product", "unfair trade"),
         ["Consumer Protection Act 2019"], ["Consumer Protection Rules 2020"],
         ["Indian consumer protection relevant judgments"]),
        (("contract", "breach of agreement", "contractual"),
         ["Indian Contract Act 1872"], [], ["Indian contract law relevant judgments"]),
        (("company", "corporate", "director", "shareholder"),
         ["Companies Act 2013"], ["Companies Rules 2014"], ["Indian company law relevant judgments"]),
    ]
    for terms, laws, regulations, judgments in plans:
        if any(term in lower for term in terms):
            return {"laws": laws, "regulations": regulations, "judgments": judgments}

    # Keep a useful generic path for Indian-law topics not yet in the curated map.
    compact_query = " ".join(query.split())[:220]
    return {"laws": [compact_query], "regulations": [compact_query], "judgments": [compact_query]}


def _payload(result: dict) -> dict:
    try:
        parsed = json.loads(result.get("result") or "{}") if result.get("status") == "success" else {}
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _rank_india_code_results(rows: list, search_query: str, *, exact_topic: bool) -> list[dict]:
    """Prefer results whose official title actually matches the planned topic."""
    stop_words = {"the", "of", "and", "for", "under", "current", "law", "india", "indian"}
    query_tokens = {token for token in re.findall(r"[a-z0-9]+", search_query.lower())
                    if token not in stop_words}
    scored = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title_tokens = {token for token in re.findall(r"[a-z0-9]+", str(row.get("title", "")).lower())
                        if token not in stop_words}
        score = len(query_tokens & title_tokens) / max(1, len(query_tokens))
        scored.append((score, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    floor = 0.45 if exact_topic else 0.12
    return [row for score, row in scored if score >= floor][:3]


def _relevant_law_excerpt(text: str, query: str, title: str) -> str:
    """Bound primary-source text sent to the LLM while retaining likely provisions."""
    lower = (query + " " + title).lower()
    if any(term in lower for term in ("employment", "labour", "labor", "termination", "misconduct",
                                      "disciplinary", "dismissal", "worker", "workman", "industrial relations")):
        relevant = {2, 28, 29, 30, 38, 50, 53}
    elif any(term in lower for term in ("personal data", "data protection", "privacy")):
        relevant = {3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 33}
    else:
        relevant = set()

    body_start = text.find("BE it enacted")
    if body_start < 0:
        body_start = 0
    heading_pattern = re.compile(r"(?m)^[ \t]*(\d{1,3})\.[ \t]+[^\n]+")
    headings = list(heading_pattern.finditer(text, body_start))
    excerpts = []
    for index, heading in enumerate(headings):
        if relevant and int(heading.group(1)) not in relevant:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        section = text[heading.start():end].strip()
        if relevant or any(term in section.lower() for term in ("misconduct", "dismissal", "termination", "inquiry", "worker")):
            excerpts.append(section)
    excerpt = "\n\n".join(excerpts) if excerpts else text[:12000]
    return excerpt[:14000]


def _preload_india_data_protection_sources(query: str) -> tuple[list[dict], str]:
    """Compatibility wrapper retained for focused DPDP lookup callers."""
    return _preload_india_legal_sources(query, include_supplementary=False)


def _preload_india_legal_sources(query: str, *, include_supplementary: bool = True) -> tuple[list[dict], str]:
    """Deterministically retrieve relevant India Code material before drafting.

    LLM tool choice is optional and inconsistent. This path makes source retrieval
    a required first step for Indian-law questions, and keeps legislation,
    subordinate rules, and third-party judgment discovery separately labelled.
    """
    plan = _india_legal_search_plan(query)
    if not plan:
        return [], ""

    from app.tools.tool_executor import execute_tool_call

    records: list[dict] = []
    context_parts: list[str] = []
    documents: list[tuple[str, dict]] = []

    search_groups = [("search_laws", plan["laws"])]
    if include_supplementary:
        search_groups.append(("search_regulations", plan["regulations"]))
    for tool_name, queries in search_groups:
        for search_query in queries:
            result = execute_tool_call("legal_agent", tool_name,
                                       {"query": search_query, "country": "India"})
            records.append({"tool": tool_name, **result})
            payload = _payload(result)
            raw_rows = payload.get("results", [])
            rows = _rank_india_code_results(raw_rows, search_query,
                                            exact_topic=search_query != " ".join(query.split())[:220]) \
                if isinstance(raw_rows, list) else []
            # Keep only title-matched results in the evidence stream so a broad
            # search cannot make an obsolete or unrelated Act look applicable.
            if isinstance(payload, dict):
                payload["results"] = rows
                result = {**result, "result": json.dumps(payload, ensure_ascii=False)}
                records[-1] = {"tool": tool_name, **result}
            if rows:
                for row in rows:
                    if isinstance(row, dict) and row.get("authority") == "authoritative" and row.get("title"):
                        documents.append((tool_name, row))
            if result.get("status") != "success" or payload.get("error"):
                context_parts.append(
                    f"{tool_name} lookup for '{search_query}' failed or was unavailable: "
                    f"{payload.get('message') or result.get('message') or 'no details returned'}."
                )
            elif not rows:
                context_parts.append(f"No India Code result was returned for {tool_name}: '{search_query}'.")

    # De-duplicate records and fetch full text for at most two most relevant
    # statutes/rules, keeping the prompt within model context and rate limits.
    unique_documents = []
    seen = set()
    for tool_name, row in documents:
        key = (tool_name, row.get("id") or row.get("handle") or row.get("title"))
        if key not in seen:
            seen.add(key)
            unique_documents.append((tool_name, row))
    unique_documents = unique_documents[:2]

    for search_tool, row in unique_documents:
        is_regulation = search_tool == "search_regulations"
        detail_tool = "get_regulation" if is_regulation else "get_law"
        argument = "regulation_name_or_id" if is_regulation else "law_name_or_id"
        detail = execute_tool_call("legal_agent", detail_tool,
                                   {argument: row.get("title") or row.get("id"), "country": "India"})
        records.append({"tool": detail_tool, **detail})
        detail_payload = _payload(detail)
        law = detail_payload.get("result", {}) if isinstance(detail_payload, dict) else {}
        if not isinstance(law, dict) or not law.get("full_text"):
            context_parts.append(
                f"The official text for {row.get('title')} could not be retrieved; do not state its provisions as verified."
            )
            continue
        context_parts.append(
            f"AUTHORITATIVE INDIA CODE {('REGULATION' if is_regulation else 'STATUTE')} TEXT. "
            f"Title: {law.get('title')}. URL: {law.get('source_url')}. "
            f"Record status: {law.get('status', 'unknown')}; effective date: {law.get('effective_date') or 'not supplied'}. "
            "This verifies the official published text only. The provider did not independently verify current in-force status, "
            "subsequent amendments, or commencement notifications; state those limits and do not claim verified currency. "
            "Relevant text follows:\n" + _relevant_law_excerpt(law["full_text"], query, law.get("title", ""))
        )

    for judgment_query in plan["judgments"] if include_supplementary else []:
        result = execute_tool_call("legal_agent", "search_judgments",
                                   {"query": judgment_query, "country": "India"})
        records.append({"tool": "search_judgments", **result})
        payload = _payload(result)
        rows = payload.get("results", [])
        if not isinstance(rows, list) or not rows:
            context_parts.append(
                f"No judgment discovery results were returned for '{judgment_query}'. "
                "Judgment coverage is incomplete; do not infer that no case law exists."
            )
        else:
            summaries = []
            for item in rows[:5]:
                if not isinstance(item, dict):
                    continue
                summaries.append(
                    f"- {item.get('title')}; court={item.get('court')}; date={item.get('date')}; "
                    f"authority={item.get('authority', 'unknown')}; URL={item.get('source_url')}; "
                    f"headnote={item.get('headnote') or 'not supplied'}"
                )
            context_parts.append(
                "THIRD-PARTY JUDGMENT DISCOVERY (secondary; not an authoritative court record). "
                "Use only as leads. Do not state a holding as verified unless an official court judgment is retrieved.\n" +
                "\n".join(summaries)
            )

    if not context_parts:
        context_parts.append("India legal-source lookup returned no usable evidence; current-law verification is unavailable.")
    return records, "\n\n".join(context_parts)


def legal_agent(state: State) -> Dict[str, Any]:
    """Legal Agent: Evaluates legal risks, regulatory constraints, and compliance."""
    messages = state.get("messages", [])
    query = ""
    if messages:
        last = messages[-1]
        query = getattr(last, "content", "") or (last.get("content", "") if isinstance(last, dict) else "")
    source_results, source_context = _preload_india_legal_sources(query)
    rules = [
        "Keep historical_case_evidence, legal_evidence, and judicial_evidence distinct; historical MARS cases do not establish what current law says",
        "For Indian-law questions, use the preloaded India Code statutes and regulations before answering; deterministic retrieval has already been attempted even if you choose not to call another tool",
        "Use the retrieved statutory text to answer the user's legal question directly. Do not make internal MARS precedent a prerequisite for answering a law question",
        "Use search_laws/get_law for statutes and search_regulations/get_regulation for subordinate legislation; identify the precise title and relevant provision from the returned text",
        "India Code authority confirms the official published text, but if status is unknown or amendments/commencement were not retrieved, disclose that current in-force status was not independently verified",
        "Third-party eCourtsIndia judgment results are secondary discovery only. Do not state a case holding as verified unless the official judgment record/text was retrieved; distinguish the discovery lead from authoritative legislation",
        "Do not report that no law or case exists merely because a lookup returned no result; state that this provider did not retrieve one and explain the coverage limit",
        "When authoritative law retrieval fails, state that current-law verification is unavailable; never substitute remembered law or internal MARS cases as current law",
        "Include legal_evidence and judicial_evidence arrays in the JSON when legal tools return evidence; include type, id, title, section, jurisdiction, source, authority, source_url, and retrieved_at when available",
        "Do not fabricate provisions, citations, case names, dates, statuses, or metadata; preserve unknown fields as unknown",
        "Confidence reflects the strength and authority of evidence actually considered, including legal sources, from 0.0 to 1.0",
        "case_based_confidence remains a separate score over historical MARS cases and is not changed by legal-source authority",
    ]
    if source_context:
        rules.append(source_context)
    return execute_department_agent(
        state=state,
        department="legal",
        agent_title="Legal Department",
        output_key="legal_output",
        role_points=[
            "Analyze legal implications using historical MARS cases and retrieved legal sources as separate evidence types",
            "Use statutory tools for legislation, regulatory tools for subordinate legislation and compliance, and judgment tools for judicial interpretation",
            "Use only sources whose authority and jurisdiction are explicit; never invent provisions or citations",
        ],
        rules=rules,
        preloaded_tool_results=source_results,
    )


def parse_legal_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from Legal LLM output."""
    return parse_structured_output(text, preserve_legal_confidence=True)
