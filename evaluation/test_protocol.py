"""Protocol-level tests for the leakage-safe evaluation layer."""

from __future__ import annotations

from evaluation.dataset import load_cases, split_cases, visible_corpus
from evaluation.replay import build_replay_cases
from evaluation.retrieval import run_retrieval_evaluation


def test_visible_corpus_excludes_target_and_future_decisions():
    cases = load_cases()
    target = split_cases(cases)["test"][0]
    corpus = visible_corpus(cases, as_of_date=target.decision_date, target_case_id=target.case_id)
    assert target.case_id not in {row["case_id"] for row in corpus}
    assert all(row["decision_date"] < target.decision_date for row in corpus)


def test_visible_corpus_hides_future_outcomes():
    cases = load_cases()
    target = split_cases(cases)["validation"][0]
    corpus = visible_corpus(cases, as_of_date=target.decision_date, target_case_id=target.case_id)
    assert all(
        row["outcome_visible"] or row["outcome_label"] == "unknown"
        for row in corpus
    )
    assert all(
        (not row["outcome_visible"]) or row["observation_date"] <= target.decision_date
        for row in corpus
    )


def test_retrieval_smoke_has_no_leakage():
    result = run_retrieval_evaluation(split_name="validation", max_queries=5)
    assert result["queries_evaluated"] == 5
    assert result["leakage_violations"] == []


def test_replay_packet_smoke_has_no_leakage():
    packet = build_replay_cases(split_name="validation", max_cases=5, k=3)
    assert packet["cases"] == 5
    assert packet["leakage_violations"] == []
    for case in packet["replay_cases"]:
        for system in ["naive_bm25_rag", "hybrid_rag_optional_dense"]:
            ids = {doc["case_id"] for doc in case["systems"][system]["retrieved_cases"]}
            assert case["case_id"] not in ids

