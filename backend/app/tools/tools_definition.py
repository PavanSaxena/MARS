
from typing import List

from app.services.case_retrieval_service import get_similar_cases


def retrieve_similar_cases(query: str, domain: str, k: int = 5) -> List[dict]:
    """Wrapper around Supabase (pgvector) retrieval to return a normalized list of cases."""
    return get_similar_cases(query=query, domain=domain, k=k)


def summarize_case_risk_tool(query: str, cases: List[dict]) -> str:
    """Summarize operational risks from retrieved cases to inform agent reasoning."""
    if not cases:
        return "No similar cases found to assess operational risks."

    summary = "Operational Risk Summary based on Similar Cases:\n"
    for idx, case in enumerate(cases, start=1):
        summary += f"{idx}. Case: {case['document']}\n   Risk Factors: {case['metadata'].get('risk_factors', 'N/A')}\n   Distance: {case['distance']:.4f}\n"
    return summary