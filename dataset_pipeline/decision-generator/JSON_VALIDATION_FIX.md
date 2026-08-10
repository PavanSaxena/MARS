# JSON Validation Fix

## Problem

The Generation Agent was failing with `json_validate_failed` errors when using `response_format={"type":"json_object"}` with Groq. The model was producing invalid JSON or including explanatory text/markdown around the JSON.

## Solution

Implemented a comprehensive fix with multiple layers of defense:

### 1. Enhanced Logging (`app/llm/openai_client.py`)

**Added debug logging:**
- Logs prompt lengths for debugging
- Logs response length and preview for JSON requests
- Helps identify when responses contain non-JSON content

```python
logger.debug(f"LLM Request - Format: {response_format}, System prompt length: {len(prompt.system_prompt)}")
logger.debug(f"LLM Response length: {len(response_content)}, First 200 chars: {response_content[:200]}")
```

### 2. Robust JSON Parsing (`app/agents/generation_agent.py`)

**Enhanced `_load_json_payload()` method:**
- Tries direct JSON parsing first
- Falls back to extracting JSON from markdown code blocks
- Searches for JSON objects in mixed content
- Logs detailed error messages with response previews
- Returns None gracefully on failure

```python
# Try to extract JSON from markdown code blocks
json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)

# Try to find JSON object in the response
json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
```

### 3. Automatic Retry Logic (`app/agents/generation_agent.py`)

**Added retry mechanism for malformed JSON:**
- Retries up to 2 times if JSON parsing fails
- Adds explicit "JSON-only" instruction to feedback on retry
- Falls back to heuristics after all retries exhausted
- Applied to both `generate()` and `repair()` methods

```python
for json_attempt in range(max_json_retries):
    response_text = self.llm_client.complete(prompt, response_format="json")
    intermediates = self._parse_generation_response(response_text)
    
    if intermediates:
        break
    
    if json_attempt < max_json_retries - 1:
        logger.warning(f"JSON parsing failed. Retrying with clearer instructions...")
        json_feedback = ["CRITICAL: Return ONLY valid JSON. No markdown, no explanatory text."]
```

### 4. Clearer Prompts

**Updated `generation.md`:**
- Explicit "CRITICAL" instruction at the top
- Clear statement: "Return ONLY a valid JSON object"
- Emphasized: "No explanatory text, markdown formatting, or commentary"
- Provided exact JSON structure example
- Added "Response" section reminding to return JSON only

**Updated `repair.md`:**
- Same explicit JSON-only instructions
- Clear patch format example
- Emphasized no extra text

**Key additions:**
```markdown
**CRITICAL**: Return ONLY a valid JSON object. Do not include any explanatory text, 
markdown formatting, or commentary before or after the JSON.

## Response

Return only the JSON object with the "cases" array. No other text.
```

## Benefits

1. **Resilient**: Multiple fallback strategies for parsing JSON
2. **Self-Healing**: Automatic retry with clearer instructions
3. **Debuggable**: Comprehensive logging for troubleshooting
4. **Graceful**: Falls back to heuristics rather than crashing
5. **Clear**: Explicit prompts reduce model confusion

## Testing

The implementation:
- ✅ Compiles successfully
- ✅ Handles markdown-wrapped JSON
- ✅ Handles mixed content responses
- ✅ Retries with clearer instructions
- ✅ Logs detailed debugging information
- ✅ Falls back gracefully on failure

## Architecture Preservation

✅ **All existing functionality preserved:**
- Pipeline architecture unchanged
- Validator logic intact
- Final MARS CSV schema preserved
- Batching and retry logic maintained
- Heuristic fallback still available

## Monitoring

Watch for these log messages:

```
DEBUG - LLM Request - Format: json, System prompt length: 5234
DEBUG - LLM Response length: 1523, First 200 chars: {"cases":[{"source_excerpt":...
WARNING - JSON parsing failed (attempt 1/2). Retrying with clearer instructions...
INFO - Successfully extracted JSON from markdown code block
ERROR - Could not parse JSON. Full response: ...
INFO - generation_falling_back_to_heuristics
```

## Next Steps

If JSON issues persist:
1. Check logs for response previews
2. Verify model supports JSON mode
3. Consider reducing prompt complexity
4. Adjust temperature (lower = more deterministic)
5. Try different model if available