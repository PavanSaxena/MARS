#!/usr/bin/env python3
"""
Test JSON parsing and repair logic.
"""

import json
import logging
from app.agents.generation_agent import DecisionGenerationAgent
from app.llm.client import LLMClient
from app.prompts.builder import PromptBuilder
from pathlib import Path

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_json_parsing():
    """Test JSON parsing with various formats."""
    
    llm_client = LLMClient()
    prompt_builder = PromptBuilder(Path(__file__).parent / "app" / "prompts")
    agent = DecisionGenerationAgent(llm_client, prompt_builder)
    
    # Test cases
    test_cases = [
        # Valid JSON
        ('{"cases": [{"decision_text": "test"}]}', True, "Valid JSON"),
        
        # JSON in markdown
        ('```json\n{"cases": [{"decision_text": "test"}]}\n```', True, "JSON in markdown"),
        
        # JSON with text before
        ('Here is the JSON:\n{"cases": [{"decision_text": "test"}]}', True, "JSON with prefix text"),
        
        # Invalid JSON
        ('{"cases": [{"decision_text": "test"', False, "Incomplete JSON"),
    ]
    
    for response, should_succeed, description in test_cases:
        logger.info(f"\nTesting: {description}")
        logger.info(f"Input: {response[:50]}...")
        
        result = agent._load_json_payload(response)
        
        if should_succeed:
            if result:
                logger.info(f"✓ Successfully parsed: {result}")
            else:
                logger.error(f"✗ Failed to parse (expected success)")
        else:
            if result:
                logger.warning(f"⚠ Unexpectedly parsed: {result}")
            else:
                logger.info(f"✓ Correctly failed to parse")
    
    logger.info("\n" + "="*50)
    logger.info("JSON parsing tests complete")

if __name__ == "__main__":
    test_json_parsing()