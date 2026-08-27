# Decision Case Repair

You are repairing specific fields in decision cases that failed validation.

## Task

Fix only the flagged fields in the provided cases. Return patches for the specific cases and fields that need repair.

## Output Format

**CRITICAL**: Return ONLY a valid JSON object. Do not include any explanatory text, markdown formatting, or commentary.

Your response must be a single JSON object with this exact structure:

```json
{
  "patches": [
    {
      "case_id": 1,
      "fields": {
        "decision_title": "improved title",
        "reasoning_summary": "improved reasoning"
      }
    }
  ]
}
```

## Current Cases

{{current_cases}}

## Validation Feedback

{{feedback}}

## Feedback by Case

{{feedback_by_case}}

## Requirements

1. **JSON Only**: Your entire response must be valid JSON. No text before or after.
2. **Patch Format**: Use the exact structure shown above.
3. **Only Fix Flagged Fields**: Only include fields that need changes.
4. **Address All Feedback**: Fix all issues mentioned in the feedback.
5. **Maintain Consistency**: Keep the same style and tone as the original.

## Enterprise Context

{{context}}

## Response

Return only the JSON object with the "patches" array. No other text.