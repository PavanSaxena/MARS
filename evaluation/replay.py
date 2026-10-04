"""Historical decision-replay dataset and baseline packet generation.

This module prepares the central paper evaluation: each target decision is
replayed as if the system were operating on that decision date. It generates
leakage-safe inputs for several baselines and computes simple non-LLM proxy
metrics that are useful for smoke testing. Full advisory quality should still
be judged by blinded human/expert evaluation or a carefully validated judge.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Sequence

from evaluation.dataset import REPO_ROOT, CaseRecord, load_cases, replay_query_text, split_cases, visible_corpus
from evaluation.metrics import mean_dicts
from evaluation.retrieval import BM25Index, HybridIndex


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

    rows = []
    proxy_rows: List[Dict[str, float]] = []
    leakage_violations = []
    for target in targets:
        corpus = visible_corpus(
            cases,
            as_of_date=target.decision_date,
            target_case_id=target.case_id,
            include_visible_outcomes=True,
        )
        bm25 = BM25Index(corpus)
        naive_docs = [doc for doc, _ in bm25.retrieve(replay_query_text(target), k=k)]
        if include_dense:
            hybrid_docs = [doc for doc, _ in HybridIndex(corpus, use_mmr=True).retrieve(replay_query_text(target), k=k)]
        else:
            hybrid_docs = naive_docs

        for docs, system in [(naive_docs, "naive_bm25_rag"), (hybrid_docs, "hybrid_rag_optional_dense")]:
            if target.case_id in {doc["case_id"] for doc in docs}:
                leakage_violations.append({"case_id": target.case_id, "system": system, "type": "self_retrieval"})

        proxy_rows.append(_proxy_metrics(target, naive_docs, prefix="naive_bm25"))
        proxy_rows.append(_proxy_metrics(target, hybrid_docs, prefix="hybrid"))

        rows.append(
            {
                "case_id": target.case_id,
                "decision_date": target.decision_date,
                "department": target.department,
                "action_type": target.action_type,
                "outcome_label": target.outcome_label,
                "query": replay_query_text(target),
                "ground_truth_summary": {
                    "documented_action": target.documented_action,
                    "outcome_label": target.outcome_label,
                    "observation_excerpt": target.observation_excerpt,
                },
                "visible_corpus_size": len(corpus),
                "systems": {
                    "llm_only": {
                        "prompt": _llm_only_prompt(target),
                        "retrieved_cases": [],
                    },
                    "naive_bm25_rag": {
                        "prompt": _rag_prompt(target, naive_docs, title="Naive BM25 RAG"),
                        "retrieved_cases": _slim_docs(naive_docs),
                    },
                    "hybrid_rag_optional_dense": {
                        "prompt": _rag_prompt(target, hybrid_docs, title="Hybrid RAG"),
                        "retrieved_cases": _slim_docs(hybrid_docs),
                    },
                    "static_multi_agent_context": {
                        "prompt": _multi_agent_prompt(target, corpus, dynamic=False, k=k),
                        "retrieved_cases": _department_context(corpus, k=k),
                    },
                    "dynamic_mars_context": {
                        "prompt": _multi_agent_prompt(target, corpus, dynamic=True, k=k),
                        "retrieved_cases": _dynamic_context(target, corpus, k=k),
                    },
                },
            }
        )

    return {
        "protocol": "evaluation.leakage_safe historical decision replay packet",
        "split": split_name,
        "cases": len(rows),
        "k": k,
        "include_dense": include_dense,
        "systems": SYSTEMS,
        "leakage_violations": leakage_violations,
        "proxy_summary": mean_dicts(proxy_rows),
        "replay_cases": rows,
    }


def build_blind_human_eval_packet(
    replay_result: Dict[str, Any],
    *,
    seed: int = 42,
) -> Dict[str, Any]:
    """Create a packet structure ready for human scoring once outputs exist.

    The packet intentionally contains empty `system_output` fields; after LLM
    runs, fill those fields and keep the anonymized labels fixed.
    """
    rng = random.Random(seed)
    packet_cases = []
    for case in replay_result["replay_cases"]:
        labels = list(SYSTEMS)
        rng.shuffle(labels)
        anonymized = {
            f"System {chr(ord('A') + idx)}": {
                "source_system": system,
                "system_output": "",
                "retrieved_case_ids": _retrieved_case_ids(case["systems"][system].get("retrieved_cases", [])),
            }
            for idx, system in enumerate(labels)
        }
        packet_cases.append(
            {
                "case_id": case["case_id"],
                "decision_date": case["decision_date"],
                "department": case["department"],
                "query": case["query"],
                "ground_truth_for_adjudicator_only": case["ground_truth_summary"],
                "systems": anonymized,
                "rubric": {
                    "action_alignment": "1-5: Does the recommendation align with the historically successful/appropriate action?",
                    "evidence_grounding": "1-5: Are claims grounded in visible precedents rather than unsupported assertions?",
                    "risk_foresight": "1-5: Does it identify material downstream risks?",
                    "conflict_awareness": "1-5: Does it surface cross-department trade-offs?",
                    "abstention_appropriateness": "1-5: Does it abstain or caveat appropriately when evidence is weak?",
                },
            }
        )
    return {
        "protocol": "MARS blind human evaluation packet",
        "instructions": [
            "Raters should not see source_system labels.",
            "Randomize case order per rater if possible.",
            "Use 3-5 raters and report inter-rater reliability.",
            "Ground truth block is for adjudication setup, not shown with system outputs unless using outcome-aware scoring.",
        ],
        "cases": packet_cases,
    }


def _proxy_metrics(target: CaseRecord, docs: Sequence[Dict[str, Any]], *, prefix: str) -> Dict[str, float]:
    visible = [doc for doc in docs if doc.get("outcome_visible") and doc.get("outcome_label") in {"success", "failure"}]
    if docs:
        majority_action = _majority(str(doc.get("action_type", "")) for doc in docs)
        same_dept_rate = sum(1 for doc in docs if doc.get("department") == target.department) / len(docs)
    else:
        majority_action = ""
        same_dept_rate = 0.0
    if visible:
        success_rate = sum(1 for doc in visible if doc.get("outcome_label") == "success") / len(visible)
    else:
        success_rate = 0.5
    return {
        f"{prefix}_action_match": 1.0 if majority_action == target.action_type else 0.0,
        f"{prefix}_same_department_rate": same_dept_rate,
        f"{prefix}_visible_outcome_count": float(len(visible)),
        f"{prefix}_success_prob_abs_error": abs(success_rate - target.outcome_binary),
    }


def _retrieved_case_ids(retrieved_cases: Any) -> List[str]:
    if isinstance(retrieved_cases, dict):
        ids: List[str] = []
        for docs in retrieved_cases.values():
            ids.extend(_retrieved_case_ids(docs))
        return ids
    if isinstance(retrieved_cases, list):
        return [
            str(doc.get("case_id"))
            for doc in retrieved_cases
            if isinstance(doc, dict) and doc.get("case_id")
        ]
    return []


def _llm_only_prompt(target: CaseRecord) -> str:
    return (
        "You are a corporate decision advisor. Use only the decision-time context below. "
        "Do not claim access to future outcomes.\n\n"
        f"{replay_query_text(target)}\n\n"
        "Return a concise recommendation, key risks, and confidence with rationale."
    )


def _rag_prompt(target: CaseRecord, docs: Sequence[Dict[str, Any]], *, title: str) -> str:
    return (
        f"You are evaluating a historical decision replay using {title}. "
        "Use only the visible precedents below; do not infer future-only outcomes.\n\n"
        f"CURRENT DECISION\n{replay_query_text(target)}\n\n"
        f"VISIBLE PRECEDENTS\n{_format_docs(docs)}\n\n"
        "Return a concise recommendation, key risks, cited precedents, and confidence."
    )


def _multi_agent_prompt(target: CaseRecord, corpus: Sequence[Dict[str, Any]], *, dynamic: bool, k: int) -> str:
    if dynamic:
        contexts = _dynamic_context(target, corpus, k=k)
        mode = "dynamic routed"
    else:
        contexts = _department_context(corpus, k=k)
        mode = "static all-department"
    return (
        f"Build a {mode} multi-agent decision assessment. Each department must use only its "
        "visible precedents and explicitly state when evidence is weak.\n\n"
        f"CURRENT DECISION\n{replay_query_text(target)}\n\n"
        f"DEPARTMENT CONTEXTS\n{json.dumps(contexts, indent=2)}\n\n"
        "Return final recommendation, conflicts, risks, and confidence."
    )


def _department_context(corpus: Sequence[Dict[str, Any]], *, k: int) -> Dict[str, List[Dict[str, Any]]]:
    contexts: Dict[str, List[Dict[str, Any]]] = {}
    for dept in ["Finance", "Legal", "Operations", "R&D"]:
        docs = [doc for doc in corpus if doc.get("department") == dept]
        contexts[dept] = _slim_docs(sorted(docs, key=lambda d: d.get("decision_date", ""), reverse=True)[:k])
    return contexts


def _dynamic_context(target: CaseRecord, corpus: Sequence[Dict[str, Any]], *, k: int) -> Dict[str, List[Dict[str, Any]]]:
    target_depts = {target.department}
    for item in (target.cross_dept_impact or "").replace(",", ";").split(";"):
        item = item.strip()
        if item in {"Finance", "Legal", "Operations", "R&D"}:
            target_depts.add(item)
    return {
        dept: docs
        for dept, docs in _department_context(corpus, k=k).items()
        if dept in target_depts
    }


def _format_docs(docs: Sequence[Dict[str, Any]]) -> str:
    if not docs:
        return "No visible precedents found."
    blocks = []
    for idx, doc in enumerate(docs, start=1):
        outcome = doc.get("outcome_label") if doc.get("outcome_visible") else "not visible at decision time"
        blocks.append(
            f"[{idx}] {doc.get('case_id')} | {doc.get('decision_date')} | {doc.get('department')} | "
            f"{doc.get('action_type')} | outcome={outcome}\n"
            f"{doc.get('decision_title')}\n{doc.get('decision_description')}"
        )
    return "\n\n".join(blocks)


def _slim_docs(docs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "case_id": doc.get("case_id"),
            "decision_date": doc.get("decision_date"),
            "department": doc.get("department"),
            "action_type": doc.get("action_type"),
            "decision_title": doc.get("decision_title"),
            "outcome_visible": doc.get("outcome_visible"),
            "outcome_label": doc.get("outcome_label") if doc.get("outcome_visible") else "unknown",
        }
        for doc in docs
    ]


def _majority(values: Sequence[str]) -> str:
    counts: Dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return max(counts.items(), key=lambda item: item[1])[0] if counts else ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build leakage-safe decision replay packets.")
    parser.add_argument("--split", default="test", choices=["train", "validation", "test"])
    parser.add_argument("--max-cases", type=int, default=25)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--include-dense", action="store_true")
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "evaluation" / "leakage_safe" / "artifacts" / "decision_replay_packet.json"),
    )
    parser.add_argument(
        "--human-output",
        default=str(REPO_ROOT / "evaluation" / "leakage_safe" / "artifacts" / "blind_human_eval_packet.json"),
    )
    args = parser.parse_args()
    replay = build_replay_cases(
        split_name=args.split,
        max_cases=args.max_cases,
        k=args.k,
        include_dense=args.include_dense,
    )
    human = build_blind_human_eval_packet(replay)
    output = Path(args.output)
    human_output = Path(args.human_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(replay, indent=2), encoding="utf-8")
    human_output.write_text(json.dumps(human, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "human_output": str(human_output),
        "cases": replay["cases"],
        "leakage_violations": len(replay["leakage_violations"]),
        "proxy_summary": replay["proxy_summary"],
    }, indent=2))


if __name__ == "__main__":
    main()
