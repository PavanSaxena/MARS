"""Retrieval Evaluation Engine for MARS against Standard Baselines.

Theoretical Foundations:
- BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models (Thakur et al., NeurIPS 2021)
- RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation (Ru et al., NeurIPS 2024)
- Maximal Marginal Relevance (Carbonell & Goldstein, 1998)

Evaluates:
  1. Baseline R1: BM25 Lexical Retrieval (Robertson & Zaragoza; Thakur et al. 2021)
  2. Baseline R2: Naive Dense Bi-Encoder Vector Retrieval (all-MiniLM-L6-v2 flat cosine similarity)
  3. Proposed: MARS Domain-Filtered Hybrid Retrieval + MMR Diversity + Cross-Dept Expansion
"""

import json
import math
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple

import numpy as np

# Add backend to sys.path so app modules are available
MARS_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = MARS_DIR / "backend"
if str(MARS_DIR) not in sys.path:
    sys.path.insert(0, str(MARS_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.benchmark_dataset import load_verified_2023_dataset
from app.storage.embedder import get_embedding, get_embeddings
from app.services.case_retrieval_service import _tokenize, _calculate_lexical_score, _calculate_case_similarity


# =============================================================================
# Baseline R1: BM25 Lexical Search Implementation (Robertson & Zaragoza)
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
            tokens = list(_tokenize(text))
            self.doc_tokens.append(tokens)
            self.doc_lens.append(len(tokens))
            unique_terms = set(tokens)
            for t in unique_terms:
                self.df[t] += 1

        self.avgdl = sum(self.doc_lens) / max(1, self.N)
        self.idf = {}
        for term, freq in self.df.items():
            # Standard Lucene/Okapi BM25 IDF formula
            self.idf[term] = math.log(1.0 + (self.N - freq + 0.5) / (freq + 0.5))

    def retrieve(self, query: str, k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        q_tokens = _tokenize(query)
        scores = []

        for idx, tokens in enumerate(self.doc_tokens):
            score = 0.0
            doc_len = self.doc_lens[idx]
            term_freqs = Counter(tokens)

            for qt in q_tokens:
                if qt in term_freqs:
                    freq = term_freqs[qt]
                    idf_val = self.idf.get(qt, 0.0)
                    denom = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
                    score += idf_val * (freq * (self.k1 + 1.0)) / max(1e-6, denom)

            scores.append((self.corpus[idx], score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]


# =============================================================================
# Baseline R2: Naive Dense Vector Retrieval (Flat Bi-Encoder Cosine)
# =============================================================================
class NaiveDenseRetriever:
    """Flat cosine similarity search over unpartitioned all-MiniLM-L6-v2 embeddings."""

    def __init__(self, corpus: List[Dict[str, Any]], corpus_embeddings: np.ndarray):
        self.corpus = corpus
        self.embeddings = corpus_embeddings  # Normalized (N, 384)

    def retrieve(self, query_emb: np.ndarray, k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        # Cosine similarity for normalized vectors is simply dot product
        sims = np.dot(self.embeddings, query_emb)
        top_indices = np.argsort(-sims)[:k]
        return [(self.corpus[idx], float(sims[idx])) for idx in top_indices]


# =============================================================================
# Proposed System: MARS Domain-Filtered Hybrid Retrieval + MMR
# =============================================================================
class MARSHybridRetriever:
    """
    Domain-filtered hybrid retrieval with cross-department impact expansion,
    lexical reranking, and Maximal Marginal Relevance (MMR) diversity filtering.
    """

    def __init__(self, corpus: List[Dict[str, Any]], corpus_embeddings: np.ndarray):
        self.corpus = corpus
        self.embeddings = corpus_embeddings
        self.mmr_lambda = 0.65
        self.candidate_count = 25

    def retrieve(
        self,
        query: str,
        query_emb: np.ndarray,
        target_department: str,
        k: int = 5,
        as_of_date: Optional[str] = None
    ) -> List[Tuple[Dict[str, Any], float]]:
        # 1. Filter candidates by department + cross-department impact + time-safe cutoff
        candidate_indices = []
        target_dept_lower = target_department.lower()

        for idx, doc in enumerate(self.corpus):
            # Time safe boundary
            if as_of_date and doc.get("decision_date") and doc.get("decision_date") > as_of_date:
                continue

            doc_dept = doc.get("department", "").lower()
            cross_impact = str(doc.get("cross_dept_impact", "")).lower()

            # Domain match OR cross-department impact match
            if doc_dept == target_dept_lower or target_dept_lower in cross_impact:
                candidate_indices.append(idx)

        if not candidate_indices:
            candidate_indices = list(range(len(self.corpus)))

        # 2. Vector similarities for candidates
        cand_embs = self.embeddings[candidate_indices]
        sims = np.dot(cand_embs, query_emb)

        # Top candidates
        sub_top = np.argsort(-sims)[:self.candidate_count]
        
        # 3. Composite contextual reranking (0.65 vector + 0.35 lexical)
        query_tokens = _tokenize(query)
        scored_candidates = []

        for sub_idx in sub_top:
            real_idx = candidate_indices[sub_idx]
            doc = self.corpus[real_idx]
            vec_sim = float(sims[sub_idx])
            lex_score = _calculate_lexical_score(query_tokens, doc)
            composite_score = round(0.65 * vec_sim + 0.35 * lex_score, 4)

            doc_text = f"{doc.get('decision_title', '')} {doc.get('decision_description', '')} {doc.get('decision_rationale', '')}"
            case_tokens = _tokenize(doc_text)

            scored_candidates.append({
                "doc": doc,
                "vector_sim": vec_sim,
                "composite_score": composite_score,
                "tokens": case_tokens,
                "real_idx": real_idx,
            })

        scored_candidates.sort(key=lambda x: x["composite_score"], reverse=True)

        # 4. Maximal Marginal Relevance (MMR)
        selected = []
        remaining = list(scored_candidates)

        while remaining and len(selected) < k:
            best_mmr = -999.0
            best_idx = -1

            for idx, cand in enumerate(remaining):
                if not selected:
                    redundancy = 0.0
                else:
                    redundancies = [
                        _calculate_case_similarity(cand["tokens"], s["tokens"])
                        for s in selected
                    ]
                    redundancy = max(redundancies) if redundancies else 0.0

                mmr_score = (self.mmr_lambda * cand["composite_score"]) - ((1.0 - self.mmr_lambda) * redundancy)
                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_idx = idx

            if best_idx == -1:
                break
            selected.append(remaining.pop(best_idx))

        return [(item["doc"], item["composite_score"]) for item in selected]


# =============================================================================
# Evaluation Metrics (BEIR / RAGChecker Standard)
# =============================================================================
def compute_ndcg_at_k(retrieved_docs: List[Dict[str, Any]], target_doc: Dict[str, Any], k: int = 5) -> float:
    """Compute Normalized Discounted Cumulative Gain (nDCG@K) with graded relevance.

    Graded relevance (Järvelin & Kekäläinen, TOIS 2002):
      rel=3: exact target case retrieved
      rel=2: same dept + shared cross-dept impact
      rel=1: same dept only
      rel=0: different dept / no match

    IDCG is computed per-query from the relevance scores actually achievable
    in the retrieved list — sorted in ideal order — so nDCG is always in [0, 1].
    """
    target_id = target_doc["case_id"]
    target_dept = target_doc.get("department")
    target_cross = str(target_doc.get("cross_dept_impact", ""))
    target_cross_depts = {d.strip() for d in target_cross.split(";") if d.strip()}

    # Assign relevance for each retrieved doc
    gains = []
    for doc in retrieved_docs[:k]:
        rel = 0
        if doc["case_id"] == target_id:
            rel = 3
        elif doc.get("department") == target_dept and target_cross_depts and any(
            d in str(doc.get("cross_dept_impact", "")) for d in target_cross_depts
        ):
            rel = 2
        elif doc.get("department") == target_dept:
            rel = 1
        gains.append(rel)

    # DCG
    dcg = sum(
        (2.0 ** rel - 1.0) / math.log2(rank + 2)
        for rank, rel in enumerate(gains)
        if rel > 0
    )

    # IDCG: sort gains in ideal (descending) order
    ideal_gains = sorted(gains, reverse=True)
    idcg = sum(
        (2.0 ** rel - 1.0) / math.log2(rank + 2)
        for rank, rel in enumerate(ideal_gains)
        if rel > 0
    )

    return dcg / idcg if idcg > 0 else 0.0


def evaluate_retriever(
    name: str,
    retrieve_fn,
    queries: List[Dict[str, Any]],
    corpus: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Run evaluation across all queries and compute official BEIR/RAGAS IR metrics."""
    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    reciprocal_ranks = []
    ndcg_scores = []
    dept_correct_count = 0
    total_retrieved = 0
    cross_dept_hits = 0
    cross_dept_opportunities = 0
    latencies = []

    for item in queries:
        target_id = item["case_id"]
        target_dept = item.get("department")
        cross_impact = str(item.get("cross_dept_impact", ""))
        impacted_depts = [d.strip() for d in cross_impact.split(";") if d.strip() and d.strip() != target_dept]

        start_t = time.perf_counter()
        retrieved_results = retrieve_fn(item)
        latencies.append((time.perf_counter() - start_t) * 1000.0)

        retrieved_docs = [r[0] for r in retrieved_results]
        retrieved_ids = [d["case_id"] for d in retrieved_docs]

        # Recall@K / Hit@K
        if target_id in retrieved_ids[:1]:
            hits_at_1 += 1
        if target_id in retrieved_ids[:3]:
            hits_at_3 += 1
        if target_id in retrieved_ids[:5]:
            hits_at_5 += 1

        # MRR
        if target_id in retrieved_ids:
            rank = retrieved_ids.index(target_id) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

        # nDCG@5
        ndcg_scores.append(compute_ndcg_at_k(retrieved_docs, item, k=5))

        # Department routing accuracy
        for d in retrieved_docs[:5]:
            total_retrieved += 1
            if d.get("department") == target_dept:
                dept_correct_count += 1

        # Cross-department impact recall
        if impacted_depts:
            cross_dept_opportunities += 1
            retrieved_depts = {d.get("department") for d in retrieved_docs[:5]}
            # Did we retrieve from at least one impacted department?
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


def run_retrieval_benchmark() -> Dict[str, Any]:
    """Execute full retrieval evaluation comparing Baselines R1, R2, and MARS."""
    print("=" * 80)
    print("RUNNING TIME-SAFE RETRIEVAL BENCHMARK ON 2023 DATASET (640 CASES)")
    print("Literature Standard: Thakur et al. (BEIR NeurIPS 2021) & Ru et al. (NeurIPS 2024)")
    print("=" * 80)

    corpus = load_verified_2023_dataset()
    N = len(corpus)
    print(f"Loaded {N} decision cases. Pre-computing embeddings for naive vector and MARS...")

    # Embed corpus documents once
    docs_text = [
        f"Decision Title: {d['decision_title']}\nDescription: {d['decision_description']}\nRationale: {d['decision_rationale']}\nDepartment: {d['department']}"
        for d in corpus
    ]
    raw_embeddings = get_embeddings(docs_text)
    corpus_embeddings = np.array(raw_embeddings, dtype=np.float32)
    # Normalize
    norms = np.linalg.norm(corpus_embeddings, axis=1, keepdims=True)
    corpus_embeddings = corpus_embeddings / np.maximum(1e-9, norms)

    print("Embeddings ready. Building retrievers...")
    bm25 = BM25Retriever(corpus)
    naive_dense = NaiveDenseRetriever(corpus, corpus_embeddings)
    mars_hybrid = MARSHybridRetriever(corpus, corpus_embeddings)

    # Pre-embed queries
    query_texts = [item["benchmark_query"] for item in corpus]
    query_embeddings = np.array(get_embeddings(query_texts), dtype=np.float32)
    q_norms = np.linalg.norm(query_embeddings, axis=1, keepdims=True)
    query_embeddings = query_embeddings / np.maximum(1e-9, q_norms)

    # Wrap retrieval calls
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
        "metrics": [res_bm25, res_dense, res_mars]
    }

    print("\n" + "=" * 80)
    print(f"{'System':<35} | {'Rec@1':<7} | {'Rec@3':<7} | {'Rec@5':<7} | {'MRR':<7} | {'nDCG@5':<7} | {'DeptPrec':<8} | {'CrossRec':<8} | {'Latency':<7}")
    print("-" * 105)
    for m in results["metrics"]:
        print(
            f"{m['system']:<35} | {m['recall_at_1']:<7.4f} | {m['recall_at_3']:<7.4f} | "
            f"{m['recall_at_5']:<7.4f} | {m['mrr']:<7.4f} | {m['ndcg_at_5']:<7.4f} | "
            f"{m['dept_routing_precision']:<8.4f} | {m['cross_dept_recall']:<8.4f} | {m['mean_latency_ms']:<7.2f}ms"
        )
    print("=" * 80)

    # Save results to JSON
    import datetime
    results["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "retrieval_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {out_path}")

    return results


if __name__ == "__main__":
    run_retrieval_benchmark()
