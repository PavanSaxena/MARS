
from typing import List


def retrieve_similar_cases(query: str, domain: str, k: int = 5) -> List[dict]:
    """Wrapper around ChromaDB retrieval to return a normalized list of cases."""
    from app.storage.chroma_client import get_collection

    collection = get_collection()
    try:
        results = collection.query(
            query_texts=[query],
            n_results=k,
            where={"department": domain},
        )
    except Exception as e:
        raise RuntimeError(f"ChromaDB retrieval failed: {str(e)}")

    cases = []
    for doc_list, meta_list, dist_list in zip(results.get("documents", []), results.get("metadatas", []), results.get("distances", [])):
        for doc, meta, dist in zip(doc_list, meta_list, dist_list):
            cases.append({
                "document": doc,
                "metadata": meta,
                "distance": dist,
            })
    return cases


def summarize_case_risk_tool(query: str, cases: List[dict]) -> str:
    """Summarize operational risks from retrieved cases to inform agent reasoning."""
    if not cases:
        return "No similar cases found to assess operational risks."

    summary = "Operational Risk Summary based on Similar Cases:\n"
    for idx, case in enumerate(cases, start=1):
        summary += f"{idx}. Case: {case['document']}\n   Risk Factors: {case['metadata'].get('risk_factors', 'N/A')}\n   Distance: {case['distance']:.4f}\n"
    return summary