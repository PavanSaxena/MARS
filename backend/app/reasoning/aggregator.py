from typing import Any, Dict, List, Tuple

from app.agents.common import get_llm
from app.state import State


def _confidence_value(output: dict) -> float:
    """
    Extract the effective confidence for ranking.
    Uses calibrated multi-factor empirical confidence.
    """
    case_conf = (output or {}).get("case_based_confidence")
    if isinstance(case_conf, (int, float)):
        return float(case_conf)
    conf = (output or {}).get("confidence")
    return float(conf) if isinstance(conf, (int, float)) else 0.0


def _fmt_department(name: str, output: dict) -> str:
    if not output:
        return f"--- {name} Assessment ---\n(Scoped out by dynamic router — not required for this query)"

    case_based_confidence = output.get("case_based_confidence", output.get("confidence", 0.0))
    case_based_text = (
        f"{case_based_confidence:.2f}"
        if isinstance(case_based_confidence, (int, float))
        else "0.00"
    )

    avg_sim = output.get("avg_similarity")
    sim_text = f"{avg_sim:.2f}" if isinstance(avg_sim, (int, float)) else "N/A"

    succ_rate = output.get("historical_success_rate")
    succ_text = f"{succ_rate:.1%}" if isinstance(succ_rate, (int, float)) else "N/A"

    conformal = output.get("conformal_bound") or {}
    ci = conformal.get("confidence_interval")
    conformal_line = ""
    if ci:
        policy = conformal.get("decision_policy", "N/A")
        conformal_line = f"\nConformal 95% Bound: [{ci[0]:.2f}, {ci[1]:.2f}] (Policy: {policy})"

    dyn_w = output.get("dynamic_weights")
    weights_line = ""
    if dyn_w and len(dyn_w) == 3:
        rationale = output.get("weight_rationale", "")
        weights_line = f"\nDynamic Query-Conditioned Weights: [Sim={dyn_w[0]:.2f}, Rec={dyn_w[1]:.2f}, Succ={dyn_w[2]:.2f}]"
        if rationale:
            weights_line += f" ({rationale})"

    return (
        f"--- {name} Assessment ---\n"
        f"Response: {output.get('response', 'N/A')}\n"
        f"Reasoning: {output.get('reasoning', 'N/A')}\n"
        f"Empirical Confidence: {case_based_text} (Avg Sim: {sim_text}, Historical Success: {succ_text}){conformal_line}{weights_line}\n"
        f"Cases Retrieved: {output.get('num_cases_retrieved', 'N/A')}"
    )


def aggregator_agent(state: State) -> Dict:
    """
    Aggregator Agent:
    - Collects outputs from all four department agents
    - Ranks departments by their calibrated multi-factor case_based_confidence
      (similarity + recency + past success rate), highest first
    - Uses priority order (Legal > Finance > Operations > R&D) as a tiebreaker
    - Synthesizes cross-departmental tensions and produces a grounded strategic decision
    """
    departments: List[Tuple[str, dict]] = [
        ("Finance", state.get("finance_output") or {}),
        ("R&D", state.get("rd_output") or {}),
        ("Legal", state.get("legal_output") or {}),
        ("Operations", state.get("operations_output") or {}),
    ]

    # Rank by calibrated case-based confidence, highest first
    ranked = sorted(departments, key=lambda item: _confidence_value(item[1]), reverse=True)
    ranked_summary = "\n".join(
        f"{i+1}. {name} (Case-Based Confidence: {_confidence_value(output):.2f})"
        for i, (name, output) in enumerate(ranked)
        if output
    ) or "No department outputs available."

    assessments_block = "\n\n".join(_fmt_department(name, output) for name, output in departments)

    prompt = f"""
You are a Strategic Decision-Making AI.

You have received assessments from four department agents. Your task is to synthesize
them into a coherent, evidence-grounded strategic summary and decision.

Departments Ranked by Reported Confidence (highest first):
{ranked_summary}

Department Assessments:
{assessments_block}

CRITICAL GROUNDING DIRECTIVES (STRICT EVIDENCE-ONLY REQUIREMENT):
1. You must base your synthesis and decision STRICTLY on the evidence-backed findings reported by the department agents.
2. IF ALL DEPARTMENTS REPORT "No historical evidences/decisions found." (or have 0.0 confidence / no retrieved cases):
   - You MUST NOT fabricate, invent, or hallucinate a speculative business strategy, rollout plan, budget, or timeline.
   - Under "Key Insights": State clearly that no historical cases or precedents were found in the dataset across any department.
   - Under "Conflicts": State "None (no historical data to evaluate)".
   - Under "Final Decision": State explicitly: "No evidence-based decision can be recommended. The dataset does not contain historical precedents or decisions for this query. The system refuses to provide ungrounded or hallucinated recommendations without supporting empirical evidence."
3. IF ONLY SOME DEPARTMENTS HAVE EVIDENCE:
   - Base your recommendations ONLY on the departments that provided grounded evidence from historical cases.
   - Explicitly note which departments lacked historical precedents.
   - Do NOT invent recommendations for ungrounded departments.
4. IF DEPARTMENTS HAVE VALID GROUNDED EVIDENCE:
   - Identify key recommendations, agreements, and conflicts supported by their cited historical cases.
   - Under "Conflicts": Explicitly synthesize any cross-department tensions, conflicting perspectives, or trade-offs (e.g. Finance gross margin/CapEx concerns vs. Operations supply/backlog targets, Legal regulatory/compliance constraints vs. R&D engineering velocity) evidenced in the retrieved cases, and outline how management should balance these competing priorities.
   - Weight higher-confidence, evidence-backed departments more heavily.
   - Produce a final actionable plan directly referencing the historical evidence.

Output Format (STRICT):
Key Insights:
<bullet points of the findings, or note the complete absence of historical evidence>

Conflicts:
<synthesis of inter-departmental tensions, conflicting perspectives, and trade-offs, or "None detected">

Final Decision:
<the grounded recommendation, or explicit refusal if no historical evidence exists>
"""

    import time
    time.sleep(2)
    response = get_llm(state.get("model")).invoke(prompt)

    # Normalise content — Gemini returns a list of dicts, not a plain string.
    from app.agents.common import _normalize_content
    response_text = _normalize_content(getattr(response, "content", str(response)))

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

    final_output = f"{response_text}{explainability_block}"

    # Collect retrieved cases per department so the API can surface them.
    retrieved_cases_by_dept: dict = {}
    for name, output in departments:
        cases = (output or {}).get("retrieved_cases")
        if cases:
            retrieved_cases_by_dept[name] = cases

    return {
        "final_output": final_output,
        "retrieved_cases": retrieved_cases_by_dept,
        "messages": state.get("messages", []) + [response],
    }
