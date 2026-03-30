from typing import Dict
from langchain.chat_models import init_chat_model
from app.state import State

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = init_chat_model("groq:llama-3.3-70b-versatile")
    return _llm


def aggregator_agent(state: State) -> Dict:
    """
    Aggregator Agent:
    - Collects outputs from all four department agents
    - Resolves conflicts with priority: Legal > Finance > Operations > R&D
    - Produces a final actionable strategic decision
    """
    finance = state.get("finance_output") or {}
    rd = state.get("rd_output") or {}
    legal = state.get("legal_output") or {}
    operations = state.get("operations_output") or {}

    def fmt(output: dict) -> str:
        if not output:
            return "No input received."
        return (
            f"Response: {output.get('response', 'N/A')}\n"
            f"Reasoning: {output.get('reasoning', 'N/A')}\n"
            f"Confidence: {output.get('confidence', 'N/A')}"
        )

    prompt = f"""
You are a Strategic Decision-Making AI.

You have received assessments from four department agents. Your task is to synthesize
them into a single, coherent, actionable final plan.

--- Finance Assessment ---
{fmt(finance)}

--- R&D Assessment ---
{fmt(rd)}

--- Legal Assessment ---
{fmt(legal)}

--- Operations Assessment ---
{fmt(operations)}

Instructions:
1. Identify key recommendations and agreements across departments
2. Detect any conflicts between departments
3. Resolve conflicts by prioritizing in this order:
   - Legal compliance (highest priority)
   - Financial feasibility
   - Operational practicality
   - R&D innovation potential
4. Produce a final actionable plan

Output Format (STRICT):
Key Insights:
<bullet points of the most important findings>

Conflicts:
<any conflicts between departments, or "None detected">

Final Decision:
<the recommended course of action>
"""

    response = _get_llm().invoke(prompt)

    return {
        "final_output": response.content,
        "messages": state.get("messages", []) + [response],
    }
