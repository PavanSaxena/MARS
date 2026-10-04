"""Runtime-style tracing primitives for evaluation_v2.

The trace object is deliberately model-agnostic. Real runtime instrumentation
can populate the same fields later; deterministic replay baselines already use
it to produce comparable efficiency tables.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterator, List


@dataclass
class TraceEvent:
    name: str
    duration_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceRecord:
    system: str
    case_id: str
    llm_calls: int = 0
    estimated_prompt_tokens: int = 0
    estimated_completion_tokens: int = 0
    retrieval_calls: int = 0
    retrieved_cases: int = 0
    tool_calls: int = 0
    active_agents: int = 0
    skipped_agents: int = 0
    latency_ms: float = 0.0
    events: List[TraceEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["events"] = [asdict(event) for event in self.events]
        return data


class EvaluationTracer:
    def __init__(self, system: str, case_id: str):
        self.record = TraceRecord(system=system, case_id=case_id)

    @contextmanager
    def event(self, name: str, **metadata: Any) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            self.record.events.append(TraceEvent(name=name, duration_ms=round(elapsed, 4), metadata=metadata))
            self.record.latency_ms = round(self.record.latency_ms + elapsed, 4)

    def add_retrieval(self, count: int) -> None:
        self.record.retrieval_calls += 1
        self.record.retrieved_cases += count

    def add_llm_call(self, prompt: str, completion: str = "") -> None:
        self.record.llm_calls += 1
        self.record.estimated_prompt_tokens += estimate_tokens(prompt)
        self.record.estimated_completion_tokens += estimate_tokens(completion)

    def add_agents(self, active: int, total: int = 4) -> None:
        self.record.active_agents += active
        self.record.skipped_agents += max(0, total - active)


def estimate_tokens(text: str) -> int:
    """A rough, deterministic estimate for cost/latency comparisons."""
    if not text:
        return 0
    return max(1, round(len(text.split()) * 1.33))


def summarize_traces(records: List[TraceRecord]) -> Dict[str, Dict[str, float]]:
    by_system: Dict[str, List[TraceRecord]] = {}
    for record in records:
        by_system.setdefault(record.system, []).append(record)
    return {system: _summary(rows) for system, rows in by_system.items()}


def _summary(records: List[TraceRecord]) -> Dict[str, float]:
    latencies = sorted(record.latency_ms for record in records)
    n = len(records)
    return {
        "cases": n,
        "mean_llm_calls": _mean(record.llm_calls for record in records),
        "mean_prompt_tokens_est": _mean(record.estimated_prompt_tokens for record in records),
        "mean_completion_tokens_est": _mean(record.estimated_completion_tokens for record in records),
        "mean_retrieval_calls": _mean(record.retrieval_calls for record in records),
        "mean_retrieved_cases": _mean(record.retrieved_cases for record in records),
        "mean_tool_calls": _mean(record.tool_calls for record in records),
        "mean_active_agents": _mean(record.active_agents for record in records),
        "mean_skipped_agents": _mean(record.skipped_agents for record in records),
        "latency_p50_ms": _percentile(latencies, 0.50),
        "latency_p95_ms": _percentile(latencies, 0.95),
        "latency_p99_ms": _percentile(latencies, 0.99),
    }


def _mean(values) -> float:
    values = list(values)
    return round(sum(values) / len(values), 4) if values else 0.0


def _percentile(sorted_values: List[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, max(0, round((len(sorted_values) - 1) * q)))
    return round(sorted_values[idx], 4)

