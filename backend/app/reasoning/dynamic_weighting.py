"""
Query-Adaptive Dynamic Weighting Engine.
=========================================
Implements research-backed query-conditioned, agent-specific dynamic feature weighting
for Case-Based Reasoning confidence scoring, grounded in:
1. Wettschereck, Aha, & Mohri (1997) "A Review and Empirical Evaluation of Feature
   Weighting Methods for Lazy Learning Algorithms" (Local / Query-Dependent Weighting)
2. Jacobs, Jordan, Nowlan, & Hinton (1991) "Adaptive Mixtures of Local Experts"
   (Input-Dependent Gating Networks)
3. Hastie & Tibshirani (1996) "Discriminant Adaptive Nearest Neighbor Classification"
4. Cruz, Sabourin, & Cavalcanti (2018) "Dynamic Ensemble Selection: A Review"
   (Agent Competence Regions)

Replaces rigid, precomputed offline weights with dynamic simplex projection:
    (w1, w2, w3) = f(Query, AgentDomain)
where w1 (Similarity) + w2 (Recency) + w3 (PastSuccess) = 1.0 and w_i >= 0.10.
"""

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Canonical semantic anchor descriptions for query intent extraction
ANCHOR_PROFILES: Dict[str, str] = {
    "temporal_urgency": (
        "Recent updates, latest developments, current quarter regulations, upcoming deadlines, "
        "new laws, ongoing market volatility, immediate compliance mandates, fiscal year 2024 2025."
    ),
    "risk_stakes": (
        "High stakes capital allocation, catastrophic downside risk, financial loss, margin collapse, "
        "bankruptcy, severe regulatory fines, billions of dollars at risk, unrecoverable contract default."
    ),
    "precedent_specificity": (
        "Exact technical specification, architectural precedent, specific INT8 quantization steps, "
        "detailed procedural protocol, step by step implementation, contractual clause analog."
    ),
}

# Domain-specific base priors reflecting each agent's organizational mandate
AGENT_DOMAIN_PRIORS: Dict[str, Tuple[float, float, float]] = {
    # [w_sim, w_rec, w_succ]
    "legal": (0.38, 0.42, 0.20),      # High recency (laws change) + strict precedent similarity
    "finance": (0.30, 0.18, 0.52),    # High past success (ROI & track record) + financial safety
    "rd": (0.52, 0.28, 0.20),         # High similarity (technical analogy) + modern tech recency
    "operations": (0.42, 0.20, 0.38), # Balanced similarity & past execution reliability
    "default": (0.40, 0.25, 0.35),
}

# Lexical marker patterns
RE_TEMPORAL = re.compile(
    r"\b(202[3-6]|q[1-4]|fy2[3-6]|latest|recent|currently?|upcoming|immediate|fresh|new|updated|ongoing|today|now)\b",
    re.IGNORECASE,
)
RE_RISK = re.compile(
    r"(\$|billion|million|capital|invest|budget|roi|margin|write-?down|impairment|penalt|lawsuit|fine|catastroph|shutdown|bankrupt|severe|risk|danger|liabilit|covenant)",
    re.IGNORECASE,
)
RE_PRECEDENT = re.compile(
    r"\b(how did|exact|specif|architect|quantiz|formula|code|step-by-step|protocol|clause|precedent|analog|mechanis|configur)\b",
    re.IGNORECASE,
)

_anchor_cache: Optional[Dict[str, np.ndarray]] = None


def _get_anchor_embeddings() -> Dict[str, np.ndarray]:
    """Compute and cache normalized embedding centroids for query intent dimensions."""
    global _anchor_cache
    if _anchor_cache is None:
        try:
            from app.storage.embedder import get_embeddings
            keys = list(ANCHOR_PROFILES.keys())
            descriptions = [ANCHOR_PROFILES[k] for k in keys]
            embeddings = get_embeddings(descriptions)
            _anchor_cache = {
                k: np.array(emb, dtype=np.float32)
                for k, emb in zip(keys, embeddings)
            }
        except Exception:
            # Fallback if sentence-transformers is unavailable
            _anchor_cache = {}
    return _anchor_cache


@dataclass
class DynamicWeightResult:
    """Represents the dynamic weights calculated for an agent and query."""
    weights: Tuple[float, float, float]
    w_similarity: float
    w_recency: float
    w_past_success: float
    department: str
    query_signals: Dict[str, float] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "weights": list(self.weights),
            "w_similarity": self.w_similarity,
            "w_recency": self.w_recency,
            "w_past_success": self.w_past_success,
            "department": self.department,
            "query_signals": self.query_signals,
            "rationale": self.rationale,
        }


class QueryAdaptiveWeightEngine:
    """
    Computes dynamic, query-conditioned weights for heterogeneous department agents.
    
    Combines:
    1. Lexical and semantic intent extraction from the query (Temporal, Risk, Precedent)
    2. Agent-specific domain priors (Legal vs Finance vs R&D vs Operations)
    3. Simplex projection ensuring bounds (w_i >= 0.10) and sum(w_i) == 1.0
    4. Natural language explainability rationale for transparency
    """

    def __init__(self, modulation_gain: float = 0.50):
        self.gain = modulation_gain

    def extract_query_signals(self, query: str) -> Dict[str, float]:
        """
        Extract normalized sensitivity signals [0.0, 1.0] across:
        - temporal_urgency (boosts w2 recency)
        - risk_stakes (boosts w3 past success)
        - precedent_specificity (boosts w1 similarity)
        """
        if not query or not query.strip():
            return {
                "temporal_urgency": 0.333,
                "risk_stakes": 0.333,
                "precedent_specificity": 0.333,
            }

        q_clean = query.strip()

        # 1. Lexical density scores
        temporal_matches = len(RE_TEMPORAL.findall(q_clean))
        risk_matches = len(RE_RISK.findall(q_clean))
        precedent_matches = len(RE_PRECEDENT.findall(q_clean))

        lex_temp = min(1.0, temporal_matches * 0.35)
        lex_risk = min(1.0, risk_matches * 0.35)
        lex_prec = min(1.0, precedent_matches * 0.35)

        # 2. Semantic vector similarity scores
        sem_temp, sem_risk, sem_prec = 0.3, 0.3, 0.3
        anchors = _get_anchor_embeddings()
        if anchors:
            try:
                from app.storage.embedder import get_embedding
                q_emb = np.array(get_embedding(q_clean), dtype=np.float32)
                sem_temp = max(0.0, float(np.dot(q_emb, anchors.get("temporal_urgency", q_emb))))
                sem_risk = max(0.0, float(np.dot(q_emb, anchors.get("risk_stakes", q_emb))))
                sem_prec = max(0.0, float(np.dot(q_emb, anchors.get("precedent_specificity", q_emb))))
            except Exception:
                pass

        # 3. Fuse lexical + semantic signals
        raw_temp = 0.5 * lex_temp + 0.5 * sem_temp
        raw_risk = 0.5 * lex_risk + 0.5 * sem_risk
        raw_prec = 0.5 * lex_prec + 0.5 * sem_prec

        total = raw_temp + raw_risk + raw_prec
        if total <= 1e-6:
            return {
                "temporal_urgency": 0.333,
                "risk_stakes": 0.333,
                "precedent_specificity": 0.333,
            }

        return {
            "temporal_urgency": round(raw_temp / total, 4),
            "risk_stakes": round(raw_risk / total, 4),
            "precedent_specificity": round(raw_prec / total, 4),
        }

    def compute_weights(
        self,
        query: Optional[str] = None,
        department: Optional[str] = None,
        action_type: Optional[str] = None,
    ) -> DynamicWeightResult:
        """
        Compute dynamic weights (w1, w2, w3) for a given query and agent department.
        """
        dept_key = (department or "").lower().strip()
        prior = AGENT_DOMAIN_PRIORS.get(dept_key, AGENT_DOMAIN_PRIORS["default"])
        p_sim, p_rec, p_succ = prior

        if not query or not query.strip():
            # No query provided: return calibrated base prior
            return DynamicWeightResult(
                weights=(round(p_sim, 3), round(p_rec, 3), round(p_succ, 3)),
                w_similarity=round(p_sim, 3),
                w_recency=round(p_rec, 3),
                w_past_success=round(p_succ, 3),
                department=dept_key or "default",
                query_signals={"temporal_urgency": 0.333, "risk_stakes": 0.333, "precedent_specificity": 0.333},
                rationale=f"Baseline domain prior applied for {dept_key or 'default'} department (no query specified).",
            )

        # Extract signals
        signals = self.extract_query_signals(query)
        s_rec = signals["temporal_urgency"]
        s_succ = signals["risk_stakes"]
        s_sim = signals["precedent_specificity"]

        # Mean centering of signals (so neutral query does not displace prior)
        s_mean = (s_sim + s_rec + s_succ) / 3.0
        delta_sim = s_sim - s_mean
        delta_rec = s_rec - s_mean
        delta_succ = s_succ - s_mean

        # Modulate agent prior
        u_sim = max(0.10, p_sim * (1.0 + self.gain * delta_sim))
        u_rec = max(0.10, p_rec * (1.0 + self.gain * delta_rec))
        u_succ = max(0.10, p_succ * (1.0 + self.gain * delta_succ))

        # Simplex normalization
        total_u = u_sim + u_rec + u_succ
        w1 = round(u_sim / total_u, 3)
        w2 = round(u_rec / total_u, 3)
        w3 = round(1.0 - w1 - w2, 3)

        # Enforce bounds
        if w3 < 0.10:
            diff = 0.10 - w3
            w3 = 0.10
            if w1 >= w2:
                w1 = round(w1 - diff, 3)
            else:
                w2 = round(w2 - diff, 3)

        # Generate explainable rationale
        shifted_factors = []
        if delta_rec > 0.04:
            shifted_factors.append(f"temporal freshness/regulatory urgency (w2={w2:.2f})")
        if delta_succ > 0.04:
            shifted_factors.append(f"historical past success/risk mitigation (w3={w3:.2f})")
        if delta_sim > 0.04:
            shifted_factors.append(f"exact structural precedent similarity (w1={w1:.2f})")

        dept_title = dept_key.upper() if dept_key else "SPECIALIST"
        if shifted_factors:
            rationale = (
                f"Dynamic {dept_title} weights adapted to query intent: elevated "
                + " and ".join(shifted_factors)
                + f". Resulting simplex: [w_sim={w1:.2f}, w_rec={w2:.2f}, w_succ={w3:.2f}]."
            )
        else:
            rationale = (
                f"Dynamic {dept_title} weights balanced across balanced query signals: "
                f"[w_sim={w1:.2f}, w_rec={w2:.2f}, w_succ={w3:.2f}]."
            )

        return DynamicWeightResult(
            weights=(w1, w2, w3),
            w_similarity=w1,
            w_recency=w2,
            w_past_success=w3,
            department=dept_key or "default",
            query_signals=signals,
            rationale=rationale,
        )


# Global singleton instance
dynamic_weight_engine = QueryAdaptiveWeightEngine()
