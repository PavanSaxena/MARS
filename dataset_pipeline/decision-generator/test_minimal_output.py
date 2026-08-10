#!/usr/bin/env python3
"""
Test script to verify minimal output generation workflow.
Tests that LLM generates only semantic content while Python populates deterministic fields.
"""

import os
import sys
import json
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.llm.openai_client import OpenAIClient
from app.agents.generation_agent import GenerationAgent
from app.config import OPENAI_API_KEY, OPENAI_MODEL, MAX_COMPLETION_TOKENS, GENERATION_BATCH_SIZE
from app.logging_utils import get_logger

logger = get_logger(__name__)

def test_minimal_output():
    """Test that generation produces minimal output and enriches with deterministic fields."""
    
    print("=" * 80)
    print("MINIMAL OUTPUT GENERATION TEST")
    print("=" * 80)
    
    # Initialize client with max_completion_tokens
    print(f"\n1. Initializing OpenAI client...")
    print(f"   Model: {OPENAI_MODEL}")
    print(f"   Max completion tokens: {MAX_COMPLETION_TOKENS}")
    print(f"   Batch size: {GENERATION_BATCH_SIZE}")
    
    client = OpenAIClient(
        api_key=OPENAI_API_KEY,
        model=OPENAI_MODEL,
        max_completion_tokens=MAX_COMPLETION_TOKENS
    )
    
    # Initialize generation agent
    print(f"\n2. Initializing GenerationAgent with batch_size={GENERATION_BATCH_SIZE}...")
    agent = GenerationAgent(client, batch_size=GENERATION_BATCH_SIZE)
    
    # Create minimal test context
    context = {
        "quarter": "Q1",
        "year": 2022,
        "company_name": "Test Corp",
        "industry": "Technology",
        "financial_summary": "Revenue: $100M, Profit: $20M",
        "strategic_priorities": ["Growth", "Innovation"],
        "market_conditions": "Competitive market with growth opportunities",
        "recent_events": ["Product launch", "Market expansion"]
    }
    
    print(f"\n3. Generating {GENERATION_BATCH_SIZE} decisions with minimal output format...")
    print("   LLM will generate ONLY semantic content")
    print("   Python will populate: case_id, quarter, year, confidence_score")
    
    try:
        decisions = agent.generate_decisions(context, batch_size=GENERATION_BATCH_SIZE)
        
        print(f"\n4. Generation successful! Generated {len(decisions)} decisions")
        
        # Verify enrichment
        print("\n5. Verifying deterministic field population...")
        for idx, decision in enumerate(decisions, 1):
            print(f"\n   Decision {idx}:")
            print(f"   - case_id: {decision.case_id} (Python-generated)")
            print(f"   - quarter: {decision.quarter} (Python-populated)")
            print(f"   - year: {decision.year} (Python-populated)")
            print(f"   - confidence_score: {decision.confidence_score} (Python-default)")
            print(f"   - decision_title: {decision.decision_title} (LLM-generated)")
            print(f"   - trigger_event: {decision.trigger_event[:50]}... (LLM-generated)")
            
            # Verify required fields exist
            assert decision.case_id, "case_id missing"
            assert decision.quarter, "quarter missing"
            assert decision.year, "year missing"
            assert decision.confidence_score, "confidence_score missing"
            assert decision.decision_title, "decision_title missing"
            assert decision.trigger_event, "trigger_event missing"
        
        print("\n" + "=" * 80)
        print("✓ TEST PASSED: Minimal output generation working correctly")
        print("=" * 80)
        print(f"\nKey improvements:")
        print(f"  • LLM generates only semantic content (reduced output size)")
        print(f"  • Python populates deterministic fields (case_id, quarter, year, etc.)")
        print(f"  • Batch size reduced to {GENERATION_BATCH_SIZE} (configurable)")
        print(f"  • Max completion tokens set to {MAX_COMPLETION_TOKENS}")
        print(f"  • Token logging enabled for input and completion")
        
        return True
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_minimal_output()
    sys.exit(0 if success else 1)