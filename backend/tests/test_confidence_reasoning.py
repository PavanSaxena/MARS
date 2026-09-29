"""Unit and integration test suite for MARS multi-factor confidence and reasoning engine."""

import unittest
from app.reasoning.confidence import (
    calculate_confidence,
    compute_recency,
    parse_quarter_to_index,
)
from app.reasoning.outcome_analysis import analyze_outcomes
from app.reasoning.similarity import compute_similarity
from app.agents.common import build_case_evidence
from app.reasoning.aggregator import _confidence_value, _fmt_department


class TestMARSConfidenceReasoning(unittest.TestCase):
    def test_quarter_parsing(self):
        self.assertEqual(parse_quarter_to_index("2023Q1"), 2023 * 4 + 0)
        self.assertEqual(parse_quarter_to_index("2024-Q3"), 2024 * 4 + 2)
        self.assertEqual(parse_quarter_to_index("Q2 2025"), 2025 * 4 + 1)
        self.assertEqual(parse_quarter_to_index("2026-06-15"), 2026 * 4 + 1)

    def test_recency_decay(self):
        cases_old = [{"metadata": {"quarter": "2023Q1"}}]
        cases_mid = [{"metadata": {"quarter": "2024Q4"}}]
        cases_now = [{"metadata": {"quarter": "2026Q2"}}]

        rec_old = compute_recency(cases_old, reference_quarter="2026Q2")
        rec_mid = compute_recency(cases_mid, reference_quarter="2026Q2")
        rec_now = compute_recency(cases_now, reference_quarter="2026Q2")

        self.assertLess(rec_old, rec_mid)
        self.assertLess(rec_mid, rec_now)
        self.assertAlmostEqual(rec_now, 1.0, places=3)

    def test_outcome_classification(self):
        cases = [
            {"outcome": "Full regulatory clearance obtained with zero fines"},
            {"outcome": "Achieved gross margin expansion above guidance"},
            {"outcome": "Project delayed due to severe supply chain bottlenecks"},
        ]
        success_rate = analyze_outcomes(cases)
        # 2 successes out of 3 cases
        self.assertAlmostEqual(success_rate, 2 / 3, places=2)

    def test_confidence_calculation(self):
        # High similarity + high success + fresh
        cases_strong = [
            {"metadata": {"quarter": "2026Q1", "outcome": "success"}, "distance": 0.1, "outcome": "success"}
        ]
        conf_strong = calculate_confidence(cases=cases_strong)
        self.assertGreater(conf_strong, 0.90)

        # Low similarity + failure + stale
        cases_weak = [
            {"metadata": {"quarter": "2023Q1", "outcome": "failed"}, "distance": 0.65, "outcome": "failed"}
        ]
        conf_weak = calculate_confidence(cases=cases_weak)
        self.assertLess(conf_weak, 0.40)

        # Empty case list must yield 0.0
        self.assertEqual(calculate_confidence(cases=[]), 0.0)

    def test_all_department_evidence_and_aggregator_ranking(self):
        dept_data = {
            "Finance": [
                {"metadata": {"case_id": "AAPL-2024Q1-0010", "quarter": "2024Q1", "department": "Finance", "outcome": "Gross margin expansion of 150 bps achieved"}, "distance": 0.12, "outcome": "Gross margin expansion of 150 bps achieved", "document": "Treasury note"}
            ],
            "Legal": [
                {"metadata": {"case_id": "AAPL-2025Q2-0045", "quarter": "2025Q2", "department": "Legal", "outcome": "Full regulatory clearance obtained with zero penalties"}, "distance": 0.08, "outcome": "Full regulatory clearance obtained with zero penalties", "document": "DOJ compliance memo"}
            ],
            "Operations": [
                {"metadata": {"case_id": "AAPL-2023Q4-0022", "quarter": "2023Q4", "department": "Operations", "outcome": "Delayed rollout due to port congestion and component shortages"}, "distance": 0.35, "outcome": "Delayed rollout due to port congestion and component shortages", "document": "Supply chain audit"}
            ],
            "R&D": []
        }

        outputs = {}
        for dept, cases in dept_data.items():
            evidence = build_case_evidence(cases, reported_confidence=0.85 if cases else 0.0)
            outputs[dept] = {"response": "test", "reasoning": "test", **evidence}

        # Check ranking order
        ranked = sorted(outputs.items(), key=lambda item: _confidence_value(item[1]), reverse=True)
        ranked_names = [name for name, _ in ranked]
        self.assertEqual(ranked_names, ["Legal", "Finance", "Operations", "R&D"])

    def test_weight_optimization_from_outcomes(self):
        from app.reasoning.confidence import optimize_weights_from_outcomes

        training_data = [
            {"metadata": {"similarity": 0.9, "quarter": "2026Q1", "outcome": "success"}},
            {"metadata": {"similarity": 0.85, "quarter": "2025Q4", "outcome": "achieved growth"}},
            {"metadata": {"similarity": 0.3, "quarter": "2023Q1", "outcome": "delayed failure"}},
            {"metadata": {"similarity": 0.8, "quarter": "2026Q2", "outcome": "approved and cleared"}},
            {"metadata": {"similarity": 0.2, "quarter": "2022Q3", "outcome": "failed and cancelled"}},
        ]
        w_opt = optimize_weights_from_outcomes(training_data)
        self.assertEqual(len(w_opt), 3)
        self.assertAlmostEqual(sum(w_opt), 1.0, places=2)
        # Similarity and success rate should carry substantial positive weight
        self.assertGreater(w_opt[0] + w_opt[2], 0.6)

    def test_sparse_dynamic_routing_agent_skipping(self):
        from app.agents.finance_agent import finance_agent
        from app.agents.rd_agent import rd_agent
        from app.agents.legal_agent import legal_agent
        from app.agents.operations_agent import operations_agent

        # State where only Finance and Legal are active
        state_sparse = {
            "messages": [{"role": "user", "content": "Tax and liquidity routing"}],
            "active_departments": ["finance", "legal"],
            "model": None
        }

        rd_result = rd_agent(state_sparse)
        ops_result = operations_agent(state_sparse)

        # Scoped out agents return None immediately with zero LLM execution
        self.assertIsNone(rd_result.get("rd_output"))
        self.assertIsNone(ops_result.get("operations_output"))

    def test_semantic_vector_gating_router(self):
        from app.reasoning.semantic_router import route_departments_semantically

        # 1. Targeted regulatory query should prioritize Legal
        legal_query = "Antitrust compliance under the European Union Digital Markets Act"
        active_legal, scores_legal = route_departments_semantically(legal_query)
        self.assertIn("legal", active_legal)
        self.assertGreater(scores_legal["legal"], scores_legal["rd"])

        # 2. Targeted engineering query should prioritize R&D
        rd_query = "Neural Engine INT8 quantization and CoreML firmware performance"
        active_rd, scores_rd = route_departments_semantically(rd_query)
        self.assertIn("rd", active_rd)
        self.assertGreater(scores_rd["rd"], scores_rd["legal"])

    def test_persistent_weight_registry(self):
        from app.reasoning.weight_registry import weight_registry

        # Test fetching department weights
        w_legal = weight_registry.get_weights(department="legal")
        self.assertEqual(len(w_legal), 3)
        self.assertAlmostEqual(sum(w_legal), 1.0, places=2)

        # Test updating and persisting weights
        test_update = (0.42, 0.28, 0.30)
        weight_registry.update_department_weights("legal", test_update)
        w_updated = weight_registry.get_weights(department="legal")
        self.assertAlmostEqual(w_updated[0], 0.42, places=2)


if __name__ == "__main__":
    unittest.main()
