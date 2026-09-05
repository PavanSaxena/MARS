import logging
import re
from typing import List, Optional, Set, Dict, Any

from app.core.config import settings
from app.storage.retriever import retrieve_cases

logger = logging.getLogger("app.retrieval")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [Retrieval] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# Common stopwords to filter when calculating lexical relevance
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
    "to", "was", "were", "will", "with", "we", "our", "should", "how",
    "what", "when", "where", "which", "who", "why", "can", "could", "do",
    "does", "did", "have", "had", "been", "would", "about", "into", "over"
}


def _tokenize(text: str) -> Set[str]:
    """Tokenize text into lowercase alphanumeric words excluding basic stopwords."""
    if not text:
        return set()
    words = re.findall(r"\b[a-zA-Z0-9_\-\$]+\b", text.lower())
    return {w for w in words if len(w) > 1 and w not in _STOPWORDS}


def _calculate_lexical_score(query_tokens: Set[str], row: Dict[str, Any]) -> float:
    """
    Calculate keyword/lexical relevance score [0.0 - 1.0] between query and case fields.
    Gives higher weight to matches in the decision title and trigger.
    """
    if not query_tokens:
        return 0.0

    title_tokens = _tokenize(str(row.get("decision_title", "")))
    trigger_tokens = _tokenize(str(row.get("trigger", "")))
    desc_tokens = _tokenize(str(row.get("decision_description", "")))
    reasoning_tokens = _tokenize(str(row.get("reasoning_summary", "")))

    all_case_tokens = title_tokens | trigger_tokens | desc_tokens | reasoning_tokens
    if not all_case_tokens:
        return 0.0

    # Key fields matching
    title_matches = len(query_tokens & title_tokens)
    trigger_matches = len(query_tokens & trigger_tokens)
    body_matches = len(query_tokens & (desc_tokens | reasoning_tokens))

    # Weighted match count
    weighted_matches = (title_matches * 2.0) + (trigger_matches * 1.5) + (body_matches * 1.0)
    max_possible = len(query_tokens) * 2.0

    return min(1.0, round(weighted_matches / max_possible, 4))


def _calculate_case_similarity(tokens_a: Set[str], tokens_b: Set[str]) -> float:
    """Calculate Jaccard token similarity between two cases to quantify redundancy."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union > 0 else 0.0


def get_similar_cases(
    query: str,
    domain: Optional[str] = None,
    candidate_count: Optional[int] = None,
    min_cases: Optional[int] = None,
    max_cases: Optional[int] = None,
    similarity_floor: Optional[float] = None,
    mmr_lambda: Optional[float] = None,
    k: Optional[int] = None,
) -> List[dict]:
    """
    Retrieve top candidate cases (e.g. 20-30), rerank them based on contextual
    relevance and vector similarity, eliminate redundancy, and return a diverse
    selection of 3-10 top evidence cases.

    Args:
        query:            Natural language query to search for.
        domain:           Optional department filter ('finance', 'legal', 'rd', 'operations').
        candidate_count:  Number of candidates fetched from vector search (default: settings.RETRIEVAL_CANDIDATE_COUNT).
        min_cases:        Minimum target cases to return if relevant (default: settings.RETRIEVAL_MIN_CASES).
        max_cases:        Maximum diverse cases to return (default: settings.RETRIEVAL_MAX_CASES).
        similarity_floor: Soft similarity floor to reject non-relevance noise (default: settings.RETRIEVAL_SIMILARITY_FLOOR).
        mmr_lambda:       MMR balance parameter (1.0 = purely relevant, 0.0 = purely diverse).
        k:                Backward compatibility alias for max_cases.

    Returns:
        List of selected case documents formatted as dicts.
    """
    candidate_count = candidate_count or getattr(settings, "RETRIEVAL_CANDIDATE_COUNT", 25)
    min_cases = min_cases or getattr(settings, "RETRIEVAL_MIN_CASES", 3)
    max_cases = k or max_cases or getattr(settings, "RETRIEVAL_MAX_CASES", 10)
    similarity_floor = similarity_floor if similarity_floor is not None else getattr(settings, "RETRIEVAL_SIMILARITY_FLOOR", 0.25)
    mmr_lambda = mmr_lambda if mmr_lambda is not None else getattr(settings, "RETRIEVAL_MMR_LAMBDA", 0.65)

    # 1. Fetch Candidate Pool (20-30 candidates from vector DB)
    rows = retrieve_cases(query=query, k=candidate_count, domain=domain)
    logger.info(
        f"Retrieved {len(rows)} raw candidates for domain='{domain}', query='{query[:60]}...'"
    )

    if not rows:
        logger.info(f"No candidate rows returned from vector search for domain='{domain}'.")
        return []

    query_tokens = _tokenize(query)

    # 2. Score and Rerank Candidates
    scored_candidates = []
    for row in rows:
        similarity = row.get("similarity")
        sim_val = float(similarity) if isinstance(similarity, (int, float)) else 0.0

        # Filter out complete noise below soft floor
        if sim_val < similarity_floor:
            continue

        lexical_score = _calculate_lexical_score(query_tokens, row)
        # Composite contextual relevance score (weighted blend of vector similarity and lexical match)
        composite_relevance = round((0.65 * sim_val) + (0.35 * lexical_score), 4)

        # Prepare tokens for redundancy check
        doc_text = (
            f"{row.get('decision_title', '')} {row.get('trigger', '')} "
            f"{row.get('decision_description', '')} {row.get('reasoning_summary', '')}"
        )
        case_tokens = _tokenize(doc_text)

        scored_candidates.append({
            "row": row,
            "vector_sim": round(sim_val, 4),
            "lexical_score": lexical_score,
            "relevance_score": composite_relevance,
            "tokens": case_tokens,
            "case_id": row.get("case_id"),
            "title": row.get("decision_title", "Untitled"),
            "quarter": row.get("quarter", ""),
            "risk_level": row.get("risk_level", ""),
            "outcome": row.get("outcome_summary", "unknown"),
        })

    # Log candidate scores for evaluation
    logger.info(f"Scored {len(scored_candidates)} candidates above similarity floor ({similarity_floor}):")
    for idx, c in enumerate(scored_candidates[:15]):  # log top 15 candidates
        logger.info(
            f"  Candidate #{idx + 1}: ID={c['case_id']}, Q={c['quarter']}, "
            f"VecSim={c['vector_sim']}, LexScore={c['lexical_score']}, "
            f"Composite={c['relevance_score']}, Title='{c['title'][:40]}'"
        )

    if not scored_candidates:
        logger.info(f"All candidates were below similarity floor ({similarity_floor}). Returning 0 cases.")
        return []

    # Sort candidates by initial composite relevance descending
    scored_candidates.sort(key=lambda x: x["relevance_score"], reverse=True)
    best_score = scored_candidates[0]["relevance_score"]

    # 3. Maximal Marginal Relevance (MMR) & Diversity Filtering
    # Select cases that provide strong evidence while penalizing redundancy
    selected_candidates = []
    remaining_pool = list(scored_candidates)

    while remaining_pool and len(selected_candidates) < max_cases:
        best_mmr_score = -999.0
        best_candidate_idx = -1

        for idx, candidate in enumerate(remaining_pool):
            # Calculate maximum redundancy with already selected cases
            if not selected_candidates:
                redundancy = 0.0
            else:
                redundancies = [
                    _calculate_case_similarity(candidate["tokens"], s["tokens"])
                    for s in selected_candidates
                ]
                redundancy = max(redundancies) if redundancies else 0.0

            # MMR formula: lambda * relevance - (1 - lambda) * max_redundancy
            mmr_score = (mmr_lambda * candidate["relevance_score"]) - ((1.0 - mmr_lambda) * redundancy)

            if mmr_score > best_mmr_score:
                best_mmr_score = mmr_score
                best_candidate_idx = idx

        if best_candidate_idx == -1:
            break

        chosen = remaining_pool.pop(best_candidate_idx)

        # Stop condition: if we already have min_cases, and candidate relevance is too degraded (< 40% of best)
        if len(selected_candidates) >= min_cases and chosen["relevance_score"] < (best_score * 0.40):
            logger.info(
                f"Halting selection at {len(selected_candidates)} cases (Candidate ID={chosen['case_id']} "
                f"score {chosen['relevance_score']} < 40% of best {best_score})"
            )
            break

        selected_candidates.append(chosen)

    # 4. Build Final Formatted Output
    cases = []
    for c in selected_candidates:
        row = c["row"]
        sim_val = c["vector_sim"]
        distance = max(0.0, 1.0 - sim_val)

        document = (
            f"Decision Title: {row.get('decision_title', '')}\n"
            f"Trigger: {row.get('trigger', '')}\n"
            f"Decision Description: {row.get('decision_description', '')}\n"
            f"Reasoning Summary: {row.get('reasoning_summary', '')}\n"
            f"Risk Level: {row.get('risk_level', '')}\n"
            f"Outcome Summary: {row.get('outcome_summary', '')}"
        )

        cases.append({
            "document": document,
            "metadata": {
                "case_id": c["case_id"],
                "quarter": c["quarter"],
                "department": row.get("department", ""),
                "risk_level": c["risk_level"],
                "outcome": c["outcome"],
                "similarity": sim_val,
                "relevance_score": c["relevance_score"],
            },
            "distance": distance,
            "outcome": c["outcome"],
        })

    # Log selected cases and final count
    logger.info(f"--- Final Selected Evidence Cases for domain='{domain}' (Count: {len(cases)}) ---")
    for idx, case in enumerate(cases):
        meta = case["metadata"]
        logger.info(
            f"  Selected #{idx + 1}: ID={meta['case_id']} ({meta['quarter']}) | "
            f"Sim={meta['similarity']} | Relevance={meta['relevance_score']} | "
            f"Risk={meta['risk_level']} | Outcome='{meta['outcome'][:30]}'"
        )

    return cases


class CaseRetrievalService:
    """Thin wrapper class for dependency-injection use cases."""

    def retrieve(
        self,
        query: str,
        domain: Optional[str] = None,
        candidate_count: Optional[int] = None,
        min_cases: Optional[int] = None,
        max_cases: Optional[int] = None,
        similarity_floor: Optional[float] = None,
    ) -> List[dict]:
        return get_similar_cases(
            query=query,
            domain=domain,
            candidate_count=candidate_count,
            min_cases=min_cases,
            max_cases=max_cases,
            similarity_floor=similarity_floor,
        )
