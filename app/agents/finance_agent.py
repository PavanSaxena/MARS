from typing import Dict
from langchain.chat_models import init_chat_model
from app.services.case_retrieval_service import get_similar_cases
from app.state import State

llm = init_chat_model("groq:llama-3.3-70b-versatile")


def finance_agent(state: State) -> Dict:
    """
    Finance Agent:
    - Retrieves similar financial cases from ChromaDB
    - Performs financial reasoning using an LLM
    - Outputs a structured recommendation
    """
    query = state["messages"][-1].content

    # Retrieve similar cases via ANN search
    try:
        cases = get_similar_cases(query=query, domain="finance", k=5)
    except Exception as e:
        print(f"[finance_agent] Case retrieval failed: {e}")
        cases = []

    case_text = (
        "\n\n".join([str(case) for case in cases])
        if cases
        else "No relevant cases found."
    )

    prompt = f"""
You are a Finance Department AI Agent.

Your role:
- Analyze financial aspects of the problem
- Use past similar cases to guide decisions
- Recommend a financially sound plan

User Query:
{query}

Relevant Past Cases:
{case_text}

Instructions:
1. Analyze financial risks, costs, ROI, and feasibility
2. Use past cases as supporting evidence
3. Provide a clear recommendation
4. Estimate confidence (0 to 1)

Output Format (STRICT):
Response:
<your financial recommendation>

Reasoning:
<why this is financially sound>

Confidence:
<number between 0 and 1>
"""

    response = llm.invoke(prompt)
    parsed_output = parse_finance_output(response.content)

    return {
        "finance_output": parsed_output,
        "messages": state["messages"] + [response],
    }


def parse_finance_output(text: str) -> dict:
    """Parse structured fields from the LLM output."""
    try:
        sections = {"response": "", "reasoning": "", "confidence": 0.5}
        current_key = None

        for line in text.split("\n"):
            line = line.strip()
            if line.lower().startswith("response"):
                current_key = "response"
            elif line.lower().startswith("reasoning"):
                current_key = "reasoning"
            elif line.lower().startswith("confidence"):
                current_key = "confidence"
            elif current_key == "confidence":
                try:
                    sections["confidence"] = float(line)
                except ValueError:
                    pass
            elif current_key:
                sections[current_key] += line + " "

        return sections

    except Exception:
        return {"response": text, "reasoning": "Parsing failed", "confidence": 0.5}
