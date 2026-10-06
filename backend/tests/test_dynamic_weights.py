"""
Unit test suite for Query-Adaptive Dynamic Weighting Engine.
Tests that feature weights adjust adaptively to:
1. Specific query intent (Temporal Urgency vs Risk Stakes vs Precedent Specificity)
2. Heterogeneous agent domain priorities (Legal vs Finance vs R&D vs Operations)
3. Mathematical simplex invariants (sum == 1.0, w_i >= 0.10)
"""

import unittest
import math

from app.reasoning.dynamic_weighting import dynamic_weight_engine, QueryAdaptiveWeightEngine
from app.reasoning.confidence import calculate_confidence, calculate_confidence_with_details
from app.agents.common import build_case_evidence


class TestQueryAdaptiveDynamicWeighting(unittest.TestCase):
    def setUp(self):
        self.engine = dynamic_weight_engine

    def test_simplex_invariant_and_bounds(self):
        """Weights must strictly sum to 1.0 and satisfy w_i >= 0.10 for any query."""
        test_queries = [
            "urgent 2025 regulatory compliance update",
            "catastrophic 50 billion dollar financial loss margin risk",
            "exact step by step INT8 neural quantization architecture",
            "",
            "   ",
            "general strategic overview",
            "What should we do regarding TSMC silicon wafer supply chain?",
        ]
        departments = ["legal", "finance", "rd", "operations", "unknown", None]

        for q in test_queries:
            for dept in departments:
                res = self.engine.compute_weights(query=q, department=dept)
                w1, w2, w3 = res.weights
                total = w1 + w2 + w3

                self.assertAlmostEqual(total, 1.0, places=2, msg=f"Failed sum=1.0 for q='{q}', dept='{dept}'")
                self.assertGreaterEqual(w1, 0.099, msg=f"w1 below 0.10 for q='{q}', dept='{dept}'")
                self.assertGreaterEqual(w2, 0.099, msg=f"w2 below 0.10 for q='{q}', dept='{dept}'")
                self.assertGreaterEqual(w3, 0.099, msg=f"w3 below 0.10 for q='{q}', dept='{dept}'")

    def test_temporal_query_boosts_recency_weight(self):
        """A query emphasizing recency/regulations should elevate w2 (Recency)."""
        neutral_q = "General company overview"
        temporal_q = "What are the latest 2024 compliance regulations and immediate antitrust updates under EU DMA?"

        neutral_res = self.engine.compute_weights(query=neutral_q, department="legal")
        temporal_res = self.engine.compute_weights(query=temporal_q, department="legal")

        # w2 in temporal query should be significantly higher than neutral
        self.assertGreater(temporal_res.w_recency, neutral_res.w_recency)
        self.assertIn("temporal freshness", temporal_res.rationale.lower())

    def test_risk_query_boosts_success_weight(self):
        """A high-stakes capital/risk query should elevate w3 (Past Success)."""
        neutral_q = "General company overview"
        risk_q = "Should we commit $15 billion capital expenditure with severe margin downside and bankruptcy risk?"

        neutral_res = self.engine.compute_weights(query=neutral_q, department="finance")
        risk_res = self.engine.compute_weights(query=risk_q, department="finance")

        # w3 in risk query should be higher than neutral
        self.assertGreater(risk_res.w_past_success, neutral_res.w_past_success)
        self.assertIn("past success", risk_res.rationale.lower())

    def test_precedent_query_boosts_similarity_weight(self):
        """A technical/procedural query should elevate w1 (Similarity)."""
        neutral_q = "General company overview"
        precedent_q = "What exact INT8 neural network quantization architecture and code specifications were used?"

        neutral_res = self.engine.compute_weights(query=neutral_q, department="rd")
        prec_res = self.engine.compute_weights(query=precedent_q, department="rd")

        # w1 in precedent query should be higher than neutral
        self.assertGreater(prec_res.w_similarity, neutral_res.w_similarity)
        self.assertIn("precedent similarity", prec_res.rationale.lower())

    def test_heterogeneous_agent_priorities_for_same_query(self):
        """For the EXACT SAME query, different agents must prioritize different factors."""
        query = "How to handle Foxconn supply chain disruption under recent contracts to avoid margin losses?"

        legal_res = self.engine.compute_weights(query=query, department="legal")
        finance_res = self.engine.compute_weights(query=query, department="finance")
        rd_res = self.engine.compute_weights(query=query, department="rd")

        # Legal should prioritize recency more than Finance
        self.assertGreater(legal_res.w_recency, finance_res.w_recency)
        # Finance should prioritize past success / ROI more than R&D
        self.assertGreater(finance_res.w_past_success, rd_res.w_past_success)
        # R&D should prioritize similarity more than Finance
        self.assertGreater(rd_res.w_similarity, finance_res.w_similarity)

    def test_calculate_confidence_integration_with_query(self):
        """calculate_confidence adaptively adjusts score based on query parameter."""
        # Fresh case with high recency but low past success
        cases = [
            {
                "metadata": {"quarter": "2026Q2", "similarity": 0.85, "outcome": "failed"},
                "similarity": 0.85,
                "outcome": "failed",
            }
        ]

        # Query A: Temporal urgency (boosts recency -> boosts confidence because case is fresh)
        conf_temporal, det_temporal = calculate_confidence_with_details(
            cases=cases,
            query="Latest 2026 urgent update",
            department="legal",
        )

        # Query B: High risk/success stakes (boosts past success -> penalizes confidence because case failed)
        conf_risk, det_risk = calculate_confidence_with_details(
            cases=cases,
            query="Severe capital expenditure risk and success track record",
            department="finance",
        )

        # The fresh case should receive a higher confidence under a temporal query than under a risk/success query
        self.assertGreater(conf_temporal, conf_risk)
        self.assertEqual(det_temporal["mode"], "query_adaptive_dynamic")
        self.assertEqual(det_risk["mode"], "query_adaptive_dynamic")

    def test_build_case_evidence_telemetry(self):
        """build_case_evidence attaches dynamic weights and explanation."""
        cases = [
            {
                "metadata": {"case_id": "TEST-1", "quarter": "2025Q1", "department": "legal", "outcome": "success"},
                "similarity": 0.88,
                "outcome": "success",
            }
        ]
        ev = build_case_evidence(
            cases=cases,
            query="What are the latest 2025 compliance rules?",
            department="legal",
        )

        self.assertIn("dynamic_weights", ev)
        self.assertIn("weight_rationale", ev)
        self.assertIn("weight_telemetry", ev)
        self.assertIsNotNone(ev["dynamic_weights"])
        self.assertEqual(len(ev["dynamic_weights"]), 3)
        self.assertIn("Weight Allocation", ev["explanation"])


if __name__ == "__main__":
    unittest.main()
