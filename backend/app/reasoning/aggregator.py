from typing import Any, Dict, List, Tuple

from app.agents.common import get_llm
from app.state import State
from app.core.logging_config import get_logger

logger = get_logger("reasoning.aggregator")


def _confidence_value(output: dict) -> float:
    """
    Extract the effective confidence for ranking.
    Prioritizes calibrated multi-factor case_based_confidence (empirical),
    falling back to self-reported LLM confidence if not present.
    """
    case_conf = (output or {}).get("case_based_confidence")
    if isinstance(case_conf, (int, float)):
        return float(case_conf)
    llm_conf = (output or {}).get("confidence")
    return float(llm_conf) if isinstance(llm_conf, (int, float)) else 0.0


def _fmt_department(name: str, output: dict) -> str:
    if not output:
        return f"--- {name} Assessment ---\n(Scoped out by dynamic router — not required for this query)"

    case_based_confidence = output.get("case_based_confidence")
    case_based_text = (
        f"{case_based_confidence:.2f}"
        if isinstance(case_based_confidence, (int, float))
        else "0.00"
    )
    retrieved_cases = output.get("retrieved_cases") or []
    case_summaries = []
    for c in retrieved_cases:
        if isinstance(c, dict) and c.get("case_id"):
            cid = c.get("case_id")
            title = c.get("decision_title", "")
            outcome = c.get("outcome_label", "")
            case_summaries.append(f"[{cid}] ({outcome}): {title}")
    case_ids_text = "\n  - " + "\n  - ".join(case_summaries) if case_summaries else "None supplied"

    avg_sim = output.get("avg_similarity")
    sim_text = f"{avg_sim:.2f}" if isinstance(avg_sim, (int, float)) else "N/A"

    succ_rate = output.get("historical_success_rate")
    succ_text = f"{succ_rate:.1%}" if isinstance(succ_rate, (int, float)) else "N/A"

    reported_conf = output.get("confidence")
    reported_text = f"{reported_conf:.2f}" if isinstance(reported_conf, (int, float)) else "0.00"

    conformal = output.get("conformal_bound") or {}
    ci = conformal.get("confidence_interval")
    conformal_line = ""
    if ci:
        policy = conformal.get("decision_policy", "N/A")
        conformal_line = f"\nConformal 95% Bound: [{ci[0]:.2f}, {ci[1]:.2f}] (Policy: {policy})"

    return (
        f"--- {name} Assessment ---\n"
        f"Response: {output.get('response', 'N/A')}\n"
        f"Reasoning: {output.get('reasoning', 'N/A')}\n"
        f"Case-Based Confidence: {case_based_text} (Avg Sim: {sim_text}, Historical Success: {succ_text}){conformal_line}\n"
        f"LLM Self-Reported Confidence: {reported_text}\n"
        f"Cases Retrieved: {output.get('num_cases_retrieved', 'N/A')}\n"
        f"Retrieved Case IDs: {case_ids_text}"
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

    for name, output in departments:
        conf = _confidence_value(output)
        n_cases = (output or {}).get("num_cases_retrieved", 0)
        logger.info(f"[Aggregator] {name}: confidence={conf:.2f}, cases_retrieved={n_cases}")

    assessments_block = "\n\n".join(_fmt_department(name, output) for name, output in departments)

    prompt = f"""
You are a Strategic Decision-Making AI.

You have received assessments from four department agents. Your task is to synthesize
them into a coherent, evidence-grounded strategic summary and decision.

ONE-PASS CROSS-EXAMINATION:
- For every material proposal, identify the specific constraint, objection, or dependency stated by another department that bears on it. Name both departments and summarize the proposal and peer concern accurately.
- Cross-examine in both directions where relevant; for example, consider how Legal constraints affect Finance or Operations proposals and how Finance or Operations constraints affect R&D proposals. Do not force a conflict when the assessments are compatible.
- Ground each proposal and peer concern in the case IDs cited in the relevant department reasoning. Keep the cited cases attached to the claims they support; do not treat a case ID alone as proof of a claim.
- Classify each tension as a hard constraint, an evidence-backed risk, or a preference/cost trade-off when the assessments support that distinction.
- For each tension, state whether the supplied evidence supports a resolution, a compromise, or leaves it unresolved. Give a compromise only when its steps are supported by department findings and precedents; otherwise state what remains unresolved.
- Do not invent objections, facts, dependencies, safeguards, or conflicts. If a department did not state a concern relevant to a proposal, say that no evidence-backed peer objection was identified.
- This is a synthesis of parallel assessments, not an actual debate: the department agents did not see or revise one another's assessments. Never imply that they rebutted or agreed to revisions.

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
   - Under "Risk Foresight": State that no precedent-grounded risks or safeguards can be identified.
   - Under "Recommended Strategic Plan & Action Roadmap": State that no evidence-based roadmap can be recommended; do not invent phases, actions, owners, budgets, or timelines.
   - Under "Final Decision": State explicitly: "No evidence-based decision can be recommended. The dataset does not contain historical precedents or decisions for this query. The system refuses to provide ungrounded or hallucinated recommendations without supporting empirical evidence."
3. IF ONLY SOME DEPARTMENTS HAVE EVIDENCE:
   - Base your recommendations ONLY on the departments that provided grounded evidence from historical cases.
   - Explicitly note which departments lacked historical precedents.
   - Do NOT invent recommendations for ungrounded departments.
   - Risks, safeguards, roadmap steps, and cross-department resolutions must be supported by grounded departments' findings. Identify material gaps and leave unsupported sequencing, owners, budgets, and dates unspecified.
4. IF DEPARTMENTS HAVE VALID GROUNDED EVIDENCE:
   - Identify key recommendations, agreements, and conflicts supported by their cited historical cases.
   - Under "Conflicts": Explicitly cross-examine each material proposal against peer concerns, citing the department and relevant case IDs. State the evidence-backed resolution/compromise or identify what remains unresolved.
   - Under "Risk Foresight": Identify concrete downstream failure modes grounded in retrieved failure cases or explicit departmental findings. Pair each risk with a safeguard only when the evidence supports that safeguard; cite case IDs and label material evidence gaps.
   - Weight higher-confidence, evidence-backed departments more heavily.
   - Under "Recommended Strategic Plan & Action Roadmap": Give 2-3 ordered phases only when that sequence is supported by the assessments and cases. For each phase, state the concrete action and its supporting department/case IDs. Do not fabricate owners, budgets, dates, metrics, or dependencies; say when the dataset does not establish them.
    - Make the Final Decision consistent with the conflicts, risks, and roadmap; do not overstate what the precedents establish.
5. CITATION FORMATTING REQUIREMENT:
    - Whenever citing precedent cases, ALWAYS use the EXACT bracketed case ID provided in the assessments, e.g., [AAPL-2023Q1-0001]. Never abbreviate, truncate, or hallucinate case numbers.

Output Format (STRICT):
Key Insights:
<bullet points of the findings, or note the complete absence of historical evidence>

Conflicts:
<for each material proposal, the relevant peer concern, evidence/case IDs (e.g. [AAPL-2023Q1-0001]), classification, and evidence-backed resolution or unresolved point; or "None detected">

Risk Foresight:
<specific downstream risks and evidence-backed safeguards citing exact case IDs (e.g. [AAPL-2023Q2-0050]), or state that no precedent-grounded risks/safeguards can be identified>

Recommended Strategic Plan & Action Roadmap:
<2-3 evidence-supported phases with concrete actions and exact case IDs, or state that no evidence-based roadmap can be recommended>

Final Decision:
<the grounded recommendation citing key precedents, or explicit refusal if no historical evidence exists>
"""

    logger.info("[Aggregator] Invoking LLM to synthesize final decision")
    response = get_llm(state.get("model")).invoke(prompt)

    # Normalise content — Gemini returns a list of dicts, not a plain string.
    from app.agents.common import _normalize_content
    response_text = _normalize_content(getattr(response, "content", str(response)))
    logger.info(f"[Aggregator] Synthesis complete ({len(response_text)} chars)")

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

    total_cases = sum(len(v) for v in retrieved_cases_by_dept.values())
    logger.info(f"[Aggregator] Final output ready ({total_cases} total evidence cases across {len(retrieved_cases_by_dept)} departments)")

    return {
        "final_output": final_output,
        "retrieved_cases": retrieved_cases_by_dept,
        "messages": state.get("messages", []) + [response],
    }
