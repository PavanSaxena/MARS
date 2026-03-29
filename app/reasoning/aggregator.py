from typing import Any, Dict

from langchain.chat_models import init_chat_model


llm = init_chat_model("groq:llama-3.3-70b-versatile")


def aggregator_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    finance_output = state.get("finance_output", {})
    rd_output = state.get("rd_output", {})
    legal_output = state.get("legal_output", {})
    operations_output = state.get("operations_output", {})

    prompt = f"""
    You are a strategic decision-making AI.

    Inputs:
    Finance: {finance_output}
    R&D: {rd_output}
    Legal: {legal_output}
    Operations: {operations_output}

    Instructions:
    1. Identify key recommendations from each department
    2. Detect conflicts
    3. Resolve conflicts prioritizing:
        - Legal compliance
        - Financial feasibility
        - Operational practicality
    4. Produce a final actionable plan

    Output:
    - Summary
    - Conflicts (if any)
    - Final Decision
    """

    response = llm.invoke(prompt)

    return {
        "final_output": response.content,
        "messages": state.get("messages", []) + [response]
    }