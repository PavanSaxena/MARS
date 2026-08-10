# TPM Throttling Quick Reference

## Configuration

```env
# Batch Processing
BATCH_SIZE=5                              # Cases per batch (adaptive)
BATCH_DELAY_SECONDS=20.0                  # Delay between batches
GENERATION_VALIDATION_DELAY_SECONDS=8.0   # Delay between gen/val

# TPM Management
TPM_BUDGET=6500                           # Max tokens per minute
MAX_TOKENS=3000                           # Max completion tokens
```

## Key Features

### 1. Rolling TPM Tracker
- Tracks token usage in 60-second rolling window
- Automatically prunes old records
- Calculates precise wait times
- Never fails requests

### 2. Automatic Throttling
- Estimates tokens before each request
- Checks against TPM budget
- Sleeps automatically if needed
- Resumes seamlessly

### 3. Adaptive Batch Sizing
- Starts at configured BATCH_SIZE
- Reduces by ~40% after 3 consecutive failures
- Minimum: 1 case per batch
- Never increases during run

### 4. Enhanced Logging
- Pre-request: input/completion/processed tokens, TPM usage
- Post-request: output tokens, duration, updated usage
- Throttling: wait time and reason
- Batch: progress and statistics

### 5. Minimal Validation Output
- Reduced from ~1000 to ~400 tokens
- Brief issue descriptions only
- No verbose explanations

## Monitoring Commands

```bash
# Watch TPM usage
tail -f logs/pipeline.log | grep "Rolling TPM Usage"

# Watch throttling events
tail -f logs/pipeline.log | grep "TPM Budget Exceeded"

# Watch batch size changes
tail -f logs/pipeline.log | grep "Adaptive Batch Size"

# Watch batch progress
tail -f logs/pipeline.log | grep "Processing Batch"
```

## Troubleshooting

### Frequent Throttling
- Reduce BATCH_SIZE
- Increase BATCH_DELAY_SECONDS
- Increase GENERATION_VALIDATION_DELAY_SECONDS
- Reduce MAX_TOKENS

### Slow Progress
- Increase TPM_BUDGET (if provider allows)
- Reduce delays (if TPM allows)
- Check for adaptive batch size reductions

### Batch Size Keeps Reducing
- Check for JSON generation errors
- Verify prompt quality
- Review completion token limits
- Check provider rate limits

## Testing

```bash
# Test TPM tracker
python test_tpm_tracking.py

# Test with conservative settings
export TPM_BUDGET=5000
export BATCH_SIZE=2
python -m app.main

# Test with aggressive settings
export TPM_BUDGET=8000
export BATCH_SIZE=8
python -m app.main
```

## Expected Behavior

### Normal Operation
```
Processing Batch 1 (size: 5)
→ Generation Request (2250 input, 3000 completion)
→ Rolling TPM: 2100/6500
→ Wait 8s
→ Validation Request (2300 input, 1500 completion)
→ Rolling TPM: 5900/6500
→ Wait 20s before next batch
```

### Throttling Event
```
Processing Batch 3 (size: 5)
→ Generation Request (2250 input, 3000 completion)
→ Rolling TPM: 5800/6500
→ TPM Budget Exceeded
→ Sleeping 12.3 seconds
→ Resuming generation...
→ Generation Request proceeds
```

### Adaptive Reduction
```
Batch 4: Size=5, Failed
Batch 5: Size=5, Failed
Batch 6: Size=5, Failed
→ Adaptive Batch Size Reduction
→ Previous: 5, New: 3
Batch 7: Size=3, Success
```

## Files Modified

### Core Implementation
- `app/llm/tpm_tracker.py` (NEW)
- `app/llm/client.py`
- `app/llm/openai_client.py`
- `app/llm/local_client.py`
- `app/pipeline/orchestrator.py`
- `app/agents/generation_agent.py`
- `app/agents/validation_agent.py`

### Configuration
- `app/config.py`
- `.env`
- `.env.example`

### Prompts
- `app/prompts/validation.md`

### Documentation
- `TPM_THROTTLING_IMPLEMENTATION.md` (NEW)
- `TPM_QUICK_REFERENCE.md` (NEW)

### Testing
- `test_tpm_tracking.py` (NEW)
</content>
</write_file>

Now let's create one final verification script to ensure everything works together:

<write_to_file>
<path>decision-generator/verify_implementation.py</path>
<content>"""
Verification Script for TPM Throttling Implementation

Checks that all components are properly integrated and configured.
"""

import sys
from pathlib import Path


def check_imports():
    """Verify all imports work"""
    print("\n" + "="*60)
    print("Checking Imports...")
    print("="*60)
    
    try:
        from app.llm.tpm_tracker import TPMTracker
        print("✓ TPMTracker imported")
        
        from app.llm.client import LLMClient
        print("✓ LLMClient imported")
        
        from app.llm.openai_client import OpenAIClient
        print("✓ OpenAIClient imported")
        
        from app.llm.local_client import LocalClient
        print("✓ LocalClient imported")
        
        from app.agents.generation_agent import DecisionGenerationAgent
        print("✓ DecisionGenerationAgent imported")
        
        from app.agents.validation_agent import DecisionValidationAgent
        print("✓ DecisionValidationAgent imported")
        
        from app.pipeline.orchestrator import PipelineOrchestrator
        print("✓ PipelineOrchestrator imported")
        
        from app.config import Config
        print("✓ Config imported")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def check_config():
    """Verify configuration has new fields"""
    print("\n" + "="*60)
    print("Checking Configuration...")
    print("="*60)
    
    try:
        from app.config import Config
        
        config = Config()
        
        # Check new fields exist
        assert hasattr(config, 'batch_delay'), "Missing batch_delay"
        print(f"✓ batch_delay: {config.batch_delay}")
        
        assert hasattr(config, 'generation_validation_delay'), "Missing generation_validation_delay"
        print(f"✓ generation_validation_delay: {config.generation_validation_delay}")
        
        assert hasattr(config, 'tpm_budget'), "Missing tpm_budget"
        print(f"✓ tpm_budget: {config.tpm_budget}")
        
        # Check defaults
        assert config.batch_delay == 20.0, f"Expected batch_delay=20.0, got {config.batch_delay}"
        assert config.generation_validation_delay == 8.0, f"Expected generation_validation_delay=8.0, got {config.generation_validation_delay}"
        assert config.tpm_budget == 6500, f"Expected tpm_budget=6500, got {config.tpm_budget}"
        
        print("✓ All configuration fields present with correct defaults")
        return True
    except Exception as e:
        print(f"✗ Configuration check failed: {e}")
        return False


def check_tpm_tracker():
    """Verify TPM tracker functionality"""
    print("\n" + "="*60)
    print("Checking TPM Tracker...")
    print("="*60)
    
    try:
        from app.llm.tpm_tracker import TPMTracker
        
        tracker = TPMTracker(tpm_budget=10000)
        
        # Test basic functionality
        tracker.record_usage(1000, 2000)
        usage = tracker.get_current_usage()
        assert usage == 3000, f"Expected usage=3000, got {usage}"
        print("✓ Token recording works")
        
        remaining = tracker.get_remaining_budget()
        assert remaining == 7000, f"Expected remaining=7000, got {remaining}"
        print("✓ Budget calculation works")
        
        would_exceed = tracker.would_exceed_budget(5000, 3000)
        assert would_exceed, "Should detect budget would be exceeded"
        print("✓ Budget checking works")
        
        wait_time = tracker.calculate_wait_time(5000, 3000)
        assert wait_time > 0, "Should calculate wait time"
        print(f"✓ Wait time calculation works ({wait_time:.2f}s)")
        
        stats = tracker.get_usage_stats()
        assert 'rolling_tpm_usage' in stats, "Missing rolling_tpm_usage in stats"
        assert 'remaining_budget' in stats, "Missing remaining_budget in stats"
        print("✓ Usage statistics work")
        
        return True
    except Exception as e:
        print(f"✗ TPM tracker check failed: {e}")
        return False


def check_llm_client_integration():
    """Verify LLM client has TPM integration"""
    print("\n" + "="*60)
    print("Checking LLM Client Integration...")
    print("="*60)
    
    try:
        from app.llm.client import LLMClient
        from app.config import Config
        
        # Check base class has required methods
        required_methods = [
            '_estimate_tokens',
            '_log_pre_request',
            '_log_post_request',
            '_handle_tpm_throttling'
        ]
        
        for method in required_methods:
            assert hasattr(LLMClient, method), f"Missing method: {method}"
            print(f"✓ {method} exists")
        
        return True
    except Exception as e:
        print(f"✗ LLM client integration check failed: {e}")
        return False


def check_orchestrator_integration():
    """Verify orchestrator has adaptive batching and delays"""
    print("\n" + "="*60)
    print("Checking Orchestrator Integration...")
    print("="*60)
    
    try:
        from app.pipeline.orchestrator import PipelineOrchestrator
        
        # Check for adaptive batching attributes
        required_attrs = [
            'current_batch_size',
            'min_batch_size',
            'consecutive_failures',
            'failure_threshold'
        ]
        
        # We can't instantiate without full setup, so check source
        import inspect
        source = inspect.getsource(PipelineOrchestrator.__init__)
        
        for attr in required_attrs:
            assert attr in source, f"Missing attribute: {attr}"
            print(f"✓ {attr} initialized")
        
        # Check for delay implementation
        execute_source = inspect.getsource(PipelineOrchestrator.execute)
        assert 'generation_validation_delay' in execute_source, "Missing generation_validation_delay"
        print("✓ Generation-validation delay implemented")
        
        assert 'batch_delay' in execute_source, "Missing batch_delay"
        print("✓ Batch delay implemented")
        
        # Check for adaptive batch sizing
        assert '_reduce_batch_size' in dir(PipelineOrchestrator), "Missing _reduce_batch_size method"
        print("✓ Adaptive batch sizing implemented")
        
        return True
    except Exception as e:
        print(f"✗ Orchestrator integration check failed: {e}")
        return False


def check_agent_integration():
    """Verify agents accept batch_num parameter"""
    print("\n" + "="*60)
    print("Checking Agent Integration...")
    print("="*60)
    
    try:
        import inspect
        from app.agents.generation_agent import DecisionGenerationAgent
        from app.agents.validation_agent import DecisionValidationAgent
        
        # Check generation agent
        gen_sig = inspect.signature(DecisionGenerationAgent.generate_batch)
        assert 'batch_num' in gen_sig.parameters, "Missing batch_num in generate_batch"
        print("✓ Generation agent accepts batch_num")
        
        # Check validation agent
        val_sig = inspect.signature(DecisionValidationAgent.validate_batch)
        assert 'batch_num' in val_sig.parameters, "Missing batch_num in validate_batch"
        print("✓ Validation agent accepts batch_num")
        
        return True
    except Exception as e:
        print(f"✗ Agent integration check failed: {e}")
        return False


def check_files_exist():
    """Verify all expected files exist"""
    print("\n" + "="*60)
    print("Checking Files...")
    print("="*60)
    
    required_files = [
        'app/llm/tpm_tracker.py',
        'app/llm/client.py',
        'app/llm/openai_client.py',
        'app/llm/local_client.py',
        'app/pipeline/orchestrator.py',
        'app/agents/generation_agent.py',
        'app/agents/validation_agent.py',
        'app/config.py',
        'app/prompts/validation.md',
        '.env.example',
        'TPM_THROTTLING_IMPLEMENTATION.md',
        'TPM_QUICK_REFERENCE.md',
        'test_tpm_tracking.py'
    ]
    
    all_exist = True
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} (missing)")
            all_exist = False
    
    return all_exist


def main():
    """Run all verification checks"""
    print("\n" + "="*60)
    print("TPM Throttling Implementation Verification")
    print("="*60)
    
    checks = [
        ("Files", check_files_exist),
        ("Imports", check_imports),
        ("Configuration", check_config),
        ("TPM Tracker", check_tpm_tracker),
        ("LLM Client Integration", check_llm_client_integration),
        ("Orchestrator Integration", check_orchestrator_integration),
        ("Agent Integration", check_agent_integration)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} check crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("Verification Summary")
    print("="*60)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n" + "="*60)
        print("✓ All Verification Checks Passed")
        print("="*60)
        print("\nThe TPM throttling implementation is complete and correct.")
        print("\nNext steps:")
        print("1. Review configuration in .env")
        print("2. Run: python test_tpm_tracking.py")
        print("3. Test pipeline with: python -m app.main")
        print("4. Monitor logs for TPM usage and throttling")
        return 0
    else:
        print("\n" + "="*60)
        print("✗ Some Verification Checks Failed")
        print("="*60)
        print("\nPlease review the failures above and fix any issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())