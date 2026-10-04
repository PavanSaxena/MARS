"""Generate leakage-safe replay outputs and efficiency traces.

This runner has two modes:

- `deterministic` (default): produces transparent template outputs from the
  replay packet. This is useful for protocol smoke tests and tracing.
- `llm`: reserved for future live-model execution; the command fails clearly
  until model-specific adapters are configured.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from evaluation.leakage_safe.dataset import REPO_ROOT
from evaluation.leakage_safe.replay import SYSTEMS, build_replay_cases
from evaluation.leakage_safe.tracing import EvaluationTracer, TraceRecord, summarize_traces


def run_replay_outputs(
    *,
    split_name: str = "validation",
    max_cases: int = 25,
    k: int = 5,
    mode: str = "deterministic",
) -> Dict[str, Any]:
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
        "protocol": "evaluation.leakage_safe replay outputs",
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate replay outputs and traces.")
    parser.add_argument("--split", default="validation", choices=["train", "validation", "test"])
    parser.add_argument("--max-cases", type=int, default=25)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--mode", default="deterministic", choices=["deterministic", "llm"])
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "evaluation" / "leakage_safe" / "artifacts" / "replay_outputs.json"),
    )
    args = parser.parse_args()
    result = run_replay_outputs(
        split_name=args.split,
        max_cases=args.max_cases,
        k=args.k,
        mode=args.mode,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "cases": result["cases"],
        "leakage_violations": len(result["leakage_violations"]),
        "trace_summary": result["trace_summary"],
    }, indent=2))


if __name__ == "__main__":
    main()

