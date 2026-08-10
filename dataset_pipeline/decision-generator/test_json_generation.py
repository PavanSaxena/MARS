#!/usr/bin/env python3
"""
Test script to verify JSON generation fixes.
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.generation_agent import GenerationAgent
from app.llm.client import LLMClient
from app.prompts.builder import PromptBuilder
from app.models.context import GenerationContext

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_json_generation():
    """Test JSON generation with the updated prompt."""
    
    # Initialize components
    llm_client = LLMClient()
    prompt_builder = PromptBuilder()
    generation_agent = GenerationAgent(llm_client, prompt_builder)
    
    # Create test context
    context = GenerationContext(
        company_name="TestCorp",
        quarter=1,
        year=2022,
        source_document="test.pdf",
        context_summary="TestCorp reported strong Q1 2022 results with revenue of $100M, up 15% YoY. The company is considering expansion into new markets while managing operational costs.",
        financial_metrics={
            "revenue": 100000000,
            "growth_rate": 0.15,
            "profit_margin": 0.20
        },
        key_events=["Market expansion opportunity", "Cost optimization initiative"],
        strategic_priorities=["Growth", "Efficiency"]
    )
    
    logger.info("Testing JSON generation with updated prompt...")
    
    # Generate decisions
    decisions = generation_agent.generate_decisions(
        context=context,
        num_decisions=2
    )
    
    if decisions:
        logger.info(f"✓ Successfully generated {len(decisions)} decisions")
        for i, decision in enumerate(decisions, 1):
            logger.info(f"\nDecision {i}:")
            logger.info(f"  Case ID: {decision.case_id}")
            logger.info(f"  Decision: {decision.decision_text[:100]}...")
            logger.info(f"  Chosen: Option {decision.chosen_option}")
            logger.info(f"  Risk: {decision.risk_level}")
    else:
        logger.error("✗ Failed to generate decisions")
        return False
    
    return True


if __name__ == "__main__":
    try:
        success = test_json_generation()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        sys.exit(1)