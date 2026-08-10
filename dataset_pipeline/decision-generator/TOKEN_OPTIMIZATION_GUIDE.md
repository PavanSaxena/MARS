# Token Optimization Guide

## Overview

The pipeline now uses a minimal output approach to prevent completion token limit errors and optimize generation speed.

## Key Concepts

### Separation of Concerns

**LLM Responsibility (Semantic Content):**
- Decision titles and descriptions
- Reasoning and analysis
- Options and impacts
- Strategic insights

**Python Responsibility (Deterministic Fields):**
- Unique identifiers (case_id)
- Temporal metadata (quarter, year)
- Default values (confidence_score)
- Schema compliance

## Configuration

### Batch Size

Controls how many decisions are generated per LLM call:

```python
GENERATION_BATCH_SIZE = 2  # Default
```

**Guidelines:**
- `1`: Maximum safety, minimal output per call
- `2`: Balanced (recommended default)
- `3-5`: Higher throughput, requires more completion tokens

**When to adjust:**
- Reduce to `1` if hitting token limits
- Increase to `3-5` if using powerful models (GPT-4, Claude Opus)

### Completion Token Limit

Maximum tokens the LLM can generate:

```python
MAX_COMPLETION_TOKENS = 4000  # Default
```

**Guidelines:**
- `2000-4000`: Safe for most models
- `4000-8000`: For powerful models with large context windows
- `8000+`: For specialized use cases

**Model-specific recommendations:**
- GPT-4o-mini: 4000 tokens
- GPT-4o: 8000 tokens
- GPT-4: 8000 tokens
- Claude 3.5 Sonnet: 8000 tokens

## Token Logging

Every LLM request logs token usage:

```
LLM Request - Input tokens: 1234 (system: 456, user: 778), Max completion tokens: 4000
LLM Response - Completion tokens used: 2345/4000
```

**What to monitor:**
1. **Input tokens**: Should stay under model's context window
2. **Completion tokens used**: Should stay well below max (< 80%)
3. **Ratio**: If completion tokens consistently near max, reduce batch size

## Optimization Strategies

### Strategy 1: Reduce Batch Size

If you see completion tokens approaching the limit:

```python
# Before
GENERATION_BATCH_SIZE = 5
# Completion tokens: 3800/4000 (95% - too close!)

# After
GENERATION_BATCH_SIZE = 2
# Completion tokens: 1800/4000 (45% - safe)
```

### Strategy 2: Increase Token Limit

If using a powerful model with room to spare:

```python
# Before
MAX_COMPLETION_TOKENS = 4000
GENERATION_BATCH_SIZE = 2

# After (for GPT-4)
MAX_COMPLETION_TOKENS = 8000
GENERATION_BATCH_SIZE = 3
```

### Strategy 3: Optimize Context

Reduce input token usage to allow more completion tokens:

```python
# In context builder
context = {
    "quarter": "Q1",
    "year": 2022,
    # Include only essential context
    "financial_summary": "Brief summary",  # Not full details
    "strategic_priorities": ["Top 3 only"],  # Not exhaustive list
}
```

## Troubleshooting

### Error: "Maximum completion tokens reached"

**Symptoms:**
- Incomplete JSON in response
- Parsing errors
- Truncated decisions

**Solutions:**
1. Reduce `GENERATION_BATCH_SIZE` to 1
2. Increase `MAX_COMPLETION_TOKENS` if model supports it
3. Simplify context to reduce input tokens

### Warning: "Completion tokens used: 3900/4000"

**Symptoms:**
- Token usage consistently > 90% of limit
- Risk of hitting limit

**Solutions:**
1. Reduce `GENERATION_BATCH_SIZE` by 1
2. Monitor for a few runs
3. Adjust further if needed

### Info: "Completion tokens used: 800/4000"

**Symptoms:**
- Token usage consistently < 30% of limit
- Underutilizing model capacity

**Solutions:**
1. Increase `GENERATION_BATCH_SIZE` by 1
2. Monitor for a few runs
3. Optimize for throughput

## Best Practices

1. **Start Conservative**: Begin with batch_size=2, max_tokens=4000
2. **Monitor Logs**: Watch token usage for first few runs
3. **Adjust Gradually**: Change one parameter at a time
4. **Test Thoroughly**: Verify JSON parsing after changes
5. **Document Settings**: Note optimal settings for your use case

## Example Configurations

### Conservative (Maximum Safety)
```python
GENERATION_BATCH_SIZE = 1
MAX_COMPLETION_TOKENS = 2000
```
Use when: First time setup, unreliable model, limited context window

### Balanced (Recommended)
```python
GENERATION_BATCH_SIZE = 2
MAX_COMPLETION_TOKENS = 4000
```
Use when: Standard operation, GPT-4o-mini, moderate context

### Aggressive (Maximum Throughput)
```python
GENERATION_BATCH_SIZE = 5
MAX_COMPLETION_TOKENS = 8000
```
Use when: Powerful model (GPT-4), large context window, proven stability

## Monitoring Commands

Check token usage in logs:
```bash
# View recent token usage
grep "LLM Request" decision-generator/logs/pipeline.log | tail -10
grep "LLM Response" decision-generator/logs/pipeline.log | tail -10

# Calculate average completion token usage
grep "Completion tokens used" decision-generator/logs/pipeline.log | \
  awk -F'[:/]' '{sum+=$2; count++} END {print "Average:", sum/count, "tokens"}'
```

## Further Reading

- [MINIMAL_OUTPUT_REFACTORING.md](MINIMAL_OUTPUT_REFACTORING.md) - Technical details
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - General pipeline reference
- OpenAI Token Limits: https://platform.openai.com/docs/models