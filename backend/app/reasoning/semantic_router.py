"""Semantic Vector Gating Router (Embedding-Space Mixture-of-Agents).

Dynamically routes strategic queries to relevant department specialists by computing
cosine similarity between the query embedding and department semantic centroids,
avoiding fragile prompt-based keyword rules.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np

from app.storage.embedder import get_embedding, get_embeddings

# Canonical semantic anchor descriptions per department
DEPARTMENT_ANCHOR_PROFILES: Dict[str, str] = {
    "finance": (
        "Corporate financial planning, treasury liquidity, capital expenditures, "
        "gross margin targets, operating cash flow, share buybacks, dividend allocation, "
        "pricing strategy, commercial paper yields, tax liabilities, and revenue growth."
    ),
    "legal": (
        "Regulatory compliance, antitrust investigations, EU Digital Markets Act (DMA), "
        "DOJ lawsuits, patent infringement litigation, FTC inquiries, intellectual property, "
        "bilateral contracts, privacy policies, labor covenants, and force majeure clauses."
    ),
    "rd": (
        "Research and development, software engineering, machine learning quantization, "
        "Neural Engine compute graphs, CoreML optimization, silicon chip architecture, "
        "A16/M2 processors, firmware efficiency, SRAM cache, and battery runtime."
    ),
    "operations": (
        "Supply chain logistics, tier-1 electronics manufacturing (Foxconn, Pegatron), "
        "TSMC silicon wafer procurement, channel inventory rebalancing, assembly capacity, "
        "factory lockdown recovery, freight shipping, and supplier fulfillment obligations."
    ),
}

_centroid_cache: Optional[Dict[str, np.ndarray]] = None


def _get_department_centroids() -> Dict[str, np.ndarray]:
    """Compute and cache normalized embedding centroids for all departments."""
    global _centroid_cache
    if _centroid_cache is None:
        departments = list(DEPARTMENT_ANCHOR_PROFILES.keys())
        descriptions = [DEPARTMENT_ANCHOR_PROFILES[d] for d in departments]
        embeddings = get_embeddings(descriptions)
        _centroid_cache = {
            dept: np.array(emb, dtype=np.float32)
            for dept, emb in zip(departments, embeddings)
        }
    return _centroid_cache


def route_departments_semantically(
    query: str,
    threshold: float = 0.32,
    margin_ratio: float = 0.70,
    min_departments: int = 1,
) -> Tuple[List[str], Dict[str, float]]:
    """
    Dynamically route query to active departments using embedding-space gating.

    Args:
        query: User natural language query.
        threshold: Absolute cosine similarity floor to activate a department.
        margin_ratio: Relative activation threshold (must be >= best_score * margin_ratio).
        min_departments: Minimum active departments (guarantees at least top 1-2 departments).

    Returns:
        Tuple of (active_departments_list, similarity_scores_dict).
    """
    if not query or not query.strip():
        return ["finance", "rd", "legal", "operations"], {}

    query_emb = np.array(get_embedding(query.strip()), dtype=np.float32)
    centroids = _get_department_centroids()

    # Compute cosine similarities (normalized dot product)
    scores: Dict[str, float] = {}
    for dept, centroid in centroids.items():
        sim = float(np.dot(query_emb, centroid))
        scores[dept] = round(sim, 4)

    # Sort departments descending by semantic similarity
    sorted_depts = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_score = sorted_depts[0][1]

    # Dynamic gating: select departments above floor AND within relative margin of top match
    active: List[str] = []
    for dept, score in sorted_depts:
        if score >= threshold and score >= (best_score * margin_ratio):
            active.append(dept)

    # Guarantee minimum departments
    if len(active) < min_departments:
        active = [d for d, _ in sorted_depts[:min_departments]]

    # If scores across all departments are close (broad strategic query), include all
    score_spread = best_score - sorted_depts[-1][1]
    if score_spread < 0.08 and best_score >= threshold:
        active = ["finance", "rd", "legal", "operations"]

    return active, scores
