import logging
from typing import Any, Dict, List, Tuple

from app.agents.common import get_llm
from app.state import State

logger = logging.getLogger(__name__)

def _confidence_value(output: dict) -> float:
    """Self-reported LLM confidence, used for ranking until case_based_confidence is finalized."""
    value = (output or {}).get("confidence")
    return value if isinstance(value, (int, float)) else 0.0


def _fmt_department(name: str, output: dict) -> str:
    if not output:
        return f"--- {name} Assessment ---\nNo input received."

    case_based_confidence = output.get("case_based_confidence")
    case_based_text = (
        f"{case_based_confidence:.2f}"
        if isinstance(case_based_confidence, (int, float))
        else "not yet available (placeholder — scoring formula still in progress)"
    )

    return (
        f"--- {name} Assessment ---\n"
        f"Response: {output.get('response', 'N/A')}\n"
        f"Reasoning: {output.get('reasoning', 'N/A')}\n"
        f"Reported Confidence: {_confidence_value(output):.2f}\n"
        f"Cases Retrieved: {output.get('num_cases_retrieved', 'N/A')}\n"
        f"Case-Based Confidence: {case_based_text}"
    )


def aggregator_agent(state: State) -> Dict:
    """
    Aggregator Agent:
    - Collects outputs from all four department agents
    - Ranks departments by their reported confidence (highest first), since
      the dedicated multi-factor case_based_confidence score is still a
      placeholder (see app.reasoning.confidence) and not yet reliable
    - Falls back to a fixed priority order (Legal > Finance > Operations > R&D)
      only as a tiebreaker when confidence levels are close / conflicting
    - Produces a final actionable strategic decision plus a per-department
      explainability trail
    """
    logger.info("aggregator_started")
    departments: List[Tuple[str, dict]] = [
        ("Finance", state.get("finance_output") or {}),
        ("R&D", state.get("rd_output") or {}),
        ("Legal", state.get("legal_output") or {}),
        ("Operations", state.get("operations_output") or {}),
    ]

    # Rank by reported confidence, highest first, so the master agent sees
    # which department to weight more heavily.
    ranked = sorted(departments, key=lambda item: _confidence_value(item[1]), reverse=True)
    ranked_summary = "\n".join(
        f"{i+1}. {name} (confidence: {_confidence_value(output):.2f})"
        for i, (name, output) in enumerate(ranked)
        if output
    ) or "No department outputs available."
    logger.info("aggregator_ranking ranking=%s", ranked_summary)
    assessments_block = "\n\n".join(_fmt_department(name, output) for name, output in departments)

    prompt = f"""
You are a Strategic Decision-Making AI.

You have received assessments from four department agents. Your task is to synthesize
them into a single, coherent, actionable final plan.

Departments Ranked by Reported Confidence (highest first):
{ranked_summary}

Note: each department also has a "case-based confidence" score intended to combine
similarity, recency, and historical success — this metric is still under research and
is currently a placeholder (not meaningful yet). Base your weighting on "Reported
Confidence" for now.

{assessments_block}

Instructions:
1. Identify key recommendations and agreements across departments
2. Detect any conflicts between departments
3. Weight each department's input using its reported confidence above.
   If confidence levels are close or a genuine conflict remains, break the
   tie using this priority order: Legal compliance > Financial feasibility >
   Operational practicality > R&D innovation potential
4. Produce a final actionable plan

Output Format (STRICT):
Key Insights:
<bullet points of the most important findings>

Conflicts:
<any conflicts between departments, or "None detected">

Final Decision:
<the recommended course of action>
"""

    logger.info("aggregator_llm_started")
    try:
        response = get_llm(state.get("model")).invoke(prompt)
    except Exception:
        logger.exception("aggregator_failed")
        raise
    logger.info("aggregator_llm_finished")

    explainability_lines = []
    for name, output in departments:
        if not output:
            continue
        explanation = output.get("explanation")
        if explanation:
            explainability_lines.append(f"[{name}]\n{explanation}")

    explainability_block = (
        "\n\nExplainability:\n" + "\n\n".join(explainability_lines)
        if explainability_lines
        else ""
    )

    final_output = f"{response.content}{explainability_block}"
    logger.info("aggregator_finished")
    return {
        "final_output": final_output,
        "messages": state.get("messages", []) + [response],
    }
