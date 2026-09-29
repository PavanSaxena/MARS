#!/bin/bash

# ============================================================
# Solution 3 Test Suite
# Model: groq:openai/gpt-oss-120b
# ============================================================

set -u

PASS=0
FAIL=0

API_URL="http://localhost:8000"
MODEL="groq:openai/gpt-oss-120b"
QUERY="Evaluate a product launch that may require regulatory review, significant investment, and supply-chain capacity changes."

API_OUTPUT="/tmp/solution3_api_gpt_oss_120b.json"
OPENAI_OUTPUT="/tmp/solution3_openai_gpt_oss_120b.json"
OPENAI_TEXT="/tmp/solution3_response.md"

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

pass() {
    echo "  ✅ PASS: $1"
    PASS=$((PASS + 1))
}

fail() {
    echo "  ❌ FAIL: $1"
    echo "     Error: $2"
    FAIL=$((FAIL + 1))
}

section() {
    echo
    echo "============================================================"
    echo "$1"
    echo "============================================================"
}

# ------------------------------------------------------------
# 1. Deterministic contrastive partitioning
# ------------------------------------------------------------

section "1. CONTRASTIVE CASE PARTITIONING"

OUTPUT=$(python - <<'PY' 2>&1
from app.agents.common import _format_contrastive_case_context

cases = [
    {
        "metadata": {
            "case_id": "CASE-S",
            "outcome_label": "success"
        },
        "document": "Successful precedent."
    },
    {
        "metadata": {
            "case_id": "CASE-F",
            "outcome_label": "failure"
        },
        "document": "Failure warning."
    },
    {
        "metadata": {
            "case_id": "CASE-M",
            "outcome_label": "mixed"
        },
        "document": "Mixed result."
    },
]

rendered = _format_contrastive_case_context(cases)

expected = [
    "HISTORICAL SUCCESS PRECEDENTS",
    "CASE-S",
    "HISTORICAL FAILURE WARNINGS",
    "CASE-F",
    "MIXED OR UNCERTAIN OUTCOMES",
    "CASE-M",
]

for item in expected:
    assert item in rendered, f"Missing expected text: {item}"

# Verify ordering/section membership.
success_pos = rendered.index("HISTORICAL SUCCESS PRECEDENTS")
failure_pos = rendered.index("HISTORICAL FAILURE WARNINGS")
mixed_pos = rendered.index("MIXED OR UNCERTAIN OUTCOMES")

assert success_pos < rendered.index("CASE-S") < failure_pos, \
    "CASE-S is not inside the SUCCESS section"

assert failure_pos < rendered.index("CASE-F") < mixed_pos, \
    "CASE-F is not inside the FAILURE section"

assert mixed_pos < rendered.index("CASE-M"), \
    "CASE-M is not inside the MIXED section"

print("OK")
PY
)

if echo "$OUTPUT" | grep -q "^OK$"; then
    pass "Cases are partitioned into success/failure/mixed sections"
else
    fail "Contrastive partitioning" "$OUTPUT"
fi


# ------------------------------------------------------------
# 2. Missing outcome_label
# ------------------------------------------------------------

OUTPUT=$(python - <<'PY' 2>&1
from app.agents.common import _format_contrastive_case_context

cases = [
    {
        "metadata": {
            "case_id": "CASE-UNKNOWN"
        },
        "document": "This was a highly successful launch."
    }
]

rendered = _format_contrastive_case_context(cases)

assert "OUTCOME NOT CLASSIFIED" in rendered, \
    "Missing OUTCOME NOT CLASSIFIED section"

assert "CASE-UNKNOWN" in rendered, \
    "CASE-UNKNOWN missing"

# Must not infer outcome from prose - CASE-UNKNOWN should be in
# OUTCOME NOT CLASSIFIED, not in the SUCCESS section.
case_section_start = rendered.index("OUTCOME NOT CLASSIFIED")
case_section_end = len(rendered)  # end of text
# Find the next section header after OUTCOME NOT CLASSIFIED, if any
import re as _re
next_section = _re.search(r"\n=== ", rendered[case_section_start + 1:])
if next_section:
    case_section_end = case_section_start + 1 + next_section.start()
case_section = rendered[case_section_start:case_section_end]
assert "CASE-UNKNOWN" in case_section, \
    "CASE-UNKNOWN not in OUTCOME NOT CLASSIFIED section"
assert "HISTORICAL SUCCESS PRECEDENTS" not in case_section, \
    "Outcome was incorrectly inferred as SUCCESS from prose"

print("OK")
PY
)

if echo "$OUTPUT" | grep -q "^OK$"; then
    pass "Missing outcome_label goes to OUTCOME NOT CLASSIFIED"
else
    fail "Missing outcome_label handling" "$OUTPUT"
fi


# ------------------------------------------------------------
# 3. Backend availability
# ------------------------------------------------------------

section "2. BACKEND / API"

if curl -s --max-time 5 "$API_URL/docs" >/dev/null 2>&1; then
    pass "Backend is reachable at $API_URL"
else
    fail "Backend is unreachable" \
         "Start the backend first, e.g. uvicorn main:app --reload"
fi


# ------------------------------------------------------------
# 4. /api/query
# ------------------------------------------------------------

echo
echo "Testing /api/query with model: $MODEL"

HTTP_RESPONSE=$(curl -s -w "\n%{http_code}" \
    --max-time 180 \
    "$API_URL/api/query" \
    -H 'Content-Type: application/json' \
    -d "{
        \"query\":\"$QUERY\",
        \"thread_id\":\"check-sol3-gpt-oss-120b\"
    }")

HTTP_CODE=$(echo "$HTTP_RESPONSE" | tail -n 1)
BODY=$(echo "$HTTP_RESPONSE" | sed '$d')

echo "$BODY" > "$API_OUTPUT"

if [ "$HTTP_CODE" = "200" ]; then
    pass "/api/query returned HTTP 200"
else
    fail "/api/query HTTP status" \
         "Expected 200, got $HTTP_CODE. Response: $BODY"
fi


# ------------------------------------------------------------
# 5. Validate JSON
# ------------------------------------------------------------

if jq empty "$API_OUTPUT" >/dev/null 2>&1; then
    pass "/api/query returned valid JSON"
else
    fail "API JSON parsing" \
         "Response is not valid JSON"
fi


# ------------------------------------------------------------
# 6. Required API fields
# ------------------------------------------------------------

check_field() {
    FIELD="$1"

    VALUE=$(jq -r "has(\"$FIELD\")" "$API_OUTPUT" 2>/dev/null)

    if [ "$VALUE" = "true" ]; then
        pass "API contains '$FIELD'"
    else
        fail "Missing API field '$FIELD'" \
             "Expected top-level JSON field '$FIELD'"
    fi
}

check_field "key_insights"
check_field "conflicts"
check_field "risk_foresight"
check_field "action_roadmap"
check_field "final_decision"


# ------------------------------------------------------------
# 7. Validate arrays
# ------------------------------------------------------------

TYPE=$(jq -r '.risk_foresight | type' "$API_OUTPUT" 2>/dev/null)

if [ "$TYPE" = "array" ]; then
    pass "'risk_foresight' is an array"
else
    fail "'risk_foresight' type" \
         "Expected array, got $TYPE"
fi

TYPE=$(jq -r '.action_roadmap | type' "$API_OUTPUT" 2>/dev/null)

if [ "$TYPE" = "array" ]; then
    pass "'action_roadmap' is an array"
else
    fail "'action_roadmap' type" \
         "Expected array, got $TYPE"
fi


# ------------------------------------------------------------
# 8. Risk Foresight content
# ------------------------------------------------------------

RISK_COUNT=$(jq '.risk_foresight | length' "$API_OUTPUT" 2>/dev/null)

if [ "$RISK_COUNT" -gt 0 ] 2>/dev/null; then
    pass "Risk Foresight contains at least one risk"
else
    fail "Risk Foresight is empty" \
         "Expected at least one risk"
fi

RISK_TEXT=$(jq -r '.risk_foresight | tostring' "$API_OUTPUT")

if echo "$RISK_TEXT" | grep -Eq 'AAPL-[0-9]{4}Q[1-4]-[0-9]{4}'; then
    pass "Risk Foresight contains case IDs"
else
    fail "Risk Foresight evidence" \
         "No case ID matching AAPL-YYYYQ#-#### found"
fi


# ------------------------------------------------------------
# 9. Action Roadmap content
# ------------------------------------------------------------

ROADMAP_COUNT=$(jq '.action_roadmap | length' "$API_OUTPUT" 2>/dev/null)

if [ "$ROADMAP_COUNT" -gt 0 ] 2>/dev/null; then
    pass "Action Roadmap contains at least one action"
else
    fail "Action Roadmap is empty" \
         "Expected at least one roadmap action"
fi

ROADMAP_TEXT=$(jq -r '.action_roadmap | tostring' "$API_OUTPUT")

if echo "$ROADMAP_TEXT" | grep -Eq 'AAPL-[0-9]{4}Q[1-4]-[0-9]{4}'; then
    pass "Action Roadmap contains case IDs"
else
    fail "Action Roadmap evidence" \
         "No case ID matching AAPL-YYYYQ#-#### found"
fi


# ------------------------------------------------------------
# 10. Conflicts
# ------------------------------------------------------------

CONFLICT_TEXT=$(jq -r '.conflicts | tostring' "$API_OUTPUT")

if [ -n "$CONFLICT_TEXT" ] && [ "$CONFLICT_TEXT" != "null" ]; then
    pass "Conflicts section is populated"
else
    fail "Conflicts section" \
         "No conflict synthesis returned"
fi

if echo "$CONFLICT_TEXT" | grep -Eiq \
    'finance|operations|r&d|legal'; then
    pass "Conflicts reference departments"
else
    fail "Conflict peer departments" \
         "No recognizable department names found"
fi

if echo "$CONFLICT_TEXT" | grep -Eq \
    'AAPL-[0-9]{4}Q[1-4]-[0-9]{4}'; then
    pass "Conflicts contain case IDs"
else
    fail "Conflict evidence" \
         "No case IDs found in conflicts"
fi


# ------------------------------------------------------------
# 11. Check for unresolved / explicit status
# ------------------------------------------------------------

if echo "$CONFLICT_TEXT" | grep -Eiq \
    'unresolved|resolved|no .*concern|no .*objection|no evidence'; then
    pass "Conflicts include explicit resolution/unresolved status"
else
    fail "Conflict resolution status" \
         "Could not find resolved/unresolved/no-concern language"
fi


# ------------------------------------------------------------
# 12. Check for fake inter-agent debate
# ------------------------------------------------------------

FAKE_DEBATE=$(echo "$CONFLICT_TEXT" | grep -Ein \
    'after reviewing|after considering|revised its recommendation|changed its position|responded to|debated with' \
    || true)

if [ -z "$FAKE_DEBATE" ]; then
    pass "No obvious claim that departments debated/revised each other"
else
    fail "Possible fake inter-agent debate" \
         "$FAKE_DEBATE"
fi


# ------------------------------------------------------------
# 13. Check for fabricated implementation details
# ------------------------------------------------------------

FULL_API_TEXT=$(cat "$API_OUTPUT")

if echo "$FULL_API_TEXT" | grep -Eiq \
    'owner:|budget:|assigned to|deadline:'; then
    echo "  ⚠️ WARNING: Possible implementation details detected."
    echo "     Inspect manually; presence alone does not prove hallucination."
else
    pass "No obvious fabricated owner/budget/deadline fields"
fi


# ------------------------------------------------------------
# 14. OpenAI-compatible endpoint
# ------------------------------------------------------------

section "3. OPENAI-COMPATIBLE ROUTE"

HTTP_RESPONSE=$(curl -s -w "\n%{http_code}" \
    --max-time 180 \
    "$API_URL/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d "{
        \"model\":\"$MODEL\",
        \"messages\":[
            {
                \"role\":\"user\",
                \"content\":\"$QUERY\"
            }
        ]
    }")

HTTP_CODE=$(echo "$HTTP_RESPONSE" | tail -n 1)
BODY=$(echo "$HTTP_RESPONSE" | sed '$d')

echo "$BODY" > "$OPENAI_OUTPUT"

if [ "$HTTP_CODE" = "200" ]; then
    pass "/v1/chat/completions returned HTTP 200"
else
    fail "/v1/chat/completions HTTP status" \
         "Expected 200, got $HTTP_CODE. Response: $BODY"
fi


# ------------------------------------------------------------
# 15. OpenAI response parsing
# ------------------------------------------------------------

if jq -e '.choices[0].message.content' "$OPENAI_OUTPUT" \
    >/dev/null 2>&1; then
    pass "OpenAI-compatible response contains message content"
else
    fail "OpenAI response parsing" \
         "Could not find .choices[0].message.content"
fi

jq -r '.choices[0].message.content' \
    "$OPENAI_OUTPUT" > "$OPENAI_TEXT"


# ------------------------------------------------------------
# 16. Required markdown sections
# ------------------------------------------------------------

if grep -Fq "Risk Foresight" "$OPENAI_TEXT"; then
    pass "OpenAI markdown contains 'Risk Foresight'"
else
    fail "Missing Risk Foresight heading" \
         "Expected 'Risk Foresight' in generated markdown"
fi

if grep -Fq "Recommended Strategic Plan & Action Roadmap" "$OPENAI_TEXT"; then
    pass "OpenAI markdown contains 'Recommended Strategic Plan & Action Roadmap'"
else
    fail "Missing Action Roadmap heading" \
         "Expected 'Recommended Strategic Plan & Action Roadmap'"
fi


# ------------------------------------------------------------
# 17. Check response completeness
# ------------------------------------------------------------

LAST_LINES=$(tail -10 "$OPENAI_TEXT")

if echo "$LAST_LINES" | grep -Eq \
    '^[^[:space:]].*[.!?]$|^\s*[-*] .*[.!?]$|^\s*[0-9]+\..*[.!?]$'; then
    pass "OpenAI response appears to end naturally"
else
    fail "Possible truncated OpenAI response" \
         "Final lines do not appear to end naturally"
fi


# ------------------------------------------------------------
# 18. Benchmark
# ------------------------------------------------------------

section "4. GENERATION BENCHMARK"

echo "Running:"
echo "python evaluation/run_benchmark.py --mode generation --sample-size 40"
echo
echo "Model expected: $MODEL"
echo

cd ..

BENCHMARK_OUTPUT=$(python evaluation/run_benchmark.py \
    --mode generation \
    --sample-size 40 2>&1)

BENCHMARK_STATUS=$?

echo "$BENCHMARK_OUTPUT"

if [ "$BENCHMARK_STATUS" -eq 0 ]; then
    pass "Generation benchmark completed successfully"
else
    fail "Generation benchmark" \
         "Benchmark exited with code $BENCHMARK_STATUS"
fi


# ------------------------------------------------------------
# Final summary
# ------------------------------------------------------------

section "FINAL RESULT"

echo
echo "Model: $MODEL"
echo "Query: $QUERY"
echo
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo

if [ "$FAIL" -eq 0 ]; then
    echo "🎉 OVERALL: PASS"
    echo
    echo "All automated checks passed."
    exit 0
else
    echo "❌ OVERALL: FAIL"
    echo
    echo "$FAIL automated check(s) failed."
    echo
    echo "Saved responses:"
    echo "  API:    $API_OUTPUT"
    echo "  OpenAI: $OPENAI_OUTPUT"
    echo "  Text:   $OPENAI_TEXT"
    exit 1
fi
