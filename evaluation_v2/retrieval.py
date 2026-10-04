"""Leakage-safe retrieval benchmark for MARS.

The older retrieval benchmark measured whether a retriever could find the same
case used to construct the query. This module evaluates historical precedent
retrieval instead: target cases are removed and only earlier decisions are
eligible.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

import numpy as np

from evaluation_v2.dataset import (
    REPO_ROOT,
    CaseRecord,
    decision_text,
    load_cases,
    replay_query_text,
    split_cases,
    visible_corpus,
)
from evaluation_v2.metrics import (
    binary_relevance_metrics,
    intra_list_diversity,
    mean_dicts,
    ndcg_at_k,
)


TOKEN_RE = re.compile(r"\b[a-zA-Z0-9_\-$]+\b")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "in", "is", "it", "its", "of", "on", "or", "that", "the",
    "to", "was", "were", "will", "with", "we", "our", "should", "how",
    "what", "when", "where", "which", "who", "why", "can", "could", "do",
    "does", "did", "have", "had", "been", "would", "about", "into", "over",
}


def tokenize(text: str) -> List[str]:
    return [tok.lower() for tok in TOKEN_RE.findall(text or "") if len(tok) > 1 and tok.lower() not in STOPWORDS]


class BM25Index:
    def __init__(self, docs: Sequence[Dict[str, Any]], text_key: str = "decision_text", k1: float = 1.5, b: float = 0.75):
        self.docs = list(docs)
        self.k1 = k1
        self.b = b
        self.doc_tokens = [tokenize(str(doc.get(text_key, ""))) for doc in self.docs]
        self.doc_lens = [len(tokens) for tokens in self.doc_tokens]
        self.avgdl = sum(self.doc_lens) / max(1, len(self.doc_lens))
        df: Counter[str] = Counter()
        for tokens in self.doc_tokens:
            df.update(set(tokens))
        self.idf = {
            term: math.log(1 + (len(self.docs) - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def scores(self, query: str) -> np.ndarray:
        q_tokens = tokenize(query)
        scores = np.zeros(len(self.docs), dtype=np.float32)
        for idx, tokens in enumerate(self.doc_tokens):
            tf = Counter(tokens)
            doc_len = self.doc_lens[idx] or 1
            score = 0.0
            for qt in q_tokens:
                freq = tf.get(qt, 0)
                if not freq:
                    continue
                denom = freq + self.k1 * (1 - self.b + self.b * (doc_len / max(self.avgdl, 1e-9)))
                score += self.idf.get(qt, 0.0) * (freq * (self.k1 + 1)) / max(denom, 1e-9)
            scores[idx] = score
        return scores

    def retrieve(self, query: str, k: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        scores = self.scores(query)
        order = np.argsort(-scores)[:k]
        return [(self.docs[i], float(scores[i])) for i in order]


class DenseIndex:
    def __init__(self, docs: Sequence[Dict[str, Any]]):
        from backend.app.storage.embedder import get_embeddings

        self.docs = list(docs)
        texts = [str(doc.get("decision_text", "")) for doc in self.docs]
        self.embeddings = np.array(get_embeddings(texts), dtype=np.float32)

    def retrieve(self, query: str, k: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        from backend.app.storage.embedder import get_embedding

        q = np.array(get_embedding(query), dtype=np.float32)
        sims = self.embeddings @ q
        order = np.argsort(-sims)[:k]
        return [(self.docs[i], float(sims[i])) for i in order]


class HybridIndex:
    def __init__(self, docs: Sequence[Dict[str, Any]], dense_weight: float = 0.65, use_mmr: bool = False, mmr_lambda: float = 0.65):
        self.docs = list(docs)
        self.bm25 = BM25Index(docs)
        self.dense_weight = dense_weight
        self.use_mmr = use_mmr
        self.mmr_lambda = mmr_lambda
        from backend.app.storage.embedder import get_embeddings

        self.embeddings = np.array(get_embeddings([str(doc.get("decision_text", "")) for doc in docs]), dtype=np.float32)

    def retrieve(self, query: str, k: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        from backend.app.storage.embedder import get_embedding

        if not self.docs:
            return []
        dense_scores = self.embeddings @ np.array(get_embedding(query), dtype=np.float32)
        bm25_scores = self.bm25.scores(query)
        bm25_norm = _minmax(bm25_scores)
        dense_norm = _minmax(dense_scores)
        scores = self.dense_weight * dense_norm + (1 - self.dense_weight) * bm25_norm
        candidate_order = list(np.argsort(-scores)[: min(50, len(scores))])
        if not self.use_mmr:
            return [(self.docs[i], float(scores[i])) for i in candidate_order[:k]]

        selected: List[int] = []
        remaining = candidate_order
        token_sets = [set(tokenize(str(doc.get("decision_text", "")))) for doc in self.docs]
        while remaining and len(selected) < k:
            best_idx = remaining[0]
            best_score = -1e9
            for idx in remaining:
                redundancy = max((_jaccard(token_sets[idx], token_sets[s]) for s in selected), default=0.0)
                mmr_score = self.mmr_lambda * float(scores[idx]) - (1 - self.mmr_lambda) * redundancy
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx
            selected.append(best_idx)
            remaining = [idx for idx in remaining if idx != best_idx]
        return [(self.docs[i], float(scores[i])) for i in selected]


def relevance_sets(target: CaseRecord, corpus: Sequence[Dict[str, Any]]) -> Tuple[Set[str], Dict[str, int]]:
    relevant: Set[str] = set()
    graded: Dict[str, int] = {}
    target_cross = {x.strip().lower() for x in target.cross_dept_impact.split(";") if x.strip()}
    for doc in corpus:
        cid = str(doc["case_id"])
        rel = 0
        if doc.get("department") == target.department and doc.get("action_type") == target.action_type:
            rel = 3
        elif doc.get("department") == target.department:
            rel = 2
        else:
            doc_dept = str(doc.get("department", "")).lower()
            doc_cross = str(doc.get("cross_dept_impact", "")).lower()
            if doc_dept in target_cross or any(x and x in doc_cross for x in target_cross):
                rel = 1
        if rel > 0:
            relevant.add(cid)
            graded[cid] = rel
    return relevant, graded


def run_retrieval_evaluation(
    *,
    split_name: str = "test",
    max_queries: int | None = None,
    k: int = 10,
    include_dense: bool = False,
) -> Dict[str, Any]:
    cases = load_cases()
    splits = split_cases(cases)
    queries = splits[split_name]
    if max_queries is not None:
        queries = queries[:max_queries]

    system_rows: Dict[str, List[Dict[str, float]]] = {
        "bm25_temporal": [],
    }
    if include_dense:
        system_rows["dense_temporal"] = []
        system_rows["hybrid_temporal"] = []
        system_rows["hybrid_mmr_temporal"] = []

    per_case: List[Dict[str, Any]] = []
    leakage_violations = []
    unavailable_systems: Dict[str, str] = {}

    for target in queries:
        corpus = visible_corpus(
            cases,
            as_of_date=target.decision_date,
            target_case_id=target.case_id,
            include_visible_outcomes=False,
        )
        relevant, graded = relevance_sets(target, corpus)
        query = replay_query_text(target)
        systems: Dict[str, Any] = {"bm25_temporal": BM25Index(corpus)}
        if include_dense:
            if "dense_temporal" not in unavailable_systems:
                try:
                    systems["dense_temporal"] = DenseIndex(corpus)
                except Exception as exc:
                    unavailable_systems["dense_temporal"] = str(exc)
            if "hybrid_temporal" not in unavailable_systems:
                try:
                    systems["hybrid_temporal"] = HybridIndex(corpus, use_mmr=False)
                except Exception as exc:
                    unavailable_systems["hybrid_temporal"] = str(exc)
            if "hybrid_mmr_temporal" not in unavailable_systems:
                try:
                    systems["hybrid_mmr_temporal"] = HybridIndex(corpus, use_mmr=True)
                except Exception as exc:
                    unavailable_systems["hybrid_mmr_temporal"] = str(exc)

        case_record: Dict[str, Any] = {
            "case_id": target.case_id,
            "decision_date": target.decision_date,
            "department": target.department,
            "action_type": target.action_type,
            "visible_corpus_size": len(corpus),
            "relevant_pool_size": len(relevant),
            "systems": {},
        }

        for name, index in systems.items():
            start = time.perf_counter()
            retrieved = index.retrieve(query, k=k)
            latency_ms = (time.perf_counter() - start) * 1000
            docs = [doc for doc, _ in retrieved]
            ids = [str(doc["case_id"]) for doc in docs]
            if target.case_id in ids:
                leakage_violations.append({"case_id": target.case_id, "system": name, "type": "self_retrieval"})
            metrics = binary_relevance_metrics(ids, relevant, k_values=(1, 3, 5, 10))
            metrics["ndcg_at_10"] = ndcg_at_k(ids, graded, k=10)
            metrics["diversity_at_10"] = intra_list_diversity(docs)
            metrics["latency_ms"] = latency_ms
            system_rows[name].append(metrics)
            case_record["systems"][name] = {
                "retrieved_ids": ids,
                "metrics": {key: round(value, 6) for key, value in metrics.items()},
            }
        per_case.append(case_record)

    return {
        "protocol": "evaluation_v2 temporal leave-target-out retrieval",
        "split": split_name,
        "queries_evaluated": len(queries),
        "include_dense": include_dense,
        "summary": {name: mean_dicts(rows) for name, rows in system_rows.items()},
        "unavailable_systems": unavailable_systems,
        "leakage_violations": leakage_violations,
        "per_case": per_case,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run leakage-safe retrieval evaluation.")
    parser.add_argument("--split", default="test", choices=["train", "validation", "test"])
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument("--include-dense", action="store_true", help="Run embedding baselines; may require model download/cache.")
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "evaluation_v2" / "artifacts" / "retrieval_results.json"),
    )
    args = parser.parse_args()
    result = run_retrieval_evaluation(
        split_name=args.split,
        max_queries=args.max_queries,
        include_dense=args.include_dense,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "queries_evaluated": result["queries_evaluated"],
        "summary": result["summary"],
        "unavailable_systems": result["unavailable_systems"],
        "leakage_violations": len(result["leakage_violations"]),
    }, indent=2))


def _minmax(values: np.ndarray) -> np.ndarray:
    lo = float(np.min(values))
    hi = float(np.max(values))
    if math.isclose(lo, hi):
        return np.zeros_like(values, dtype=np.float32)
    return ((values - lo) / (hi - lo)).astype(np.float32)


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


if __name__ == "__main__":
    main()
