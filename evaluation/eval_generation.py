"""Generation Evaluation Engine for MARS vs Baseline LLM Systems.

Theoretical Foundations:
- G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment (Liu et al., EMNLP 2023)
  → CoT rubric-based scoring on 1-5 Likert scale using a frontier reasoning judge
- RAGAS: Automated Evaluation of Retrieval Augmented Generation (Es et al., EACL 2024)
  → Faithfulness, Answer Relevancy, and empirical precedent grounding
- Deterministic NLP Metrics:
  → ROUGE-1, ROUGE-2, ROUGE-L (Lin, 2004) n-gram overlap with real-world observed outcomes
  → Semantic Similarity (Reimers & Gurevych, EMNLP 2019) via all-MiniLM-L6-v2 embeddings
  → Empirical Precedent Citation Precision & Validity against the 640-case verified corpus

Systems Evaluated (40-case stratified sample from verified 2023 dataset):
  G1: Zero-Shot LLM  — Local Ollama Qwen 2.5 3B, no retrieval
  G2: Naive RAG      — Top-5 dense retrieval + single LLM prompt
  MARS               — Full multi-agent pipeline (router → dept agents → aggregator)

Dual Evaluation Setup:
  1. Generator: Local Ollama Qwen 2.5 3B on NVIDIA GeForce RTX 2050 GPU (unlimited, fast)
  2. Judge: Groq llama-3.3-70b-versatile (32K context, free tier, ~800 tok/s, 7K TPM)
  3. Deterministic NLP Engine: ROUGE-1/2/L, Embedding Cosine Similarity, Citation Verification
"""

import datetime
import json
import logging
import os
import re
import sys
import time
import warnings
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Suppress noisy library logs & progress bars
warnings.filterwarnings("ignore")
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

logging.basicConfig(level=logging.WARNING)
for _log_name in [
    "app.retrieval",
    "mcp",
    "mcp.server",
    "mcp.server.lowlevel.server",
    "huggingface_hub",
    "sentence_transformers",
    "transformers",
    "httpx",
    "httpcore",
    "langchain",
    "langchain_core",
]:
    logging.getLogger(_log_name).setLevel(logging.WARNING)

import numpy as np
from rouge_score import rouge_scorer
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
MARS_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = MARS_DIR / "backend"
if str(MARS_DIR) not in sys.path:
    sys.path.insert(0, str(MARS_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.benchmark_dataset import (
    get_stratified_generation_sample,
    load_verified_2023_dataset,
)

# ---------------------------------------------------------------------------
# Environment & API Setup
# ---------------------------------------------------------------------------
_env_path = BACKEND_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line.startswith("#") or "=" not in _line:
            continue
        _key, _val = _line.split("=", 1)
        _key = _key.strip()
        _val = _val.strip().strip("\"'")
        if _key and _val and not os.environ.get(_key):
            os.environ[_key] = _val

if os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

GENERATION_MODEL = "ollama:qwen2.5:3b"
FRONTIER_JUDGE_MODEL = "qwen/qwen3.8-27b"  # Groq — 27B, free tier, confirmed JSON output

_gen_llm_cache: Dict[str, Any] = {}
_judge_llm_cache: Dict[str, Any] = {}

# Pre-initialise ROUGE scorer & sentence encoder
rouge = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
encoder = SentenceTransformer("all-MiniLM-L6-v2")


def _get_gen_llm(model_id: str = GENERATION_MODEL):
    """Return local generation LLM (Ollama)."""
    if model_id not in _gen_llm_cache:
        from langchain.chat_models import init_chat_model
        kwargs = {}
        if model_id.startswith("ollama:"):
            kwargs["num_ctx"] = 8192
        _gen_llm_cache[model_id] = init_chat_model(model_id, max_retries=3, **kwargs)
    return _gen_llm_cache[model_id]


def _get_judge_llm(model_id: str = FRONTIER_JUDGE_MODEL):
    """Return frontier judge LLM (Groq llama-3.3-70b via OpenAI-compatible API)."""
    if model_id not in _judge_llm_cache:
        from langchain_openai import ChatOpenAI
        _judge_llm_cache[model_id] = ChatOpenAI(
            model=model_id,
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ.get("GROQ_API_KEY", ""),
            max_retries=6,
            temperature=0.0,
        )
    return _judge_llm_cache[model_id]


def _normalize_content(content: Any) -> str:
    """Normalize LLM response to a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", str(item)))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


# ---------------------------------------------------------------------------
# Baseline G1: Zero-Shot LLM
# ---------------------------------------------------------------------------
class ZeroShotLLMSystem:
    """Baseline G1: No retrieval. Direct prompt to LLM (Robertson & Zaragoza 2009; Liu et al. 2023)."""

    NAME = "Baseline G1: Zero-Shot LLM"

    def run(self, case: Dict[str, Any]) -> str:
        prompt = (
            "You are a corporate decision advisor. "
            "Provide a structured recommendation for the following business decision.\n\n"
            f"Department: {case.get('department', 'Unknown')}\n"
            f"Decision Title: {case.get('decision_title', '')}\n"
            f"Description: {case.get('decision_description', '')}\n"
            f"Context: {case.get('situation_context', '')}\n\n"
            "Provide:\n"
            "1. Recommended actions (2-3 specific steps)\n"
            "2. Key risks to consider\n"
            "3. Cross-departmental impacts\n"
            "Keep your response concise and actionable."
        )
        llm = _get_gen_llm(GENERATION_MODEL)
        resp = llm.invoke(prompt)
        return _normalize_content(getattr(resp, "content", str(resp))).strip()


# ---------------------------------------------------------------------------
# Baseline G2: Naive RAG
# ---------------------------------------------------------------------------
class NaiveRAGSystem:
    """Baseline G2: Top-5 dense retrieval + single LLM prompt (Lewis et al., NeurIPS 2020)."""

    NAME = "Baseline G2: Naive RAG"

    def __init__(self, corpus: List[Dict[str, Any]], corpus_embeddings: np.ndarray):
        self.corpus = corpus
        self.corpus_embeddings = corpus_embeddings

    def _retrieve(self, case: Dict[str, Any], k: int = 5) -> List[Dict[str, Any]]:
        query = (
            f"Decision Title: {case.get('decision_title', '')} "
            f"Description: {case.get('decision_description', '')} "
            f"Department: {case.get('department', '')}"
        )
        q_emb = encoder.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
        sims = self.corpus_embeddings @ q_emb
        top_k = np.argsort(sims)[::-1][:k]
        return [self.corpus[i] for i in top_k]

    def run(self, case: Dict[str, Any]) -> str:
        retrieved = self._retrieve(case, k=5)
        blocks = []
        for i, doc in enumerate(retrieved, 1):
            blocks.append(
                f"[Case {i} - ID: {doc.get('case_id', '')}] {doc.get('decision_title', '')} ({doc.get('department', '')})\n"
                f"Outcome: {doc.get('outcome_label', 'unknown')}\n"
                f"Rationale: {doc.get('decision_rationale', '')}"
            )
        context_str = "\n\n".join(blocks)

        prompt = (
            "You are a corporate decision advisor. "
            "Use the following precedent cases to inform your recommendation.\n\n"
            f"=== PRECEDENT CASES ===\n{context_str}\n\n"
            f"=== CURRENT DECISION ===\n"
            f"Department: {case.get('department', 'Unknown')}\n"
            f"Decision Title: {case.get('decision_title', '')}\n"
            f"Description: {case.get('decision_description', '')}\n"
            f"Context: {case.get('situation_context', '')}\n\n"
            "Provide:\n"
            "1. Recommended actions (grounded in the precedent cases)\n"
            "2. Key risks (citing relevant precedent cases)\n"
            "3. Cross-departmental impacts\n"
            "Keep your response concise and actionable."
        )
        llm = _get_gen_llm(GENERATION_MODEL)
        resp = llm.invoke(prompt)
        return _normalize_content(getattr(resp, "content", str(resp))).strip()


# ---------------------------------------------------------------------------
# MARS System (full pipeline)
# ---------------------------------------------------------------------------
class MARSSystem:
    """MARS: Multi-Agent Retrieval System — full graph pipeline."""

    NAME = "MARS: Multi-Agent Hybrid + MMR + Cross-Dept"

    def run(self, case: Dict[str, Any]) -> str:
        from app.agents.master_agent import run_graph

        user_input = (
            f"Department: {case.get('department', '')}\n"
            f"Decision: {case.get('decision_title', '')}\n"
            f"Description: {case.get('decision_description', '')}\n"
            f"Context: {case.get('situation_context', '')}"
        )

        for attempt in range(2):
            try:
                result = run_graph(
                    user_input=user_input,
                    thread_id=f"dual_eval_{case.get('case_id', 'default')}_{attempt}",
                    model=GENERATION_MODEL,
                )
                if isinstance(result, tuple):
                    text = str(result[0])
                elif isinstance(result, dict):
                    text = result.get("output", result.get("response", str(result)))
                else:
                    text = str(result)
                return _normalize_content(text).strip()
            except Exception as e:
                print(f"    [MARS error] {e}")
                if attempt == 0:
                    time.sleep(2)
                else:
                    return ""
        return ""


# ---------------------------------------------------------------------------
# Deterministic Evaluation Engine (Objective, Zero-Bias)
# ---------------------------------------------------------------------------
def calculate_deterministic_metrics(
    response: str,
    case: Dict[str, Any],
    valid_case_ids: Set[str],
) -> Dict[str, Any]:
    """Calculate mathematically verifiable NLP and grounding metrics."""
    if not response or len(response.strip()) < 10:
        return {
            "citation_count": 0,
            "valid_citations_count": 0,
            "citation_validity_rate": 0.0,
            "semantic_similarity": 0.0,
            "rouge1_f1": 0.0,
            "rouge2_f1": 0.0,
            "rougeL_f1": 0.0,
        }

    # 1. Citation Precision & Recall (detects hallucinated case numbers)
    raw_citations = re.findall(r"AAPL-\d{4}Q[1-4]-\d{4}", response)
    unique_citations = set(raw_citations)
    valid_cited = [cid for cid in unique_citations if cid in valid_case_ids]

    citation_count = len(unique_citations)
    valid_count = len(valid_cited)
    validity_rate = round(valid_count / citation_count, 4) if citation_count > 0 else 0.0

    # 2. ROUGE Scores against ground-truth SEC observation excerpt
    reference_text = str(case.get("observation_excerpt", "")).strip()
    r_scores = rouge.score(reference_text, response)
    rouge1_f1 = round(float(r_scores["rouge1"].fmeasure), 4)
    rouge2_f1 = round(float(r_scores["rouge2"].fmeasure), 4)
    rougeL_f1 = round(float(r_scores["rougeL"].fmeasure), 4)

    # 3. Semantic Cosine Similarity (via sentence-transformer embedding)
    resp_emb = encoder.encode(response[:3000], normalize_embeddings=True)
    ref_emb = encoder.encode(reference_text, normalize_embeddings=True)
    semantic_similarity = round(float(resp_emb @ ref_emb), 4)

    return {
        "citation_count": citation_count,
        "valid_citations_count": valid_count,
        "citation_validity_rate": validity_rate,
        "semantic_similarity": semantic_similarity,
        "rouge1_f1": rouge1_f1,
        "rouge2_f1": rouge2_f1,
        "rougeL_f1": rougeL_f1,
    }


# ---------------------------------------------------------------------------
# Frontier LLM G-Eval Judge (Gemini 3.8 Flash with Chain-of-Thought)
# ---------------------------------------------------------------------------
GEVAL_COT_RUBRIC = """/no_think
You are an expert corporate executive and senior auditor evaluating an AI decision-support system.
Compare the following AI Recommendation against the Ground-Truth Historical Record from Apple Inc.'s 2023 SEC filings.

=== REFERENCE CASE (Ground Truth from SEC Filings) ===
Department: {department}
Decision Title: {decision_title}
Validated Real-World Outcome: {outcome_label}
Outcome Observation Excerpt: {outcome_excerpt}
Conflicting Perspectives & Tensions: {conflicting_perspectives}
Cross-Department Impact: {cross_dept_impact}

=== AI RECOMMENDATION TO EVALUATE ===
{response}

=== EVALUATION INSTRUCTIONS ===
1. In "critique", write a 2-3 sentence rigorous evaluation assessing:
   - Does the advice align with what Apple actually executed in reality?
   - Did the system acknowledge cross-department trade-offs and conflicting priorities?
   - Are the claims grounded in concrete historical precedent cases, or are they ungrounded assertions?
   - Are downstream operational, legal, and financial risks proactively flagged?

2. Assign scores on a 1-5 integer scale for each of the 4 dimensions:
   - action_alignment (1-5): 5 = Highly aligned with verified real-world outcome; 3 = Partially aligned; 1 = Contradicts outcome or recommends opposite strategy.
   - conflict_awareness (1-5): 5 = Explicitly identifies and navigates competing departmental tensions; 3 = Mentions broad trade-offs; 1 = Ignores all conflicts.
   - factual_grounding (1-5): 5 = Grounded in specific historical precedent cases and verifiable facts; 3 = Generic business logic; 1 = Complete hallucination / fabricated claims.
   - risk_foresight (1-5): 5 = Comprehensively flags cross-departmental downstream risks; 3 = Flags standard risks; 1 = Fails to flag obvious risks.

OUTPUT FORMAT: Return ONLY valid JSON in this exact schema:
{{
  "critique": "<2-3 sentence rigorous evaluation>",
  "action_alignment": <int 1-5>,
  "conflict_awareness": <int 1-5>,
  "factual_grounding": <int 1-5>,
  "risk_foresight": <int 1-5>
}}"""


def frontier_geval_score(case: Dict[str, Any], response: str) -> Dict[str, Any]:
    """Score response using Groq llama-3.3-70b with Chain-of-Thought rubric."""
    if not response or len(response.strip()) < 20:
        return {
            "critique": "Response was empty or trivially short.",
            "action_alignment": 1.0,
            "conflict_awareness": 1.0,
            "factual_grounding": 1.0,
            "risk_foresight": 1.0,
            "composite": 1.0,
        }

    prompt = GEVAL_COT_RUBRIC.format(
        department=case.get("department", ""),
        decision_title=case.get("decision_title", ""),
        outcome_label=case.get("outcome_label", "unknown"),
        outcome_excerpt=str(case.get("observation_excerpt", "")).strip(),
        conflicting_perspectives=str(case.get("conflicting_perspectives", "")).strip(),
        cross_dept_impact=str(case.get("cross_dept_impact", "")).strip(),
        response=response.strip(),
    )

    judge = _get_judge_llm(FRONTIER_JUDGE_MODEL)

    for attempt in range(5):
        try:
            resp = judge.invoke(prompt)
            raw = _normalize_content(getattr(resp, "content", str(resp))).strip()

            # Parse JSON
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                data = json.loads(match.group(0))
                scores = {
                    "critique": str(data.get("critique", "")).strip(),
                    "action_alignment": float(data.get("action_alignment", 1)),
                    "conflict_awareness": float(data.get("conflict_awareness", 1)),
                    "factual_grounding": float(data.get("factual_grounding", 1)),
                    "risk_foresight": float(data.get("risk_foresight", 1)),
                }
                scores["composite"] = round(
                    float(np.mean([scores["action_alignment"], scores["conflict_awareness"],
                                    scores["factual_grounding"], scores["risk_foresight"]])),
                    3,
                )
                return scores
            else:
                print(f"\n    [Judge warning] Attempt {attempt+1}: no JSON in response, retrying...")
                time.sleep(10)
        except Exception as e:
            err_str = str(e)
            # Groq 429 rate-limit: back off hard
            if "429" in err_str or "rate_limit" in err_str.lower() or "too many" in err_str.lower():
                wait = 30 * (attempt + 1)
                print(f"\n    [Groq 429 — rate limit] Attempt {attempt+1}: waiting {wait}s...")
                time.sleep(wait)
            else:
                wait = 8 * (attempt + 1)
                print(f"\n    [Judge warning] Attempt {attempt+1}: {err_str[:100]} — waiting {wait}s...")
                time.sleep(wait)

    return {
        "critique": "Judge evaluation failed after 5 attempts.",
        "action_alignment": 1.0,
        "conflict_awareness": 1.0,
        "factual_grounding": 1.0,
        "risk_foresight": 1.0,
        "composite": 1.0,
    }


# ---------------------------------------------------------------------------
# Main Dual-Benchmark Runner
# ---------------------------------------------------------------------------
def run_dual_benchmark(sample_size: int = 40) -> Dict[str, Any]:
    """Execute complete generation evaluation with deterministic & frontier LLM metrics."""
    print("=" * 85)
    print("RUNNING MARS DUAL GENERATION BENCHMARK (DETERMINISTIC + FRONTIER G-EVAL)")
    print(f"Generator Model:    {GENERATION_MODEL} (Local RTX 2050 GPU)")
    print(f"Frontier Judge:     {FRONTIER_JUDGE_MODEL} (Groq Cloud, 27B, free tier)")
    print("Deterministic NLP:  ROUGE-1/2/L + Embedding Semantic Sim + Precedent Citation Validity")
    print("=" * 85)

    sample = get_stratified_generation_sample(sample_size=sample_size)
    actual_n = len(sample)
    dept_dist = Counter(c["department"] for c in sample)
    outcome_dist = Counter(c.get("outcome_label", "unknown") for c in sample)
    print(f"Loaded {actual_n} stratified cases  Dept: {dict(dept_dist)}  Outcome: {dict(outcome_dist)}")

    # Load corpus & build embeddings for Naive RAG + Citation verification set
    print("\nPre-computing corpus embeddings and indexing verified case IDs...")
    corpus = load_verified_2023_dataset()
    valid_case_ids: Set[str] = {c.get("case_id", "") for c in corpus if c.get("case_id")}
    docs_text = [
        f"Decision Title: {d['decision_title']} Description: {d['decision_description']} "
        f"Rationale: {d['decision_rationale']} Department: {d['department']}"
        for d in corpus
    ]
    corpus_embeddings = encoder.encode(
        docs_text, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
    )
    print(f"  Corpus: {len(corpus)} docs | Valid Case IDs: {len(valid_case_ids)}")

    # Initialize systems
    g1 = ZeroShotLLMSystem()
    g2 = NaiveRAGSystem(corpus=corpus, corpus_embeddings=corpus_embeddings)
    mars = MARSSystem()
    systems = [g1, g2, mars]

    system_results: Dict[str, List[Dict[str, Any]]] = {s.NAME: [] for s in systems}

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    partial_path = out_dir / "generation_results_dual_partial.json"

    # Resume checkpoint if available
    completed_case_ids: Set[str] = set()
    if partial_path.exists():
        try:
            with open(partial_path, "r") as f:
                ckpt = json.load(f)
                if "systems" in ckpt:
                    for sys_name, agg in ckpt["systems"].items():
                        if sys_name in system_results and "per_case" in agg:
                            system_results[sys_name] = agg["per_case"]
                    if system_results.get(systems[0].NAME):
                        completed_case_ids = {s["case_id"] for s in system_results[systems[0].NAME]}
                        print(f"Resuming from checkpoint: {len(completed_case_ids)} cases already completed.")
        except Exception as e:
            print(f"Checkpoint read skipped: {e}")

    print(f"\nRunning {actual_n} cases across {len(systems)} systems...\n")

    for case_idx, case in enumerate(sample):
        case_id = case.get("case_id", f"case_{case_idx}")
        dept = case.get("department", "?")

        if case_id in completed_case_ids:
            print(f"[{case_idx+1:02d}/{actual_n}] {case_id} | {dept} (already completed, skipping)")
            continue

        print(f"[{case_idx+1:02d}/{actual_n}] {case_id} | {dept}")

        for sys_obj in systems:
            print(f"  → {sys_obj.NAME} ... ", end="", flush=True)
            t0 = time.perf_counter()
            response = sys_obj.run(case)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            # 1. Deterministic Metrics
            det_metrics = calculate_deterministic_metrics(response, case, valid_case_ids)

            # 2. Frontier G-Eval Judge
            print(f"judging with Groq {FRONTIER_JUDGE_MODEL}... ", end="", flush=True)
            geval_res = frontier_geval_score(case, response)
            time.sleep(20)  # Groq free tier: 7K TPM — 20s gap keeps us safely under limit

            # Consolidated record
            record = {
                "case_id": case_id,
                "department": dept,
                "outcome_label": case.get("outcome_label", "unknown"),
                "latency_ms": round(latency_ms, 1),
                "response_words": len(response.split()),
                "response": response,
                "critique": geval_res.get("critique", ""),
                "action_alignment": geval_res["action_alignment"],
                "conflict_awareness": geval_res["conflict_awareness"],
                "factual_grounding": geval_res["factual_grounding"],
                "risk_foresight": geval_res["risk_foresight"],
                "composite": geval_res["composite"],
                **det_metrics,
            }
            system_results[sys_obj.NAME].append(record)
            print(f"composite={record['composite']:.2f} | FactGround={record['factual_grounding']:.0f} | Sim={record['semantic_similarity']:.2f}")

        # Save checkpoint after each case
        checkpoint_agg: Dict[str, Any] = {}
        score_keys = [
            "action_alignment", "conflict_awareness", "factual_grounding", "risk_foresight",
            "composite", "semantic_similarity", "rougeL_f1", "citation_count",
            "valid_citations_count", "citation_validity_rate", "latency_ms", "response_words"
        ]
        for sys_name, case_scores in system_results.items():
            if case_scores:
                agg = {k: round(float(np.mean([s[k] for s in case_scores])), 4) for k in score_keys}
                agg["n"] = len(case_scores)
                agg["per_case"] = case_scores
                checkpoint_agg[sys_name] = agg

        with open(partial_path, "w") as f:
            json.dump({
                "benchmark": "MARS 2023 Dual Benchmark (Partial)",
                "sample_size": actual_n,
                "completed": len(system_results[systems[0].NAME]),
                "generator_model": GENERATION_MODEL,
                "judge_model": FRONTIER_JUDGE_MODEL,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "systems": checkpoint_agg,
            }, f, indent=2, default=str)

    # Final Aggregation
    final_agg: Dict[str, Any] = {}
    for sys_name, case_scores in system_results.items():
        agg = {k: round(float(np.mean([s[k] for s in case_scores])), 4) for k in score_keys}
        agg["n"] = len(case_scores)
        agg["per_case"] = case_scores
        final_agg[sys_name] = agg

    # Print summary tables
    print("\n" + "=" * 105)
    print(f"FRONTIER G-EVAL JUDGE (Groq {FRONTIER_JUDGE_MODEL}, Liu et al., EMNLP 2023)")
    print("=" * 105)
    header1 = f"{'System':<42} | {'ActAlign':>8} | {'ConflAware':>10} | {'FactGround':>10} | {'RiskFore':>8} | {'Composite':>9}"
    print(header1)
    print("-" * 105)
    for sys_name, agg in final_agg.items():
        print(
            f"{sys_name:<42} | {agg['action_alignment']:>8.3f} | {agg['conflict_awareness']:>10.3f} | "
            f"{agg['factual_grounding']:>10.3f} | {agg['risk_foresight']:>8.3f} | {agg['composite']:>9.3f}"
        )

    print("\n" + "=" * 105)
    print("DETERMINISTIC NLP & CITATION GROUNDING METRICS (Lin 2004; Reimers & Gurevych 2019)")
    print("=" * 105)
    header2 = f"{'System':<42} | {'SemanticSim':>11} | {'ROUGE-L':>8} | {'Citations':>9} | {'ValidCites':>10} | {'CiteValid%':>10}"
    print(header2)
    print("-" * 105)
    for sys_name, agg in final_agg.items():
        print(
            f"{sys_name:<42} | {agg['semantic_similarity']:>11.3f} | {agg['rougeL_f1']:>8.3f} | "
            f"{agg['citation_count']:>9.1f} | {agg['valid_citations_count']:>10.1f} | {agg['citation_validity_rate']*100:>9.1f}%"
        )
    print("=" * 105)

    results = {
        "benchmark": "MARS 2023 Dual Benchmark (Empirical + Frontier)",
        "sample_size": actual_n,
        "generator_model": GENERATION_MODEL,
        "judge_model": FRONTIER_JUDGE_MODEL,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dept_distribution": dict(dept_dist),
        "outcome_distribution": dict(outcome_dist),
        "systems": final_agg,
    }

    final_path = out_dir / "generation_results_dual.json"
    with open(final_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFinal results saved to: {final_path}")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MARS Dual Generation Benchmark")
    parser.add_argument("--sample-size", type=int, default=40)
    args = parser.parse_args()
    run_dual_benchmark(sample_size=args.sample_size)
