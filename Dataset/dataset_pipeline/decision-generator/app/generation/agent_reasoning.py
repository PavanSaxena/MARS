from __future__ import annotations

import re


DECISION_KEYWORDS = {
	"Finance": ("budget", "forecast", "revenue", "expense", "cost", "cash", "liquidity", "guidance", "impairment", "debt", "dividend", "buyback", "covenant"),
	"Legal": ("legal", "litigation", "lawsuit", "settlement", "compliance", "contract", "regulatory", "investigation", "consent decree"),
	"Operations": ("operations", "supply", "manufacturing", "inventory", "logistics", "procurement", "fulfillment", "distribution", "capacity", "vendor", "system outage"),
	"R&D": ("research", "development", "product", "platform", "launch", "roadmap", "prototype", "clinical", "trial", "engineering", "innovation"),
}

ACTION_KEYWORDS = {
	"Proceed": ("approve", "approved", "authorization", "launch", "expand", "invest", "continue", "increase", "enter", "adopt"),
	"Pause": ("delay", "defer", "postpone", "pause", "suspend", "halt", "freeze", "withhold"),
	"Revise": ("revise", "amend", "adjust", "renegotiate", "restructure", "modify", "reforecast", "reclassify", "remediate"),
}

THEME_TEMPLATES = {
	"capital_allocation": {
		"department": "Finance",
		"archetype": "Capital Allocation Decision",
		"title": "Rebalance capital allocation toward higher-return priorities",
	},
	"guidance_revision": {
		"department": "Finance",
		"archetype": "Financial Guidance Decision",
		"title": "Revise guidance to reflect updated demand and margin expectations",
	},
	"product_roadmap": {
		"department": "R&D",
		"archetype": "Product / Investment Decision",
		"title": "Prioritize roadmap execution around the highest-value product bets",
	},
	"supply_chain": {
		"department": "Operations",
		"archetype": "Operating Model Decision",
		"title": "Rework supply and inventory plans for the current operating outlook",
	},
	"legal_compliance": {
		"department": "Legal",
		"archetype": "Compliance Decision",
		"title": "Strengthen compliance and reserve planning around legal exposure",
	},
	"governance": {
		"department": "Legal",
		"archetype": "Governance Decision",
		"title": "Align governance actions with board and shareholder priorities",
	},
	"r_and_d_prioritization": {
		"department": "R&D",
		"archetype": "Product / Investment Decision",
		"title": "Reallocate engineering focus to the most strategic initiatives",
	},
	"operating_model": {
		"department": "Operations",
		"archetype": "Operating Model Decision",
		"title": "Streamline operating expenses and vendor commitments",
	},
}

TOPIC_KEYWORDS = {
	"capital allocation": ("buyback", "dividend", "capital return", "cash", "liquidity", "treasury", "repurchase"),
	"guidance": ("guidance", "forecast", "margin", "revenue", "outlook", "reforecast"),
	"product": ("product", "launch", "feature", "platform", "device", "service"),
	"supply chain": ("supply", "inventory", "manufacturing", "logistics", "capacity", "vendor"),
	"legal": ("legal", "litigation", "settlement", "compliance", "regulatory", "investigation"),
	"governance": ("board", "committee", "proxy", "shareholder", "director"),
	"r and d": ("research", "development", "engineering", "innovation", "prototype", "trial"),
	"operations": ("operations", "cost", "expense", "efficiency", "restructure", "productivity"),
}


def clean_text(text: str) -> str:
	return " ".join(str(text).split())


def extract_topic(text: str) -> str:
	lower_text = text.lower()
	for topic, keywords in TOPIC_KEYWORDS.items():
		if any(keyword in lower_text for keyword in keywords):
			return topic
	return "operations"


def extract_theme(text: str) -> str:
	topic = extract_topic(text)
	if topic == "capital allocation":
		return "capital_allocation"
	if topic == "guidance":
		return "guidance_revision"
	if topic == "product":
		return "product_roadmap"
	if topic == "supply chain":
		return "supply_chain"
	if topic == "legal":
		return "legal_compliance"
	if topic == "governance":
		return "governance"
	if topic == "r and d":
		return "r_and_d_prioritization"
	return "operating_model"


def extract_metrics(text: str) -> list[str]:
	metrics = []
	patterns = [
		r"\$\d+(?:\.\d+)?\s*(?:billion|million|trillion)?",
		r"\d+(?:\.\d+)?%",
		r"\b(?:revenue|margin|cash flow|inventory|capex|opex|expenses?|earnings|guidance|forecast|debt|cash)\b",
	]
	for pattern in patterns:
		for match in re.findall(pattern, text, flags=re.IGNORECASE):
			value = clean_text(match)
			if value not in metrics:
				metrics.append(value)
	return metrics[:6]


def _title_case_snippet(text: str, max_words: int = 8) -> str:
	words = [word for word in re.split(r"\W+", clean_text(text)) if word]
	return " ".join(words[:max_words]).strip().title()


def split_sentences(text: str) -> list[str]:
	parts = re.split(r"(?<=[.!?])\s+", clean_text(text))
	return [part.strip() for part in parts if part.strip()]


def infer_department(text: str) -> str:
	lower_text = text.lower()
	for department, keywords in DECISION_KEYWORDS.items():
		if any(keyword in lower_text for keyword in keywords):
			return department
	if any(keyword in lower_text for keyword in ("buyback", "dividend", "cash", "forecast", "margin", "revenue")):
		return "Finance"
	return "Operations"


def infer_archetype(text: str) -> str:
	lower_text = text.lower()
	if any(keyword in lower_text for keyword in ("buyback", "dividend", "capital", "liquidity", "cash", "debt")):
		return "Capital Allocation Decision"
	if any(keyword in lower_text for keyword in ("guidance", "forecast", "reforecast")):
		return "Financial Guidance Decision"
	if any(keyword in lower_text for keyword in ("litigation", "settlement", "compliance", "regulatory")):
		return "Compliance Decision"
	if any(keyword in lower_text for keyword in ("launch", "prototype", "roadmap", "development")):
		return "Product / Investment Decision"
	if any(keyword in lower_text for keyword in ("capacity", "inventory", "procurement", "manufacturing")):
		return "Operating Model Decision"
	if any(keyword in lower_text for keyword in ("board", "proxy", "shareholder", "committee", "director")):
		return "Governance Decision"
	return "Resource Allocation Decision"


def infer_risk_level(text: str) -> str:
	lower_text = text.lower()
	if any(keyword in lower_text for keyword in ("restatement", "breach", "lawsuit", "material weakness", "going concern", "halt", "default")):
		return "High"
	if any(keyword in lower_text for keyword in ("delay", "defer", "risk", "review", "monitor", "uncertain", "impairment", "volatility", "pressure", "headwind", "tighten")):
		return "Medium"
	return "Low"


def infer_chosen_option(text: str) -> str:
	lower_text = text.lower()
	for option, keywords in ACTION_KEYWORDS.items():
		if any(keyword in lower_text for keyword in keywords):
			return option
	return "Revise" if infer_risk_level(text) == "High" else "Proceed"


def build_options_considered(text: str) -> str:
	depart = infer_department(text)
	base_options = {
		"Finance": ["Proceed:Approve the current plan", "Pause:Hold pending more visibility", "Revise:Rebalance the plan"],
		"Legal": ["Proceed:Advance with controls", "Pause:Wait for legal clarity", "Revise:Adjust the remediation plan"],
		"Operations": ["Proceed:Execute as planned", "Pause:Defer until capacity stabilizes", "Revise:Re-sequence supply and cost actions"],
		"R&D": ["Proceed:Fund the current roadmap", "Pause:Delay lower-priority work", "Revise:Reallocate to strategic initiatives"],
	}
	return ";".join(base_options.get(depart, base_options["Operations"]))


def build_case_title(source_excerpt: str, department: str, archetype: str, company_name: str = "") -> str:
	theme = extract_theme(source_excerpt)
	template = THEME_TEMPLATES.get(theme)
	if template:
		title = template["title"]
		if company_name:
			return f"{company_name}: {title}"
		return title

	metrics = extract_metrics(source_excerpt)
	metric_phrase = metrics[0] if metrics else _title_case_snippet(source_excerpt, max_words=6)
	if company_name:
		return f"{company_name}: {department} decision on {metric_phrase}"
	return f"{department} decision on {metric_phrase}"


def build_reasoning_summary(source_excerpt: str, department: str, theme: str) -> str:
	metrics = extract_metrics(source_excerpt)
	metric_text = ", ".join(metrics[:3]) if metrics else "reported operating and financial signals"
	return clean_text(
		f"{department} should act on the {theme.replace('_', ' ')} signal because {metric_text} point to a material decision point."
	)


def _role_confidence(base: float, department: str, role: str, risk_level: str) -> float:
	adjustment = 0.0
	if role == "legal" and department == "Legal":
		adjustment += 0.1
	if role == "r_and_d" and department == "R&D":
		adjustment += 0.1
	if role == "ops" and department == "Operations":
		adjustment += 0.08
	if risk_level == "High":
		adjustment -= 0.08
	elif risk_level == "Low":
		adjustment += 0.04
	return max(0.35, min(0.93, round(base + adjustment, 2)))


def build_case_row(*, case_id: int, source_file_name: str, source_excerpt: str, quarter: str, company_name: str = "") -> dict:
	department = infer_department(source_excerpt)
	archetype = infer_archetype(source_excerpt)
	theme = extract_theme(source_excerpt)
	risk_level = infer_risk_level(source_excerpt)
	chosen_option = infer_chosen_option(source_excerpt)
	reasoning_summary = build_reasoning_summary(source_excerpt, department, theme)
	description = clean_text(
		f"{department} evaluates whether to {chosen_option.lower()} in response to the {theme.replace('_', ' ')} signal described in the filing."
	)
	title = build_case_title(source_excerpt, department, archetype, company_name=company_name)
	options = build_options_considered(source_excerpt)
	base_confidence = 0.66 if risk_level == "Low" else 0.58 if risk_level == "Medium" else 0.49
	profit_confidence = round(base_confidence, 2)
	master_confidence = round(max(0.45, min(0.9, base_confidence + (0.08 if department == "Finance" else 0.05))), 2)
	metrics = extract_metrics(source_excerpt)
	quantitative_signals = "; ".join(metrics) if metrics else "No explicit numeric metric surfaced in the sentence"
	source_grounding = "source-grounded" if source_excerpt else "context-derived"
	conflicting_perspectives = (
		f"Finance sees the strongest linkage to capital deployment while {department.lower()} emphasizes execution risk."
		if risk_level != "Low"
		else "Finance, operations, and legal considerations appear aligned around execution."
	)
	outcome_summary = clean_text(
		f"If the decision proceeds, {theme.replace('_', ' ')} actions should improve execution clarity over the next quarter."
	)
	expected_profit_impact = (
		"Potential uplift from disciplined execution and capital efficiency"
		if chosen_option == "Proceed"
		else "Potential downside reduction through timing, re-scoping, or remediation"
	)

	return {
		"case_id": case_id,
		"source_file_name": source_file_name,
		"source_excerpt": source_excerpt,
		"quarter": quarter,
		"department": department,
		"decision_title": title,
		"decision_archetype": archetype,
		"trigger": title,
		"decision_description": description,
		"options_considered": options,
		"chosen_option": chosen_option,
		"reasoning_summary": reasoning_summary,
		"quantitative_signals": quantitative_signals,
		"risk_level": risk_level,
		"cross_dept_impact": "Finance;Operations;Legal;R&D" if department != "Legal" else "Legal;Finance;Operations",
		"expected_profit_impact": expected_profit_impact,
		"profit_confidence": profit_confidence,
		"profit_impact_pathway": f"{theme.replace('_', ' ')} -> execution choices -> financial impact",
		"outcome_status": "proposed",
		"outcome_summary": outcome_summary,
		"decision_tags": ",".join(sorted({department.lower(), risk_level.lower(), source_grounding, theme.replace('_', '-') })),
		"finance_agent_conf": _role_confidence(profit_confidence, department, "finance", risk_level),
		"r_and_d_agent_conf": _role_confidence(profit_confidence - 0.04, department, "r_and_d", risk_level),
		"ops_agent_conf": _role_confidence(profit_confidence - 0.02, department, "ops", risk_level),
		"legal_agent_conf": _role_confidence(profit_confidence - 0.03, department, "legal", risk_level),
		"conflicting_perspectives": conflicting_perspectives,
		"master_agent_decision": chosen_option,
		"master_agent_confidence": master_confidence,
	}
