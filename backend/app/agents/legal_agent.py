from typing import Any, Dict

from app.agents.common import execute_department_agent, parse_structured_output
from app.state import State


def legal_agent(state: State) -> Dict[str, Any]:
    """Legal Agent: Evaluates legal risks, regulatory constraints, and compliance."""
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
        rules=[
            "Keep historical_case_evidence, legal_evidence, and judicial_evidence distinct; historical MARS cases do not establish what current law says",
            "For Indian statutory text use search_laws then get_law; use search_regulations for subordinate legislation and search_judgments/get_judgment for judicial interpretation",
            "Never present secondary web discovery or third-party judgment data as definitive or authoritative law",
            "When authoritative verification is unavailable, state that explicitly and identify any secondary sources as unverified discovery",
            "Include legal_evidence and judicial_evidence arrays in the JSON when legal tools return evidence; include type, id, title, section, jurisdiction, source, authority, source_url, and retrieved_at when available",
            "Do not fabricate provisions, citations, case names, dates, statuses, or metadata; preserve unknown fields as unknown",
            "Confidence reflects the strength and authority of evidence actually considered, including legal sources, from 0.0 to 1.0",
            "case_based_confidence remains a separate score over historical MARS cases and is not changed by legal-source authority",
        ],
    )


def parse_legal_output(text: str) -> Dict[str, Any]:
    """Parse structured fields from Legal LLM output."""
    return parse_structured_output(text, preserve_legal_confidence=True)
