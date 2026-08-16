# Decision Case Generation

You are an expert at extracting enterprise decision cases from financial documents.

## Task

Generate {{requested_cases}} decision cases based on the provided enterprise context.

## Output Format

**CRITICAL**: Return ONLY a valid JSON object. Do not include any explanatory text, markdown formatting, or commentary before or after the JSON.

Your response must be a single JSON object with this exact structure:

```json
{
  "cases": [
    {
      "source_excerpt": "string - exact quote from source material",
      "department": "string - one of: Finance, Legal, Operations, R&D",
      "decision_title": "string - clear, specific title",
      "decision_archetype": "string - type of decision",
      "trigger": "string - what prompted this decision",
      "decision_description": "string - detailed description",
      "options": [
        {"label": "Proceed", "summary": "description"},
        {"label": "Pause", "summary": "description"},
        {"label": "Revise", "summary": "description"}
      ],
      "chosen_option": "string - one of the option labels",
      "reasoning_summary": "string - why this option was chosen",
      "quantitative_signals": "string - relevant metrics or numbers",
      "risk_level": "string - one of: Low, Medium, High",
      "cross_dept_impact": ["Finance", "Operations"],
      "expected_profit_impact": "string - impact description",
      "profit_impact_pathway": "string - how it affects profit",
      "outcome_status": "string - current status",
      "outcome_summary": "string - expected or actual outcome",
      "decision_tags": ["tag1", "tag2", "tag3"],
      "conflicting_perspectives": "string - different viewpoints",
      "master_agent_decision": "string - final decision"
    }
  ]
}
```

## Requirements

1. **JSON Only**: Your entire response must be valid JSON. No text before or after.
2. **All Fields Required**: Every case must include all fields listed above.
3. **Valid Values**: Use only allowed values for department, risk_level, and chosen_option.
4. **Three Options**: Always provide exactly three options (Proceed, Pause, Revise).
5. **Realistic Content**: Base decisions on the provided enterprise context.
6. **No Placeholders**: Avoid generic phrases like "potential positive impact" or "derived from context".

## Enterprise Context

{{context}}

## Previous Cases

{{previous_cases}}

{% if feedback %}
## Feedback from Previous Attempt

{{feedback}}

Address these issues in your generation.
{% endif %}

## Response

Return only the JSON object with the "cases" array. No other text.