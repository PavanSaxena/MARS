from typing import Any, Dict, List, Tuple
import re
import time

from app.agents.common import get_llm, _invoke_with_rate_limit_retry
from app.state import State
from app.core.logging_config import get_logger

logger = get_logger("reasoning.aggregator")


def _latest_user_query(state: State) -> str:
    for message in reversed(state.get("messages", []) or []):
        role = getattr(message, "type", None)
        content = getattr(message, "content", None)
        if isinstance(message, dict):
            role = message.get("role", role)
            content = message.get("content", content)
        if role in {"human", "user"} and content:
            return str(content)
    return ""


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

    case_based_confidence = output.get("case_based_confidence", output.get("confidence", 0.0))
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

    dyn_w = output.get("dynamic_weights")
    weights_line = ""
    if dyn_w and len(dyn_w) == 3:
        rationale = output.get("weight_rationale", "")
        weights_line = f"\nDynamic Query-Conditioned Weights: [Sim={dyn_w[0]:.2f}, Rec={dyn_w[1]:.2f}, Succ={dyn_w[2]:.2f}]"
        if rationale:
            weights_line += f" ({rationale})"

    external_sources = []
    for key, label in (("legal_evidence", "Legal source"), ("judicial_evidence", "Judicial source")):
        for item in output.get(key) or []:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("id") or "Untitled source"
            authority = item.get("authority") or "authority unknown"
            source_url = item.get("source_url") or "URL unavailable"
            external_sources.append(f"{label}: {title} | Authority: {authority} | URL: {source_url}")
    source_text = "\n" + "\n".join(external_sources) if external_sources else "\nLegal/judicial source evidence: None returned."

    return (
        f"--- {name} Assessment ---\n"
        f"Response: {resp_text}\n"
        f"Reasoning: {reason_text}\n"
        f"Case-Based Confidence: {case_based_text} (Avg Sim: {sim_text}, Historical Success: {succ_text}){conformal_line}{weights_line}\n"
        f"LLM Self-Reported Confidence: {reported_text}\n"
        f"Cases Retrieved: {output.get('num_cases_retrieved', 'N/A')}\n"
        f"Retrieved Case IDs: {case_ids_text}"
        f"{source_text}"
    )


def _direct_legal_answer(state: State) -> str | None:
    """Return the Legal Agent's source-grounded answer without case-only synthesis."""
    query = _latest_user_query(state).lower()
    legal_intent = any(term in query for term in (
        "law", "legal", "statute", "statutory", "regulation", "regulatory",
        "act", "section", "provision", "rights", "compliance", "court", "judgment",
        "labour", "labor", "employment", "termination", "misconduct", "privacy",
        "data protection", "contract",
    ))
    if not legal_intent:
        return None

    legal = state.get("legal_output") or {}
    nonlegal_findings = any(
        str((state.get(key) or {}).get("response") or "").strip()
        for key in ("finance_output", "operations_output", "rd_output")
    )
    if nonlegal_findings:
        return None
    legal_sources = [item for item in legal.get("legal_evidence", []) if isinstance(item, dict)]
    judgment_sources = [item for item in legal.get("judicial_evidence", []) if isinstance(item, dict)]
    provider_warnings = legal.get("warnings") or []
    provider_attempted = any(
        tool in {"search_laws", "get_law", "search_regulations", "get_regulation", "search_judgments", "get_judgment"}
        for tool in (legal.get("tools_used") or [])
    )
    if not (legal_sources or judgment_sources or provider_warnings or provider_attempted):
        return None

    answer = str(legal.get("response") or "").strip()
    if not answer:
        answer = "I could not produce a legal answer from the available retrieval results."
    sections = ["## Legal answer", answer]
    if legal_sources:
        rows = []
        seen = set()
        for item in legal_sources:
            title = item.get("title") or item.get("id") or "Untitled source"
            url = item.get("source_url")
            key = (title, url)
            if key in seen:
                continue
            seen.add(key)
            authority = item.get("authority") or "authority unknown"
            source = f"[{title}]({url})" if url else str(title)
            date = f"; retrieved {item.get('retrieved_at')}" if item.get("retrieved_at") else ""
            rows.append(f"- {source} ({authority}{date})")
        sections.extend(["### Statutory and regulatory sources", *rows])
        if any(item.get("status") in (None, "unknown") or item.get("currentness") for item in legal_sources):
            sections.append(
                "**Currency limit:** India Code supplied official text, but this lookup did not independently verify "
                "in-force status, later amendments, or commencement notifications."
            )
    if judgment_sources:
        rows = []
        for item in judgment_sources:
            title = item.get("title") or item.get("id") or "Untitled judgment record"
            url = item.get("source_url")
            source = f"[{title}]({url})" if url else str(title)
            rows.append(f"- {source} ({item.get('authority') or 'authority unknown'}; {item.get('court') or 'court unknown'})")
        sections.extend([
            "### Judgment search results",
            *rows,
            "These are retrieval leads. Treat third-party judgment records as secondary until checked against the official court record.",
        ])
    if legal.get("historical_case_evidence"):
        sections.append("MARS historical cases are internal precedent only; they do not establish current law.")
    return "\n\n".join(sections)


def aggregator_agent(state: State) -> Dict:
    """
    Aggregator Agent:
    - Collects outputs from all four department agents
    - Ranks departments by their calibrated multi-factor case_based_confidence
      (similarity + recency + past success rate), highest first
    - Uses priority order (Legal > Finance > Operations > R&D) as a tiebreaker
    - Synthesizes cross-departmental tensions and produces a grounded strategic decision
    """
    direct_legal = _direct_legal_answer(state)
    if direct_legal:
        return {"final_output": direct_legal, "final_decision": direct_legal, "messages": []}

    departments: List[Tuple[str, dict]] = [
        ("Finance", state.get("finance_output") or {}),
        ("Legal", state.get("legal_output") or {}),
        ("Operations", state.get("operations_output") or {}),
        ("R&D", state.get("rd_output") or {}),
    ]

    priority = {"Legal": 0, "Finance": 1, "Operations": 2, "R&D": 3}
    ranked = sorted(
        departments,
        key=lambda d: (-_confidence_value(d[1]), priority[d[0]]),
    )

    ranked_summary = "\n".join(
        f"{i+1}. {name}: Empirical Confidence = {_confidence_value(out):.2f}"
        for i, (name, out) in enumerate(ranked)
    )

    assessments_block = "\n\n".join(
        _fmt_department(name, out) for name, out in departments
    )

    query = _latest_user_query(state)

    prompt = f"""You are the Master Strategic Aggregator in an evidence-grounded decision support system for multi-departmental corporate advisory.

A user has submitted the following strategic problem:
\"{query}\"

The specialized departments have performed evidence-grounded analyses using historical precedent cases retrieved from the corporate decision repository.

Synthesis Instructions:
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
   - For a legal question, retrieved legal sources are independent evidence and can support a legal answer even when no MARS historical cases exist. Historical MARS cases are internal precedent, never proof of current law.
   - If authoritative law or regulation is listed, answer the legal question from that source and cite its title and URL. If its status is unknown or currency was not checked, say so.
   - If only secondary judgment discovery is listed, label it as unverified discovery and do not present a holding as authoritative.
2. IF ALL DEPARTMENTS REPORT "No historical evidences/decisions found." (or have 0.0 confidence / no retrieved cases) AND no authoritative legal or regulatory source was retrieved:
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
   - Under "Conflicts": Rigorously synthesize and cross-examine competing departmental priorities (e.g., Finance's capital allocation and margin targets vs. Operations' buffer inventory and SLA commitments vs. Legal's regulatory covenants vs. R&D's technical feasibility). Explicitly state the evidence-backed tension, cite relevant case IDs from each side, and provide a concrete, Pareto-optimal resolution or compromise.
   - Under "Risk Foresight": Comprehensively identify cross-departmental downstream failure modes (macroeconomic headwinds, supply chain disruptions, regulatory exposure, technical bottlenecks). If any retrieved case indicates a historical failure, flag that risk prominently and pair it with an evidence-backed safeguard citing exact case IDs.
   - Anti-Failure Guardrail: If historical precedents resulted in failure, NEVER endorse repeating the failed action unchanged; recommend an adjusted, defensive, or phased rollout to avert documented failure modes.
   - Weight higher-confidence, evidence-backed departments more heavily.
   - Under "Recommended Strategic Plan & Action Roadmap": Give 2-3 ordered phases only when that sequence is supported by the assessments and cases. For each phase, state the concrete action and its supporting department/case IDs. Do not fabricate owners, budgets, dates, metrics, or dependencies; say when the dataset does not establish them.
   - Make the Final Decision consistent with the conflicts, risks, and roadmap; do not overstate what the precedents establish.
5. CITATION FORMATTING REQUIREMENT:
   - Whenever citing precedent cases, ALWAYS use the EXACT bracketed case ID provided in the assessments, e.g., [AAPL-2023Q1-0001]. Never abbreviate, truncate, or hallucinate case numbers.
   - Historical MARS case IDs are organizational precedent only; they do not establish current legal requirements.
   - Cite current legal requirements only when an authoritative law or regulation appears under the Legal source lines. Include its title and source URL; if no authoritative source is listed, state that current-law verification is unavailable.
   - Never report that no applicable law exists solely because a provider search returned no matches; describe that as a retrieval gap.

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
    response = _invoke_with_rate_limit_retry(get_llm(state.get("model")).invoke, prompt)

    # Normalise content — Gemini returns a list of dicts, not a plain string.
    raw_content = response.content
    if isinstance(raw_content, list):
        final_text = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in raw_content
        )
    else:
        final_text = str(raw_content)

    retrieved_cases_map: Dict[str, List[dict]] = {}
    for name, out in departments:
        if isinstance(out, dict):
            cases = out.get("retrieved_cases") or out.get("historical_case_evidence") or []
            if cases:
                retrieved_cases_map[name] = cases

    return {
        "final_output": final_text,
        "final_decision": final_text,
        "retrieved_cases": retrieved_cases_map,
        "messages": [response],
    }
