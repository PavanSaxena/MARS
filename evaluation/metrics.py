"""Metrics used by leakage-safe MARS evaluations."""

from __future__ import annotations

import math
import random
from typing import Any, Dict, Iterable, List, Sequence, Set


def binary_relevance_metrics(
    retrieved_ids: Sequence[str],
    relevant_ids: Set[str],
    *,
    k_values: Sequence[int] = (1, 3, 5, 10),
) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k in k_values:
        top = list(retrieved_ids[:k])
        hits = sum(1 for cid in top if cid in relevant_ids)
        out[f"precision_at_{k}"] = hits / k if k else 0.0
        out[f"recall_at_{k}"] = hits / len(relevant_ids) if relevant_ids else 0.0
        out[f"hit_at_{k}"] = 1.0 if hits > 0 else 0.0

    rr = 0.0
    for idx, cid in enumerate(retrieved_ids, start=1):
        if cid in relevant_ids:
            rr = 1.0 / idx
            break
    out["mrr"] = rr
    return out


def ndcg_at_k(retrieved_ids: Sequence[str], graded_relevance: Dict[str, int], k: int = 10) -> float:
    gains = [graded_relevance.get(cid, 0) for cid in retrieved_ids[:k]]
    dcg = sum((2**rel - 1) / math.log2(idx + 2) for idx, rel in enumerate(gains))
    ideal = sorted(graded_relevance.values(), reverse=True)[:k]
    idcg = sum((2**rel - 1) / math.log2(idx + 2) for idx, rel in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def intra_list_diversity(retrieved_docs: Sequence[Dict[str, Any]]) -> float:
    """Simple department/action diversity score in [0, 1]."""
    if len(retrieved_docs) <= 1:
        return 0.0
    pairs = 0
    diverse = 0
    for i in range(len(retrieved_docs)):
        for j in range(i + 1, len(retrieved_docs)):
            pairs += 1
            a = retrieved_docs[i]
            b = retrieved_docs[j]
            if a.get("department") != b.get("department") or a.get("action_type") != b.get("action_type"):
                diverse += 1
    return diverse / pairs if pairs else 0.0


def brier_score(probs: Sequence[float], labels: Sequence[int]) -> float:
    _validate_equal(probs, labels)
    return sum((float(p) - int(y)) ** 2 for p, y in zip(probs, labels)) / len(labels)


def nll(probs: Sequence[float], labels: Sequence[int], eps: float = 1e-12) -> float:
    _validate_equal(probs, labels)
    total = 0.0
    for p, y in zip(probs, labels):
        p = min(1.0 - eps, max(eps, float(p)))
        total -= math.log(p) if y else math.log(1.0 - p)
    return total / len(labels)


def calibration_curve(
    probs: Sequence[float],
    labels: Sequence[int],
    *,
    n_bins: int = 10,
) -> Dict[str, Any]:
    _validate_equal(probs, labels)
    bins = []
    ece = 0.0
    mce = 0.0
    n = len(labels)
    for idx in range(n_bins):
        lo = idx / n_bins
        hi = (idx + 1) / n_bins
        member_idx = [
            i
            for i, p in enumerate(probs)
            if (lo <= p < hi) or (idx == n_bins - 1 and lo <= p <= hi)
        ]
        if member_idx:
            avg_conf = sum(float(probs[i]) for i in member_idx) / len(member_idx)
            avg_acc = sum(int(labels[i]) for i in member_idx) / len(member_idx)
            gap = abs(avg_acc - avg_conf)
            ece += (len(member_idx) / n) * gap
            mce = max(mce, gap)
        else:
            avg_conf = (lo + hi) / 2
            avg_acc = 0.0
            gap = 0.0
        bins.append(
            {
                "bin": idx,
                "lower": round(lo, 3),
                "upper": round(hi, 3),
                "count": len(member_idx),
                "avg_confidence": round(avg_conf, 4),
                "avg_accuracy": round(avg_acc, 4),
                "gap": round(avg_acc - avg_conf, 4),
            }
        )
    return {
        "brier": round(brier_score(probs, labels), 6),
        "nll": round(nll(probs, labels), 6),
        "ece": round(ece, 6),
        "mce": round(mce, 6),
        "bins": bins,
    }


def paired_bootstrap_ci(
    baseline: Sequence[float],
    system: Sequence[float],
    *,
    iterations: int = 5000,
    seed: int = 42,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    _validate_equal(baseline, system)
    rng = random.Random(seed)
    n = len(baseline)
    observed = sum(s - b for b, s in zip(baseline, system)) / n
    diffs = []
    non_positive = 0
    for _ in range(iterations):
        idxs = [rng.randrange(n) for _ in range(n)]
        diff = sum(system[i] - baseline[i] for i in idxs) / n
        diffs.append(diff)
        if diff <= 0:
            non_positive += 1
    diffs.sort()
    lo = diffs[int((alpha / 2) * iterations)]
    hi = diffs[min(iterations - 1, int((1 - alpha / 2) * iterations))]
    return {
        "observed_difference": round(observed, 6),
        "p_one_sided_system_not_better": round(non_positive / iterations, 6),
        "ci_lower": round(lo, 6),
        "ci_upper": round(hi, 6),
        "iterations": iterations,
    }


def mean_dicts(rows: Sequence[Dict[str, float]]) -> Dict[str, float]:
    if not rows:
        return {}
    keys = sorted({key for row in rows for key in row})
    return {
        key: round(sum(float(row.get(key, 0.0)) for row in rows) / len(rows), 6)
        for key in keys
    }


def _validate_equal(a: Sequence[Any], b: Sequence[Any]) -> None:
    if not a or len(a) != len(b):
        raise ValueError("Metric inputs must be non-empty and have equal length.")

