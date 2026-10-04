"""Retrieval Evaluation Engine and Indexing for MARS.

Consolidates:
1. Leakage-Safe Historical Precedent Retrieval:
   - Temporal leave-target-out retrieval evaluation over chronological splits.
   - Self-contained BM25Index, DenseIndex, and HybridIndex (with MMR).
2. BEIR / RAGChecker Benchmark:
   - Evaluation comparing Baseline R1 (BM25), Baseline R2 (Naive Dense Vector),
     and MARS (Domain-Filtered Hybrid + MMR Diversity + Cross-Dept Expansion).
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np

# Ensure backend and MARS root are on sys.path
MARS_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = MARS_DIR / "backend"
if str(MARS_DIR) not in sys.path:
    sys.path.insert(0, str(MARS_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.dataset import (
    REPO_ROOT,
    CaseRecord,
    decision_text,
    load_cases,
    load_verified_2023_dataset,
    replay_query_text,
    split_cases,
    visible_corpus,
)
from evaluation.metrics import (
    binary_relevance_metrics,
    intra_list_diversity,
    mean_dicts,
    ndcg_at_k,
)

try:
    from app.storage.embedder import get_embedding, get_embeddings
except ImportError:
    from backend.app.storage.embedder import get_embedding, get_embeddings

try:
    from app.services.case_retrieval_service import (
        _calculate_case_similarity,
        _calculate_lexical_score,
        _tokenize as _service_tokenize,
    )
except ImportError:
    try:
        from backend.app.services.case_retrieval_service import (
            _calculate_case_similarity,
            _calculate_lexical_score,
            _tokenize as _service_tokenize,
        )
    except ImportError:
        _service_tokenize = None


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


# =============================================================================
# Leakage-Safe Index Primitives
# =============================================================================

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
        self.docs = list(docs)
        texts = [str(doc.get("decision_text", "")) for doc in self.docs]
        self.embeddings = np.array(get_embeddings(texts), dtype=np.float32)

    def retrieve(self, query: str, k: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        q_emb = np.array(get_embedding(query), dtype=np.float32)
        norms = np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(q_emb)
        scores = np.dot(self.embeddings, q_emb) / np.maximum(1e-9, norms)
        order = np.argsort(-scores)[:k]
        return [(self.docs[i], float(scores[i])) for i in order]


class HybridIndex:
    def __init__(
        self,
        docs: Sequence[Dict[str, Any]],
        dense_weight: float = 0.65,
        use_mmr: bool = False,
        mmr_lambda: float = 0.65,
    ):
        self.docs = list(docs)
        self.bm25 = BM25Index(self.docs)
        self.dense_weight = dense_weight
        self.use_mmr = use_mmr
        self.mmr_lambda = mmr_lambda
        self._dense: DenseIndex | None = None

    def _ensure_dense(self) -> DenseIndex:
        if self._dense is None:
            self._dense = DenseIndex(self.docs)
        return self._dense

    def retrieve(self, query: str, k: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        bm25_scores = _minmax(self.bm25.scores(query))
        if self.dense_weight > 0.0:
            dense_scores = _minmax(self._dense_scores(query))
            combined = (1.0 - self.dense_weight) * bm25_scores + self.dense_weight * dense_scores
        else:
            combined = bm25_scores

        if not self.use_mmr:
            order = np.argsort(-combined)[:k]
            return [(self.docs[i], float(combined[i])) for i in order]

        # MMR Selection
        doc_tokens = [set(tokenize(str(d.get("decision_text", "")))) for d in self.docs]
        candidates = list(np.argsort(-combined)[: min(len(self.docs), max(k * 3, 20))])
        selected: List[int] = []

        while candidates and len(selected) < k:
            if not selected:
                best = candidates.pop(0)
                selected.append(best)
                continue

            def mmr_score(cand_idx: int) -> float:
                rel = float(combined[cand_idx])
                cand_tok = doc_tokens[cand_idx]
                max_sim = max((_jaccard(cand_tok, doc_tokens[s]) for s in selected), default=0.0)
                return self.mmr_lambda * rel - (1.0 - self.mmr_lambda) * max_sim

            best = max(candidates, key=mmr_score)
            candidates.remove(best)
            selected.append(best)

        return [(self.docs[i], float(combined[i])) for i in selected]

    def _dense_scores(self, query: str) -> np.ndarray:
        dense = self._ensure_dense()
        q_emb = np.array(get_embedding(query), dtype=np.float32)
        norms = np.linalg.norm(dense.embeddings, axis=1) * np.linalg.norm(q_emb)
        return np.dot(dense.embeddings, q_emb) / np.maximum(1e-9, norms)


# =============================================================================
# BEIR / RAGChecker Baseline Retrievers
# =============================================================================

class BM25Retriever:
    """Standard Okapi BM25 implementation for zero-shot text retrieval benchmark."""

    def __init__(self, corpus: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.doc_lens = []
        self.doc_tokens = []
        self.df = Counter()
        self.N = len(corpus)

        for doc in corpus:
            text = f"{doc.get('decision_title', '')} {doc.get('decision_description', '')} {doc.get('decision_rationale', '')} {doc.get('cross_dept_impact', '')}"
            tokens = list(_service_tokenize(text)) if _service_tokenize else tokenize(text)
            self.doc_tokens.append(tokens)
            self.doc_lens.append(len(tokens))
            unique_terms = set(tokens)
            for t in unique_terms:
                self.df[t] += 1

        self.avg_doc_len = sum(self.doc_lens) / max(1, self.N)
        self.idf = {}
        for t, freq in self.df.items():
            self.idf[t] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1.0)

    def retrieve(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        tokens = list(_service_tokenize(query)) if _service_tokenize else tokenize(query)
        scores = []
        for i in range(self.N):
            doc_len = self.doc_lens[i]
            tf = Counter(self.doc_tokens[i])
            score = 0.0
            for t in tokens:
                if t in tf:
                    t_idf = self.idf.get(t, 0.0)
                    t_tf = tf[t]
                    denom = t_tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                    score += t_idf * (t_tf * (self.k1 + 1.0)) / denom
            scores.append((score, i))

        scores.sort(key=lambda x: x[0], reverse=True)
        top_k = scores[:k]
        results = []
        for s, idx in top_k:
            res = dict(self.corpus[idx])
            res["score"] = s
            results.append(res)
        return results


class NaiveDenseRetriever:
    """Standard Dense Vector Retriever using flat cosine similarity."""

    def __init__(self, corpus: List[Dict[str, Any]], corpus_embeddings: np.ndarray):
        self.corpus = corpus
        self.corpus_embeddings = corpus_embeddings

    def retrieve(self, query_emb: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        scores = np.dot(self.corpus_embeddings, query_emb)
        top_indices = np.argsort(scores)[::-1][:k]
        results = []
        for idx in top_indices:
            res = dict(self.corpus[idx])
            res["score"] = float(scores[idx])
            results.append(res)
        return results


class MARSHybridRetriever:
    """Proposed MARS Retriever: Domain-filtered hybrid + MMR diversity."""

    def __init__(self, corpus: List[Dict[str, Any]], corpus_embeddings: np.ndarray):
        self.corpus = corpus
        self.corpus_embeddings = corpus_embeddings
        self.bm25 = BM25Retriever(corpus)

    def retrieve(
        self,
        query: str,
        query_emb: np.ndarray,
        target_department: str,
        k: int = 5,
        as_of_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # Dense scores
        dense_scores = np.dot(self.corpus_embeddings, query_emb)
        # BM25 scores
        bm25_raw = self.bm25.retrieve(query, k=len(self.corpus))
        bm25_score_map = {d["case_id"]: d["score"] for d in bm25_raw}
        max_bm25 = max(bm25_score_map.values()) if bm25_score_map else 1.0

        hybrid_candidates = []
        for idx, doc in enumerate(self.corpus):
            if as_of_date and doc.get("decision_date", "") > as_of_date:
                continue

            cid = doc["case_id"]
            d_score = float(dense_scores[idx])
            b_score = bm25_score_map.get(cid, 0.0) / max(1e-6, max_bm25)
            dept_match = 1.0 if doc.get("department") == target_department else 0.4

            raw_score = 0.55 * d_score + 0.25 * b_score + 0.20 * dept_match
            hybrid_candidates.append({
                "idx": idx,
                "doc": doc,
                "raw_score": raw_score,
                "embedding": self.corpus_embeddings[idx],
            })

        hybrid_candidates.sort(key=lambda x: x["raw_score"], reverse=True)
        pool = hybrid_candidates[: min(len(hybrid_candidates), k * 3)]

        selected: List[Dict[str, Any]] = []
        selected_embs: List[np.ndarray] = []
        mmr_lambda = 0.70

        while pool and len(selected) < k:
            if not selected:
                best = pool.pop(0)
                selected.append(best["doc"])
                selected_embs.append(best["embedding"])
                continue

            best_idx = -1
            best_mmr = -1e9
            for i, cand in enumerate(pool):
                relevance = cand["raw_score"]
                redundancy = max(float(np.dot(cand["embedding"], s_emb)) for s_emb in selected_embs)
                mmr_val = mmr_lambda * relevance - (1.0 - mmr_lambda) * redundancy
                if mmr_val > best_mmr:
                    best_mmr = mmr_val
                    best_idx = i

            chosen = pool.pop(best_idx)
            selected.append(chosen["doc"])
            selected_embs.append(chosen["embedding"])

        return selected


# =============================================================================
# Evaluation Helpers & Metrics
# =============================================================================

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


def compute_ndcg_at_k(retrieved_docs: List[Dict[str, Any]], target_doc: Dict[str, Any], k: int = 5) -> float:
    target_id = target_doc.get("case_id")
    target_dept = target_doc.get("department")
    target_action = target_doc.get("action_type")

    dcg = 0.0
    for i, doc in enumerate(retrieved_docs[:k]):
        gain = 0.0
        if doc.get("case_id") == target_id:
            gain = 3.0
        elif doc.get("department") == target_dept and doc.get("action_type") == target_action:
            gain = 2.0
        elif doc.get("department") == target_dept:
            gain = 1.0

        dcg += gain / math.log2(i + 2)

    idcg = 3.0 / math.log2(2) + 2.0 / math.log2(3) + 1.0 / math.log2(4)
    return dcg / max(1e-9, idcg)


def evaluate_retriever(
    name: str,
    retriever_fn: Any,
    queries: List[Dict[str, Any]],
    corpus: List[Dict[str, Any]],
    k: int = 5,
) -> Dict[str, Any]:
    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    reciprocal_ranks = []
    ndcg_scores = []
    latencies = []

    dept_correct_count = 0
    total_retrieved = 0
    cross_dept_hits = 0
    cross_dept_opportunities = 0

    for item in queries:
        target_id = item["case_id"]
        target_dept = item.get("department")
        impacted_str = item.get("cross_dept_impact", "")
        impacted_depts = [d.strip() for d in impacted_str.split(",") if d.strip() and d.strip() != target_dept]

        start_t = time.perf_counter()
        retrieved_docs = retriever_fn(item)
        latencies.append((time.perf_counter() - start_t) * 1000)

        retrieved_ids = [d.get("case_id") for d in retrieved_docs]

        if len(retrieved_ids) > 0 and retrieved_ids[0] == target_id:
            hits_at_1 += 1
        if target_id in retrieved_ids[:3]:
            hits_at_3 += 1
        if target_id in retrieved_ids[:5]:
            hits_at_5 += 1

        if target_id in retrieved_ids:
            rank = retrieved_ids.index(target_id) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

        ndcg_scores.append(compute_ndcg_at_k(retrieved_docs, item, k=5))

        for d in retrieved_docs[:5]:
            total_retrieved += 1
            if d.get("department") == target_dept:
                dept_correct_count += 1

        if impacted_depts:
            cross_dept_opportunities += 1
            retrieved_depts = {d.get("department") for d in retrieved_docs[:5]}
            if any(imp in retrieved_depts for imp in impacted_depts):
                cross_dept_hits += 1

    N = len(queries)
    return {
        "system": name,
        "queries_evaluated": N,
        "recall_at_1": round(hits_at_1 / N, 4),
        "recall_at_3": round(hits_at_3 / N, 4),
        "recall_at_5": round(hits_at_5 / N, 4),
        "mrr": round(float(np.mean(reciprocal_ranks)), 4),
        "ndcg_at_5": round(float(np.mean(ndcg_scores)), 4),
        "dept_routing_precision": round(dept_correct_count / max(1, total_retrieved), 4),
        "cross_dept_recall": round(cross_dept_hits / max(1, cross_dept_opportunities), 4) if cross_dept_opportunities > 0 else 1.0,
        "mean_latency_ms": round(float(np.mean(latencies)), 2),
    }


def relevance_sets(target: CaseRecord, corpus: Sequence[Dict[str, Any]]) -> Tuple[Set[str], Dict[str, int]]:
    cross_dept_terms = {tok.lower() for tok in tokenize(target.cross_dept_impact)}
    graded: Dict[str, int] = {}
    exact: Set[str] = set()

    for doc in corpus:
        cid = doc["case_id"]
        same_dept = doc.get("department") == target.department
        same_action = doc.get("action_type") == target.action_type
        doc_tokens = set(tokenize(f"{doc.get('decision_title', '')} {doc.get('decision_description', '')}"))

        if same_dept and same_action:
            graded[cid] = 3
            exact.add(cid)
        elif same_dept:
            graded[cid] = 2
        elif cross_dept_terms & doc_tokens:
            graded[cid] = 1

    return exact, graded


# =============================================================================
# High-Level Benchmark Runners
# =============================================================================

def run_retrieval_evaluation(
    *,
    split_name: str = "test",
    max_queries: int | None = None,
    include_dense: bool = False,
    output: Path | None = None,
) -> Dict[str, Any]:
    """Execute leakage-safe temporal retrieval evaluation."""
    cases = load_cases()
    splits = split_cases(cases)
    query_cases = splits[split_name]
    if max_queries is not None:
        query_cases = query_cases[:max_queries]

    systems = ["bm25", "hybrid_lexical_proxy"]
    if include_dense:
        systems.extend(["dense", "hybrid_mmr"])

    per_system_metrics: Dict[str, List[Dict[str, float]]] = {s: [] for s in systems}
    leakage_violations = []
    per_case = []

    for case in query_cases:
        query = replay_query_text(case)
        corpus = visible_corpus(cases, as_of_date=case.decision_date, target_case_id=case.case_id)
        if not corpus:
            continue

        corpus_ids = {d["case_id"] for d in corpus}
        if case.case_id in corpus_ids:
            leakage_violations.append({"case_id": case.case_id, "violation": "target_case_in_visible_corpus"})

        exact_rel, graded_rel = relevance_sets(case, corpus)
        bm25_index = BM25Index(corpus)
        retrieved_map: Dict[str, List[str]] = {}

        bm25_retrieved = [doc["case_id"] for doc, _ in bm25_index.retrieve(query, k=10)]
        retrieved_map["bm25"] = bm25_retrieved

        hybrid_proxy_retrieved = [
            doc["case_id"]
            for doc, _ in HybridIndex(corpus, dense_weight=0.0, use_mmr=True).retrieve(query, k=10)
        ]
        retrieved_map["hybrid_lexical_proxy"] = hybrid_proxy_retrieved

        if include_dense:
            dense_index = DenseIndex(corpus)
            retrieved_map["dense"] = [doc["case_id"] for doc, _ in dense_index.retrieve(query, k=10)]
            hybrid_mmr_index = HybridIndex(corpus, dense_weight=0.65, use_mmr=True)
            retrieved_map["hybrid_mmr"] = [doc["case_id"] for doc, _ in hybrid_mmr_index.retrieve(query, k=10)]

        case_entry: Dict[str, Any] = {
            "case_id": case.case_id,
            "department": case.department,
            "decision_date": case.decision_date,
            "systems": {},
        }

        corpus_map = {d["case_id"]: d for d in corpus}
        for system_name, retrieved_ids in retrieved_map.items():
            metrics = binary_relevance_metrics(retrieved_ids, exact_rel, k_values=(1, 3, 5, 10))
            retrieved_docs = [corpus_map[cid] for cid in retrieved_ids if cid in corpus_map]
            metrics["diversity_at_10"] = intra_list_diversity(retrieved_docs)
            per_system_metrics[system_name].append(metrics)
            case_entry["systems"][system_name] = {
                "retrieved_case_ids": retrieved_ids[:5],
                "metrics": metrics,
            }

        per_case.append(case_entry)

    summary = {system_name: mean_dicts(rows) for system_name, rows in per_system_metrics.items()}
    unavailable = []
    if not include_dense:
        unavailable = ["dense", "hybrid_mmr (requires embeddings)"]

    result = {
        "protocol": "MARS leakage-safe temporal retrieval evaluation",
        "split": split_name,
        "queries_evaluated": len(per_case),
        "summary": summary,
        "unavailable_systems": unavailable,
        "leakage_violations": leakage_violations,
        "per_case": per_case,
    }

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result


def run_retrieval_benchmark() -> Dict[str, Any]:
    """Execute full BEIR / RAGChecker retrieval benchmark on 2023 dataset."""
    print("=" * 80)
    print("RUNNING TIME-SAFE RETRIEVAL BENCHMARK ON 2023 DATASET (640 CASES)")
    print("Literature Standard: Thakur et al. (BEIR NeurIPS 2021) & Ru et al. (NeurIPS 2024)")
    print("=" * 80)

    corpus = load_verified_2023_dataset()
    N = len(corpus)
    print(f"Loaded {N} decision cases. Computing embeddings...")

    docs_text = [
        f"Decision Title: {d['decision_title']}\nDescription: {d['decision_description']}\nRationale: {d['decision_rationale']}\nDepartment: {d['department']}"
        for d in corpus
    ]
    raw_embeddings = get_embeddings(docs_text)
    corpus_embeddings = np.array(raw_embeddings, dtype=np.float32)
    norms = np.linalg.norm(corpus_embeddings, axis=1, keepdims=True)
    corpus_embeddings = corpus_embeddings / np.maximum(1e-9, norms)

    bm25 = BM25Retriever(corpus)
    naive_dense = NaiveDenseRetriever(corpus, corpus_embeddings)
    mars_hybrid = MARSHybridRetriever(corpus, corpus_embeddings)

    query_texts = [item["benchmark_query"] for item in corpus]
    query_embeddings = np.array(get_embeddings(query_texts), dtype=np.float32)
    q_norms = np.linalg.norm(query_embeddings, axis=1, keepdims=True)
    query_embeddings = query_embeddings / np.maximum(1e-9, q_norms)

    def call_bm25(item):
        return bm25.retrieve(item["benchmark_query"], k=5)

    def call_naive_dense(item):
        idx = corpus.index(item)
        return naive_dense.retrieve(query_embeddings[idx], k=5)

    def call_mars(item):
        idx = corpus.index(item)
        return mars_hybrid.retrieve(
            query=item["benchmark_query"],
            query_emb=query_embeddings[idx],
            target_department=item["department"],
            k=5,
            as_of_date=item.get("decision_date"),
        )

    print("\n1/3 Evaluating Baseline R1: BM25 Lexical Retrieval...")
    res_bm25 = evaluate_retriever("Baseline R1: BM25 Lexical", call_bm25, corpus, corpus)

    print("2/3 Evaluating Baseline R2: Naive Dense Vector Retrieval...")
    res_dense = evaluate_retriever("Baseline R2: Naive Dense Vector", call_naive_dense, corpus, corpus)

    print("3/3 Evaluating Proposed MARS: Domain-Filtered Hybrid + MMR + Cross-Dept...")
    res_mars = evaluate_retriever("MARS: Hybrid + MMR + Cross-Dept", call_mars, corpus, corpus)

    results = {
        "benchmark": "MARS 2023 Retrieval Benchmark",
        "dataset_size": N,
        "metrics": [res_bm25, res_dense, res_mars],
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    out_dir = MARS_DIR / "evaluation" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "retrieval_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nResults saved to: {out_path}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="MARS Retrieval Evaluation Engine.")
    parser.add_argument("--mode", default="leakage_safe", choices=["leakage_safe", "beir", "all"])
    parser.add_argument("--split", default="test", choices=["train", "validation", "test"])
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument("--include-dense", action="store_true")
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "evaluation" / "artifacts" / "retrieval_results.json"),
    )
    args = parser.parse_args()

    if args.mode in ("leakage_safe", "all"):
        res = run_retrieval_evaluation(
            split_name=args.split,
            max_queries=args.max_queries,
            include_dense=args.include_dense,
            output=Path(args.output),
        )
        print(json.dumps({
            "output": args.output,
            "queries_evaluated": res["queries_evaluated"],
            "summary": res["summary"],
            "leakage_violations": len(res["leakage_violations"]),
        }, indent=2))

    if args.mode in ("beir", "all"):
        run_retrieval_benchmark()


if __name__ == "__main__":
    main()
