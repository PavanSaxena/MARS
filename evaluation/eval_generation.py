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

from evaluation.dataset import (
    get_stratified_generation_sample,
    load_verified_dataset,
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


def _get_groq_key() -> str:
    """Return the Groq API key from the environment (set via backend/.env)."""
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set. Please add it to backend/.env.")
    return key

# Pre-initialise ROUGE scorer & sentence encoder
rouge = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
encoder = SentenceTransformer("all-MiniLM-L6-v2")


def _get_gen_llm(model_id: str = GENERATION_MODEL):
    """Return generation LLM (Ollama, Groq, or OpenRouter)."""
    if model_id not in _gen_llm_cache:
        provider = model_id.split(":", 1)[0] if ":" in model_id else ""
        model_name = model_id.split(":", 1)[1] if ":" in model_id else model_id

        if provider == "openrouter":
            from langchain_openai import ChatOpenAI
            api_key = os.environ.get("OPENROUTER_API_KEY", "")
            _gen_llm_cache[model_id] = ChatOpenAI(
                model=model_name,
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                max_retries=5,
                temperature=0.2,
            )
        elif provider == "groq":
            from langchain_openai import ChatOpenAI
            api_key = _get_groq_key()
            _gen_llm_cache[model_id] = ChatOpenAI(
                model=model_name,
                base_url="https://api.groq.com/openai/v1",
                api_key=api_key,
                max_retries=5,
                temperature=0.2,
                max_tokens=600,
            )
        elif provider == "ollama":
            from langchain.chat_models import init_chat_model
            _gen_llm_cache[model_id] = init_chat_model(model_id, num_ctx=8192, max_retries=3)
        else:
            from langchain.chat_models import init_chat_model
            _gen_llm_cache[model_id] = init_chat_model(model_id, max_retries=3)
    return _gen_llm_cache[model_id]


def _get_judge_llm(model_id: str = FRONTIER_JUDGE_MODEL):
    """Return frontier judge LLM (Groq or OpenRouter via OpenAI-compatible API)."""
    if model_id not in _judge_llm_cache:
        from langchain_openai import ChatOpenAI
        provider = model_id.split(":", 1)[0] if ":" in model_id else ""
        model_name = model_id.split(":", 1)[1] if ":" in model_id else model_id

        if provider == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
            api_key = os.environ.get("OPENROUTER_API_KEY", "")
        elif provider == "groq" or not provider:
            base_url = "https://api.groq.com/openai/v1"
            api_key = _get_groq_key()
        else:
            base_url = "https://api.groq.com/openai/v1"
            api_key = _get_groq_key()

        _judge_llm_cache[model_id] = ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key=api_key,
            max_retries=6,
            temperature=0.0,
            max_tokens=600,
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


class DailyRateLimitExceeded(Exception):
    """Raised when an API provider's daily quota (TPD) is reached."""
    pass


def _is_daily_rate_limit(err: Any) -> bool:
    s = str(err).lower()
    return (
        "tokens per day" in s
        or "tpd" in s
        or "daily" in s
        or "requests per day" in s
        or "limit 200000" in s
        or "on tokens per day" in s
    )


def _is_invalid_key_error(err: Any) -> bool:
    s = str(err).lower()
    return "401" in s or "invalid api key" in s or "invalid_api_key" in s


def _is_per_minute_rate_limit(err: Any) -> bool:
    s = str(err).lower()
    return (
        ("429" in s or "rate_limit" in s or "too many" in s or "rate limit" in s)
        and not _is_daily_rate_limit(err)
    )


def _extract_retry_wait(err: Any, default: float = 30.0) -> float:
    s = str(err)
    match = re.search(r"try again in (\d+(?:\.\d+)?)\s*(s|m|h)?", s, re.IGNORECASE)
    if match:
        val = float(match.group(1))
        unit = (match.group(2) or "s").lower()
        if unit == "m":
            val *= 60
        elif unit == "h":
            val *= 3600
        return max(val + 2.0, 5.0)
    return default


def _gen_invoke_with_retry(llm: Any, prompt: str, model_id: str = "") -> str:
    """Invoke generator LLM, retrying on TPM/RPM limits, halting on daily limits.
    Never returns default values. Raises DailyRateLimitExceeded on quota exhaustion.
    """
    tpm_attempt = 0
    non_rate_attempts = 0

    while True:
        try:
            resp = llm.invoke(prompt)
            text = _normalize_content(getattr(resp, "content", str(resp))).strip()
            if text and len(text) >= 20:
                return text
            non_rate_attempts += 1
            if non_rate_attempts <= 3:
                time.sleep(5)
                continue
            raise RuntimeError("Generator LLM returned empty response after 3 attempts.")
        except DailyRateLimitExceeded:
            raise
        except Exception as e:
            if _is_daily_rate_limit(e):
                raise DailyRateLimitExceeded(str(e))
            elif _is_invalid_key_error(e):
                raise
            elif _is_per_minute_rate_limit(e):
                wait = _extract_retry_wait(e, default=30.0 + min(tpm_attempt * 15, 60))
                print(f"\n    [Generator TPM Rate Limit] Waiting {wait:.1f}s before retry...\n", flush=True)
                time.sleep(wait)
                tpm_attempt += 1
            else:
                non_rate_attempts += 1
                if non_rate_attempts <= 3:
                    time.sleep(5)
                else:
                    raise



# ---------------------------------------------------------------------------
# Baseline G1: Zero-Shot LLM
# ---------------------------------------------------------------------------
class ZeroShotLLMSystem:
    """Baseline G1: No retrieval. Direct prompt to LLM (Robertson & Zaragoza 2009; Liu et al. 2023)."""

    NAME = "Baseline G1: Zero-Shot LLM"

    def __init__(self, model: str = GENERATION_MODEL):
        self.model = model

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
        llm = _get_gen_llm(self.model)
        return _gen_invoke_with_retry(llm, prompt, self.model)


# ---------------------------------------------------------------------------
# Baseline G2: Naive RAG
# ---------------------------------------------------------------------------
class NaiveRAGSystem:
    """Baseline G2: Top-5 dense retrieval + single LLM prompt (Lewis et al., NeurIPS 2020)."""

    NAME = "Baseline G2: Naive RAG"

    def __init__(self, corpus: List[Dict[str, Any]], corpus_embeddings: np.ndarray, model: str = GENERATION_MODEL):
        self.corpus = corpus
        self.corpus_embeddings = corpus_embeddings
        self.model = model

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
        llm = _get_gen_llm(self.model)
        return _gen_invoke_with_retry(llm, prompt, self.model)


# ---------------------------------------------------------------------------
# Baseline G3: Single-Agent Multi-Persona (Roleplay Council)
# ---------------------------------------------------------------------------
class MultiPersonaSystem:
    """Baseline G3: Multi-Persona Roleplay Council in a Single LLM Prompt (Wang et al. ICLR 2024; Du et al. ICML 2024)."""

    NAME = "Baseline G3: Single-Agent Multi-Persona"

    def __init__(self, model: str = GENERATION_MODEL):
        self.model = model

    def run(self, case: Dict[str, Any]) -> str:
        prompt = (
            "You are an Executive Leadership Committee comprising four department leaders:\n"
            "1. VP of Finance (focus: capital allocation, gross margins, cash flow runway)\n"
            "2. Head of Operations (focus: supply chain continuity, factory throughput, supplier SLAs)\n"
            "3. Chief Technology Officer / R&D (focus: technical feasibility, product roadmap, engineering)\n"
            "4. General Counsel / Legal (focus: regulatory compliance, antitrust, contractual exposure)\n\n"
            "Evaluate the following strategic corporate decision from all four perspectives simultaneously:\n\n"
            f"Primary Department: {case.get('department', 'Unknown')}\n"
            f"Decision Title: {case.get('decision_title', '')}\n"
            f"Description: {case.get('decision_description', '')}\n"
            f"Context: {case.get('situation_context', '')}\n\n"
            "Instructions:\n"
            "Part 1: Departmental Deliberation — Have each of the 4 executives state their department's position, key priorities, and objections.\n"
            "Part 2: Executive Synthesis & Verdict — Reconcile the competing departmental trade-offs into an agreed corporate recommendation, citing key risks and contingency measures.\n"
            "Keep the response structured, rigorous, and actionable."
        )
        llm = _get_gen_llm(self.model)
        return _gen_invoke_with_retry(llm, prompt, self.model)


# ---------------------------------------------------------------------------
# Baseline G4: Hybrid RAG Single-Agent (Advanced RAG)
# ---------------------------------------------------------------------------
class HybridRAGSystem:
    """Baseline G4: Hybrid BM25 + Dense Vector + MMR Diversity in a Single LLM (Thakur et al. NeurIPS 2021; Gao et al. 2023)."""

    NAME = "Baseline G4: Hybrid RAG Single-Agent"

    def __init__(self, corpus: List[Dict[str, Any]], corpus_embeddings: np.ndarray, model: str = GENERATION_MODEL):
        self.corpus = corpus
        self.corpus_embeddings = corpus_embeddings
        self.model = model
        from evaluation.eval_retrieval import MARSHybridRetriever
        self.retriever = MARSHybridRetriever(corpus=corpus, corpus_embeddings=corpus_embeddings)

    def _retrieve(self, case: Dict[str, Any], k: int = 5) -> List[Dict[str, Any]]:
        query = (
            f"Decision Title: {case.get('decision_title', '')} "
            f"Description: {case.get('decision_description', '')} "
            f"Department: {case.get('department', '')}"
        )
        q_emb = encoder.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
        dept = case.get("department", "")
        as_of = case.get("decision_date")
        cross_impact = case.get("cross_department_impact")
        return self.retriever.retrieve(
            query=query,
            query_emb=q_emb,
            target_department=dept,
            k=k,
            as_of_date=as_of,
            cross_dept_impact=cross_impact,
        )

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
            "You are a senior corporate decision advisory intelligence system. "
            "Use the following temporally filtered, cross-departmental precedent cases to ground your recommendation.\n\n"
            f"=== RETRIEVED PRECEDENT CASES (Hybrid BM25 + Dense + MMR Diversity) ===\n{context_str}\n\n"
            f"=== STRATEGIC DECISION UNDER EVALUATION ===\n"
            f"Department: {case.get('department', 'Unknown')}\n"
            f"Decision Title: {case.get('decision_title', '')}\n"
            f"Description: {case.get('decision_description', '')}\n"
            f"Context: {case.get('situation_context', '')}\n\n"
            "Provide:\n"
            "1. Recommended actions (explicitly citing precedent case IDs)\n"
            "2. Critical risks and historical failure modes to guard against\n"
            "3. Cross-departmental operational and compliance implications\n"
            "Keep your response concise, evidence-grounded, and actionable."
        )
        llm = _get_gen_llm(self.model)
        return _gen_invoke_with_retry(llm, prompt, self.model)


# ---------------------------------------------------------------------------
# Baseline G5: Zero-Shot Chain-of-Thought (Wei et al. NeurIPS 2022)
# ---------------------------------------------------------------------------
class ZeroShotCoTSystem:
    """Baseline G5: Zero-Shot Chain-of-Thought (CoT) Prompting (Wei et al. 2022; Kojima et al. 2022)."""

    NAME = "Baseline G5: Zero-Shot CoT"

    def __init__(self, model: str = GENERATION_MODEL):
        self.model = model

    def run(self, case: Dict[str, Any]) -> str:
        prompt = (
            "You are a corporate decision advisor. Analyze the following business dilemma using rigorous step-by-step reasoning.\n\n"
            f"Department: {case.get('department', 'Unknown')}\n"
            f"Decision Title: {case.get('decision_title', '')}\n"
            f"Description: {case.get('decision_description', '')}\n"
            f"Context: {case.get('situation_context', '')}\n\n"
            "Let's think step by step:\n"
            "Step 1: Deconstruct the primary dilemma, strategic objectives, and immediate operational triggers.\n"
            "Step 2: Identify conflicting priorities between different business units (Finance capital, Operations throughput, R&D technical constraints, Legal compliance).\n"
            "Step 3: Evaluate potential risks, vulnerabilities, and negative outcome modes if executed without safeguards.\n"
            "Step 4: Formulate a final structured synthesis with specific recommended actions, risk hedges, and cross-departmental coordination steps."
        )
        llm = _get_gen_llm(self.model)
        return _gen_invoke_with_retry(llm, prompt, self.model)


# ---------------------------------------------------------------------------
# MARS System (full pipeline)
# ---------------------------------------------------------------------------
class MARSSystem:
    """MARS: Multi-Agent Retrieval System — full graph pipeline."""

    NAME = "MARS: Multi-Agent Hybrid + MMR + Cross-Dept"

    def __init__(self, model: str = GENERATION_MODEL):
        self.model = model

    def run(self, case: Dict[str, Any]) -> str:
        from app.agents.master_agent import run_graph

        user_input = (
            f"Evaluate the strategic decision and provide recommendations:\n"
            f"Department: {case.get('department', '')}\n"
            f"Decision: {case.get('decision_title', '')}\n"
            f"Description: {case.get('decision_description', '')}\n"
            f"Context: {case.get('situation_context', '')}"
        )

        tpm_attempt = 0
        non_rate_attempts = 0

        while True:
            try:
                result = run_graph(
                    user_input=user_input,
                    thread_id=f"dual_eval_{case.get('case_id', 'default')}_{tpm_attempt}_{non_rate_attempts}",
                    model=self.model,
                    force_pipeline=True,
                    raise_on_rate_limit=True,
                )
                if isinstance(result, tuple):
                    text = str(result[0])
                elif isinstance(result, dict):
                    text = result.get("output", result.get("response", str(result)))
                else:
                    text = str(result)
                text = _normalize_content(text).strip()

                if "### ⚠️ Provider Rate Limit Reached" in text or "Rate limit reached" in text:
                    if _is_daily_rate_limit(text):
                        raise DailyRateLimitExceeded(text)
                    wait = _extract_retry_wait(text, default=30.0 + min(tpm_attempt * 15, 60))
                    print(f"\n    [MARS TPM Rate Limit in output] Waiting {wait:.1f}s before retry...\n", flush=True)
                    time.sleep(wait)
                    tpm_attempt += 1
                    continue

                if text and len(text) >= 20:
                    return text

                # Empty result — retry
                non_rate_attempts += 1
                if non_rate_attempts <= 3:
                    print(f"    [MARS warning] Empty response (attempt {non_rate_attempts}/3), retrying in 5s...")
                    time.sleep(5)
                    continue
                raise RuntimeError(f"MARS produced empty response after {non_rate_attempts} attempts for case {case.get('case_id')}.")
            except DailyRateLimitExceeded:
                raise
            except Exception as e:
                if _is_daily_rate_limit(e):
                    raise DailyRateLimitExceeded(str(e))
                elif _is_invalid_key_error(e):
                    raise
                elif _is_per_minute_rate_limit(e):
                    wait = _extract_retry_wait(e, default=30.0 + min(tpm_attempt * 15, 60))
                    print(f"\n    [MARS TPM Rate Limit] Waiting {wait:.1f}s before retry...\n", flush=True)
                    time.sleep(wait)
                    tpm_attempt += 1
                else:
                    non_rate_attempts += 1
                    if non_rate_attempts <= 3:
                        print(f"    [MARS error] #{non_rate_attempts}: {str(e)[:100]} — retrying in 5s...")
                        time.sleep(5)
                    else:
                        raise RuntimeError(f"MARS failed on case {case.get('case_id')} after 3 non-rate-limit errors: {e}")



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

    # 1. Citation Precision & Recall (detects hallucinated case numbers, normalizes padding)
    raw_matches = re.findall(r"(AAPL-\d{4}Q[1-4]-)(\d{1,4})", response)
    unique_citations = {f"{prefix}{int(num_str):04d}" for prefix, num_str in raw_matches}
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


def frontier_geval_score(case: Dict[str, Any], response: str, judge_model: str = FRONTIER_JUDGE_MODEL) -> Dict[str, Any]:
    """Score response using frontier LLM with Chain-of-Thought rubric.
    Never returns synthetic default scores in research mode.
    """
    if not response or len(response.strip()) < 20:
        raise ValueError(f"Cannot score empty or trivially short response for case {case.get('case_id')} in research mode.")

    prompt = GEVAL_COT_RUBRIC.format(
        department=case.get("department", ""),
        decision_title=case.get("decision_title", ""),
        outcome_label=case.get("outcome_label", "unknown"),
        outcome_excerpt=str(case.get("observation_excerpt", "")).strip(),
        conflicting_perspectives=str(case.get("conflicting_perspectives", "")).strip(),
        cross_dept_impact=str(case.get("cross_dept_impact", "")).strip(),
        response=response.strip(),
    )

    judge = _get_judge_llm(judge_model)
    tpm_attempt = 0
    parse_failures = 0

    while True:
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
                parse_failures += 1
                if parse_failures >= 10:
                    raise RuntimeError(f"Judge returned non-JSON output after 10 attempts on case {case.get('case_id')}.")
                print(f"\n    [Judge warning] No JSON in response (attempt {parse_failures}/10), retrying in 10s...")
                time.sleep(10)
        except DailyRateLimitExceeded:
            raise
        except Exception as e:
            if _is_daily_rate_limit(e):
                raise DailyRateLimitExceeded(str(e))
            elif _is_invalid_key_error(e):
                raise
            elif _is_per_minute_rate_limit(e):
                wait = _extract_retry_wait(e, default=30.0 + min(tpm_attempt * 15, 60))
                print(f"\n    [Judge TPM Rate Limit] Waiting {wait:.1f}s before retry...\n", flush=True)
                time.sleep(wait)
                tpm_attempt += 1
            else:
                parse_failures += 1
                if parse_failures >= 5:
                    raise RuntimeError(f"Judge failed after 5 non-rate-limit errors on case {case.get('case_id')}: {e}")
                wait = 8 * min(parse_failures, 5)
                print(f"\n    [Judge error] #{parse_failures}: {str(e)[:100]} — waiting {wait}s...")
                time.sleep(wait)




# ---------------------------------------------------------------------------
# Main Dual-Benchmark Runner
# ---------------------------------------------------------------------------
def run_dual_benchmark(
    sample_size: int = 40,
    generator_model: str = GENERATION_MODEL,
    judge_model: str = FRONTIER_JUDGE_MODEL,
) -> Dict[str, Any]:
    """Execute complete generation evaluation with deterministic & frontier LLM metrics."""
    print("=" * 85)
    print("RUNNING MARS DUAL GENERATION BENCHMARK (DETERMINISTIC + FRONTIER G-EVAL)")
    print(f"Generator Model:    {generator_model}")
    print(f"Frontier Judge:     {judge_model}")
    print("Deterministic NLP:  ROUGE-1/2/L + Embedding Semantic Sim + Precedent Citation Validity")
    print("=" * 85)

    sample = get_stratified_generation_sample(sample_size=sample_size)
    actual_n = len(sample)
    dept_dist = Counter(c["department"] for c in sample)
    outcome_dist = Counter(c.get("outcome_label", "unknown") for c in sample)
    print(f"Loaded {actual_n} stratified cases  Dept: {dict(dept_dist)}  Outcome: {dict(outcome_dist)}")

    # Load corpus & build embeddings for Naive RAG + Citation verification set
    print("\nPre-computing corpus embeddings and indexing verified case IDs...")
    corpus = load_verified_dataset()
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
    g1 = ZeroShotLLMSystem(model=generator_model)
    g2 = NaiveRAGSystem(corpus=corpus, corpus_embeddings=corpus_embeddings, model=generator_model)
    mars = MARSSystem(model=generator_model)
    systems = [g1, g2, mars]

    system_results: Dict[str, List[Dict[str, Any]]] = {s.NAME: [] for s in systems}
    score_keys = [
        "action_alignment", "conflict_awareness", "factual_grounding", "risk_foresight",
        "composite", "semantic_similarity", "rougeL_f1", "citation_count",
        "valid_citations_count", "citation_validity_rate", "latency_ms", "response_words"
    ]

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    partial_path = out_dir / "generation_results_dual_partial.json"

    # Resume checkpoint if available and matching model setup
    completed_case_ids: Set[str] = set()
    if partial_path.exists():
        try:
            with open(partial_path, "r") as f:
                ckpt = json.load(f)
                if ckpt.get("generator_model") == generator_model and ckpt.get("judge_model") == judge_model:
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

        case_records: Dict[str, Dict[str, Any]] = {}
        try:
            for sys_obj in systems:
                print(f"  → {sys_obj.NAME} ... ", end="", flush=True)
                t0 = time.perf_counter()
                response = sys_obj.run(case)
                latency_ms = (time.perf_counter() - t0) * 1000.0

                # Pace generator token usage: short sleep between generation calls on Groq
                if "groq" in generator_model.lower() and not isinstance(sys_obj, MARSSystem):
                    time.sleep(8)  # ~8s between G1/G2 generator calls to pace TPM/TPD usage

                # 1. Deterministic Metrics
                det_metrics = calculate_deterministic_metrics(response, case, valid_case_ids)

                # 2. Frontier G-Eval Judge
                print(f"judging with {judge_model}... ", end="", flush=True)
                geval_res = frontier_geval_score(case, response, judge_model=judge_model)
                if "groq" in judge_model.lower():
                    time.sleep(20)  # Groq free tier: 7K TPM — 20s gap keeps us safely under limit
                else:
                    time.sleep(3)

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
                case_records[sys_obj.NAME] = record
                print(f"composite={record['composite']:.2f} | FactGround={record['factual_grounding']:.0f} | Sim={record['semantic_similarity']:.2f}")

            # All 3 systems succeeded for this case — append to results
            for sys_name, rec in case_records.items():
                system_results[sys_name].append(rec)

            # Save checkpoint after each case
            checkpoint_agg: Dict[str, Any] = {}
            for sys_name, case_scores in system_results.items():
                if case_scores:
                    agg = {k: round(float(np.mean([s[k] for s in case_scores])), 4) for k in score_keys}
                    agg["n"] = len(case_scores)
                    agg["per_case"] = case_scores
                    checkpoint_agg[sys_name] = agg

            with open(partial_path, "w") as f:
                json.dump({
                    "benchmark": "MARS Multi-Year Dual Benchmark (Partial)",
                    "sample_size": actual_n,
                    "completed": len(system_results[systems[0].NAME]),
                    "generator_model": generator_model,
                    "judge_model": judge_model,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "systems": checkpoint_agg,
                }, f, indent=2, default=str)

        except DailyRateLimitExceeded as dre:
            print("\n" + "=" * 90)
            print("🚨 DAILY RATE LIMIT (TPD) REACHED — HALTING BENCHMARK")
            print(f"Details: {dre}")
            print("Research Data Integrity: ZERO default scores recorded. No corrupted data.")
            print(f"Completed and verified cases: {len(system_results[systems[0].NAME])}/{actual_n}")
            print("Checkpoint safely preserved. Resuming later will continue directly from this case.")
            print("=" * 90)
            checkpoint_agg = {}
            for sys_name, case_scores in system_results.items():
                if case_scores:
                    agg = {k: round(float(np.mean([s[k] for s in case_scores])), 4) for k in score_keys}
                    agg["n"] = len(case_scores)
                    agg["per_case"] = case_scores
                    checkpoint_agg[sys_name] = agg
            return checkpoint_agg

    # Final Aggregation
    final_agg: Dict[str, Any] = {}
    for sys_name, case_scores in system_results.items():
        agg = {k: round(float(np.mean([s[k] for s in case_scores])), 4) for k in score_keys}
        agg["n"] = len(case_scores)
        agg["per_case"] = case_scores
        final_agg[sys_name] = agg

    # Print summary tables
    print("\n" + "=" * 105)
    print(f"FRONTIER G-EVAL JUDGE ({judge_model}, Liu et al., EMNLP 2023)")
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
            f"{agg['citation_count']:>9.1f} | {agg['valid_citations_count']:>10.1f} | {agg['citation_validity_rate'] * 100:>9.1f}%"
        )
    print("=" * 105)

    results = {
        "benchmark": "MARS Multi-Year Dual Benchmark (2023-2026)",
        "sample_size": actual_n,
        "generator_model": generator_model,
        "judge_model": judge_model,
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
    parser.add_argument("--sample-size", type=int, default=40, help="Number of stratified cases to evaluate")
    parser.add_argument("--generator", type=str, default=GENERATION_MODEL, help=f"Generator model (default: {GENERATION_MODEL})")
    parser.add_argument("--judge", type=str, default=FRONTIER_JUDGE_MODEL, help=f"Judge model (default: {FRONTIER_JUDGE_MODEL})")
    args = parser.parse_args()
    run_dual_benchmark(
        sample_size=args.sample_size,
        generator_model=args.generator,
        judge_model=args.judge,
    )
