"""Historical decision-replay dataset, baseline packet generation, and replay tracing.

Consolidates:
1. Decision Replay Packets:
   - Generates leakage-safe inputs for 5 systems:
     llm_only, naive_bm25_rag, hybrid_rag_optional_dense,
     static_multi_agent_context, dynamic_mars_context.
   - Computes non-LLM proxy metrics and builds blind human evaluation packets.
2. Replay Execution & Tracing:
   - Runs deterministic execution tracing across all 5 systems.
   - Logs agent invocations, retrieval counts, and latency traces.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Sequence

from evaluation.dataset import (
    REPO_ROOT,
    CaseRecord,
    load_cases,
    replay_query_text,
    split_cases,
    visible_corpus,
)
from evaluation.eval_retrieval import BM25Index, HybridIndex
from evaluation.metrics import mean_dicts
from evaluation.tracing import EvaluationTracer, TraceRecord, summarize_traces


SYSTEMS = [
    "llm_only",
    "naive_bm25_rag",
    "hybrid_rag_optional_dense",
    "static_multi_agent_context",
    "dynamic_mars_context",
]


def build_replay_cases(
    *,
    split_name: str = "test",
    max_cases: int | None = None,
    k: int = 5,
    include_dense: bool = False,
) -> Dict[str, Any]:
    cases = load_cases()
    targets = split_cases(cases)[split_name]
    if max_cases is not None:
        targets = targets[:max_cases]

    replay_cases: List[Dict[str, Any]] = []
    leakage_violations: List[Dict[str, Any]] = []
    proxy_metrics: Dict[str, List[Dict[str, float]]] = {s: [] for s in SYSTEMS}

    for target in targets:
        corpus = visible_corpus(cases, as_of_date=target.decision_date, target_case_id=target.case_id)
        corpus_ids = {row["case_id"] for row in corpus}
        if target.case_id in corpus_ids:
            leakage_violations.append(
                {"case_id": target.case_id, "violation": "target_case_in_visible_corpus"}
            )

        bm25_index = BM25Index(corpus)
        query = replay_query_text(target)
        bm25_docs = [doc for doc, _ in bm25_index.retrieve(query, k=k)]

        if include_dense:
            hybrid_index = HybridIndex(corpus, dense_weight=0.65, use_mmr=True)
            hybrid_docs = [doc for doc, _ in hybrid_index.retrieve(query, k=k)]
        else:
            hybrid_docs = bm25_docs

        static_context = _department_context(corpus, k=k)
        dynamic_context = _dynamic_context(target, corpus, k=k)

        systems_payload = {
            "llm_only": {
                "prompt": _llm_only_prompt(target),
                "retrieved_cases": [],
            },
            "naive_bm25_rag": {
                "prompt": _rag_prompt(target, bm25_docs, title="Naive BM25 Precedents"),
                "retrieved_cases": _slim_docs(bm25_docs),
            },
            "hybrid_rag_optional_dense": {
                "prompt": _rag_prompt(
                    target,
                    hybrid_docs,
                    title="Dense/Hybrid Precedents" if include_dense else "BM25 Precedents (Dense Off)",
                ),
                "retrieved_cases": _slim_docs(hybrid_docs),
            },
            "static_multi_agent_context": {
                "prompt": _multi_agent_prompt(target, static_context, dynamic=False, k=k),
                "retrieved_cases": {dept: _slim_docs(docs) for dept, docs in static_context.items()},
            },
            "dynamic_mars_context": {
                "prompt": _multi_agent_prompt(target, dynamic_context, dynamic=True, k=k),
                "retrieved_cases": {dept: _slim_docs(docs) for dept, docs in dynamic_context.items()},
            },
        }

        # Check self retrieval
        for system_name, payload in systems_payload.items():
            retrieved_ids = _retrieved_case_ids(payload["retrieved_cases"])
            if target.case_id in retrieved_ids:
                leakage_violations.append(
                    {
                        "case_id": target.case_id,
                        "system": system_name,
                        "violation": "target_case_retrieved_by_system",
                    }
                )

        proxy_metrics["llm_only"].append(
            {"action_match": 0.0, "same_dept_rate": 0.0, "visible_outcome_count": 0.0, "success_prob_abs_error": 0.5}
        )
        proxy_metrics["naive_bm25_rag"].append(_proxy_metrics(target, bm25_docs, prefix="bm25"))
        proxy_metrics["hybrid_rag_optional_dense"].append(_proxy_metrics(target, hybrid_docs, prefix="hybrid"))
        proxy_metrics["static_multi_agent_context"].append(
            _proxy_metrics(target, [doc for docs in static_context.values() for doc in docs], prefix="static")
        )
        proxy_metrics["dynamic_mars_context"].append(
            _proxy_metrics(target, [doc for docs in dynamic_context.values() for doc in docs], prefix="dynamic")
        )

        replay_cases.append(
            {
                "case_id": target.case_id,
                "company_name": target.company_name,
                "department": target.department,
                "action_type": target.action_type,
                "decision_date": target.decision_date,
                "observation_date": target.observation_date,
                "actual_outcome": target.outcome_label,
                "query": query,
                "systems": systems_payload,
            }
        )

    return {
        "protocol": "MARS historical decision replay packet",
        "split": split_name,
        "cases": len(replay_cases),
        "leakage_violations": leakage_violations,
        "proxy_summary": {k: mean_dicts(v) for k, v in proxy_metrics.items()},
        "replay_cases": replay_cases,
    }


def build_blind_human_eval_packet(replay_result: Dict[str, Any], *, seed: int = 42) -> Dict[str, Any]:
    rng = random.Random(seed)
    blind_cases = []
    rubric = {
        "scale": "1 to 5 Likert",
        "dimensions": {
            "factual_grounding": "Are claims supported only by the provided context and decision-time record?",
            "action_utility": "Is the recommendation concrete, operationally viable, and relevant to the inquiry?",
            "risk_foresight": "Does the response anticipate cross-department and execution risks?",
            "temporal_validity": "Does the response avoid future leakage or unverified post-decision assumptions?",
        },
    }

    for case in replay_result["replay_cases"]:
        system_names = list(SYSTEMS)
        rng.shuffle(system_names)
        labels = [f"System {chr(ord('A') + idx)}" for idx in range(len(system_names))]
        assignment = dict(zip(labels, system_names))

        options = []
        for label, sys_name in assignment.items():
            payload = case["systems"][sys_name]
            options.append(
                {
                    "system_label": label,
                    "prompt": payload["prompt"],
                    "retrieved_case_ids": _retrieved_case_ids(payload["retrieved_cases"]),
                    "system_output": "",
                    "scores": {dim: None for dim in rubric["dimensions"]},
                    "notes": "",
                }
            )

        blind_cases.append(
            {
                "case_id": case["case_id"],
                "department": case["department"],
                "decision_date": case["decision_date"],
                "inquiry": case["query"],
                "options": options,
                "_key": assignment,
            }
        )

    return {
        "protocol": "MARS blinded evaluation packet",
        "cases": len(blind_cases),
        "rubric": rubric,
        "cases_to_evaluate": blind_cases,
    }


# =============================================================================
# Execution Tracing Runner
# =============================================================================

def run_replay_outputs(
    *,
    split_name: str = "validation",
    max_cases: int = 25,
    k: int = 5,
    mode: str = "deterministic",
) -> Dict[str, Any]:
    """Generate replay outputs and runtime efficiency traces."""
    if mode != "deterministic":
        raise RuntimeError(
            "Live LLM replay is not configured yet. Use mode='deterministic' or add a model adapter."
        )

    packet = build_replay_cases(split_name=split_name, max_cases=max_cases, k=k, include_dense=False)
    outputs: List[Dict[str, Any]] = []
    traces: List[TraceRecord] = []

    for case in packet["replay_cases"]:
        for system in SYSTEMS:
            tracer = EvaluationTracer(system=system, case_id=case["case_id"])
            with tracer.event("generate_output"):
                output = _deterministic_output(case, system, tracer)
            tracer.add_llm_call(case["systems"][system]["prompt"], output)
            outputs.append(
                {
                    "case_id": case["case_id"],
                    "system": system,
                    "output": output,
                    "trace": tracer.record.to_dict(),
                }
            )
            traces.append(tracer.record)

    return {
        "protocol": "MARS replay outputs & traces",
        "mode": mode,
        "split": split_name,
        "cases": packet["cases"],
        "systems": SYSTEMS,
        "leakage_violations": packet["leakage_violations"],
        "trace_summary": summarize_traces(traces),
        "outputs": outputs,
    }


def _deterministic_output(case: Dict[str, Any], system: str, tracer: EvaluationTracer) -> str:
    system_payload = case["systems"][system]
    retrieved = system_payload.get("retrieved_cases", [])
    if system == "llm_only":
        tracer.add_agents(active=0)
        return (
            "Recommendation: insufficient precedent context was supplied; provide a cautious decision-time assessment only.\n"
            "Risks: unknown empirical precedent risk, cross-department uncertainty.\n"
            "Confidence: 0.30."
        )

    if isinstance(retrieved, dict):
        active_agents = len(retrieved)
        total_cases = sum(len(v) for v in retrieved.values())
        tracer.add_agents(active=active_agents)
        tracer.add_retrieval(total_cases)
        context_line = ", ".join(f"{dept}: {len(rows)} cases" for dept, rows in retrieved.items())
    else:
        active_agents = 1
        total_cases = len(retrieved)
        tracer.add_agents(active=active_agents)
        tracer.add_retrieval(total_cases)
        context_line = f"{total_cases} retrieved precedents"

    outcome_visible = _visible_outcome_count(retrieved)
    return (
        f"Recommendation: use the visible historical precedents conservatively before acting on {case['department']} decision.\n"
        f"Evidence: {context_line}; {outcome_visible} retrieved precedents have outcomes visible at this decision date.\n"
        "Risks: verify whether prior precedent conditions match the current decision; avoid relying on future-only outcomes.\n"
        f"Confidence: {_confidence_from_counts(total_cases, outcome_visible):.2f}."
    )


def _visible_outcome_count(retrieved: Any) -> int:
    if isinstance(retrieved, dict):
        return sum(_visible_outcome_count(rows) for rows in retrieved.values())
    if isinstance(retrieved, list):
        return sum(1 for row in retrieved if isinstance(row, dict) and row.get("outcome_visible"))
    return 0


def _confidence_from_counts(total_cases: int, visible_outcomes: int) -> float:
    if total_cases <= 0:
        return 0.25
    return min(0.75, 0.35 + 0.05 * visible_outcomes + 0.02 * total_cases)


# =============================================================================
# Helper Prompt Formats & Metric Proxies
# =============================================================================

def _proxy_metrics(target: CaseRecord, docs: Sequence[Dict[str, Any]], *, prefix: str) -> Dict[str, float]:
    if not docs:
        return {
            f"{prefix}_action_match": 0.0,
            f"{prefix}_same_dept_rate": 0.0,
            f"{prefix}_visible_outcome_count": 0.0,
            f"{prefix}_success_prob_abs_error": 0.5,
        }

    same_action = sum(1 for d in docs if d.get("action_type") == target.action_type) / len(docs)
    same_dept = sum(1 for d in docs if d.get("department") == target.department) / len(docs)
    visible_outcomes = [d for d in docs if d.get("outcome_visible") and d.get("outcome_label")]
    succ_count = sum(1 for d in visible_outcomes if d.get("outcome_label", "").lower() == "success")
    prob = (succ_count / len(visible_outcomes)) if visible_outcomes else 0.5
    error = abs(prob - target.outcome_binary)

    return {
        "action_match": same_action,
        "same_dept_rate": same_dept,
        "visible_outcome_count": float(len(visible_outcomes)),
        "success_prob_abs_error": error,
    }


def _retrieved_case_ids(retrieved_cases: Any) -> List[str]:
    if isinstance(retrieved_cases, list):
        ids = []
        for item in retrieved_cases:
            if isinstance(item, dict) and "case_id" in item:
                ids.append(item["case_id"])
            elif isinstance(item, str):
                ids.append(item)
        return ids
    if isinstance(retrieved_cases, dict):
        ids = []
        for rows in retrieved_cases.values():
            ids.extend(_retrieved_case_ids(rows))
        return ids
    return []


def _llm_only_prompt(target: CaseRecord) -> str:
    return (
        f"You are advising on a corporate decision as of {target.decision_date}.\n"
        f"Inquiry: {replay_query_text(target)}\n"
        "No historical precedent records are provided. Provide a recommended action, key risks, and confidence."
    )


def _rag_prompt(target: CaseRecord, docs: Sequence[Dict[str, Any]], *, title: str) -> str:
    context = _format_docs(docs)
    return (
        f"You are advising on a corporate decision as of {target.decision_date}.\n"
        f"Inquiry: {replay_query_text(target)}\n\n"
        f"Context ({title}):\n{context}\n\n"
        "Rely only on the precedents above that were observable before the decision date."
    )


def _multi_agent_prompt(
    target: CaseRecord,
    dept_context: Dict[str, Sequence[Dict[str, Any]]],
    *,
    dynamic: bool,
    k: int,
) -> str:
    blocks = []
    for dept, docs in sorted(dept_context.items()):
        blocks.append(f"[{dept.upper()} SPECIALIST CONTEXT]\n{_format_docs(docs)}")
    joined = "\n\n".join(blocks)
    mode = "Dynamic Sparse Cross-Department Context" if dynamic else "Static All-Department Context"
    return (
        f"You are the MARS Executive Advisory Aggregator operating as of {target.decision_date}.\n"
        f"Inquiry: {replay_query_text(target)}\n\n"
        f"{mode}:\n{joined}\n\n"
        "Synthesize conflicting perspectives and cite only visible historical precedents."
    )


def _department_context(corpus: Sequence[Dict[str, Any]], *, k: int) -> Dict[str, Sequence[Dict[str, Any]]]:
    result = {}
    for dept in ["Finance", "Legal", "Operations", "R&D"]:
        subset = [d for d in corpus if d.get("department") == dept]
        result[dept] = subset[:k]
    return result


def _dynamic_context(target: CaseRecord, corpus: Sequence[Dict[str, Any]], *, k: int) -> Dict[str, Sequence[Dict[str, Any]]]:
    impacted = {target.department}
    cross_text = (target.cross_dept_impact or "").lower()
    for d in ["Finance", "Legal", "Operations", "R&D"]:
        if d.lower() in cross_text:
            impacted.add(d)

    result = {}
    for dept in sorted(impacted):
        subset = [d for d in corpus if d.get("department") == dept]
        result[dept] = subset[:k]
    return result


def _format_docs(docs: Sequence[Dict[str, Any]]) -> str:
    if not docs:
        return "No historical precedents available."
    lines = []
    for idx, d in enumerate(docs, start=1):
        outcome_str = d.get("outcome_label") or "UNKNOWN (future-censored)"
        lines.append(
            f"{idx}. [{d.get('case_id')}] {d.get('decision_title')} "
            f"({d.get('department')}, {d.get('decision_date')}) -> Outcome: {outcome_str}\n"
            f"   Action: {d.get('documented_action')}"
        )
    return "\n".join(lines)


def _slim_docs(docs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "case_id": d.get("case_id"),
            "department": d.get("department"),
            "action_type": d.get("action_type"),
            "decision_date": d.get("decision_date"),
            "outcome_visible": d.get("outcome_visible", False),
            "outcome_label": d.get("outcome_label", ""),
        }
        for d in docs
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Decision replay and output generation.")
    parser.add_argument("--mode", default="packet", choices=["packet", "outputs", "all"])
    parser.add_argument("--split", default="test", choices=["train", "validation", "test"])
    parser.add_argument("--max-cases", type=int, default=25)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--include-dense", action="store_true")
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "evaluation" / "artifacts" / "decision_replay_packet.json"),
    )
    parser.add_argument(
        "--human-output",
        default=str(REPO_ROOT / "evaluation" / "artifacts" / "blind_human_eval_packet.json"),
    )
    args = parser.parse_args()

    artifacts_dir = REPO_ROOT / "evaluation" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    if args.mode in ("packet", "all"):
        replay = build_replay_cases(
            split_name=args.split,
            max_cases=args.max_cases,
            k=args.k,
            include_dense=args.include_dense,
        )
        human = build_blind_human_eval_packet(replay)
        Path(args.output).write_text(json.dumps(replay, indent=2), encoding="utf-8")
        Path(args.human_output).write_text(json.dumps(human, indent=2), encoding="utf-8")
        print(f"Replay packet saved to: {args.output}")
        print(f"Blind human eval packet saved to: {args.human_output}")

    if args.mode in ("outputs", "all"):
        outputs_res = run_replay_outputs(
            split_name=args.split,
            max_cases=args.max_cases,
            k=args.k,
            mode="deterministic",
        )
        out_path = artifacts_dir / "replay_outputs.json"
        out_path.write_text(json.dumps(outputs_res, indent=2), encoding="utf-8")
        print(f"Replay outputs & traces saved to: {out_path}")


if __name__ == "__main__":
    main()
