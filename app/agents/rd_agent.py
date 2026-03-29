from typing import Dict
from langchain.chat_models import init_chat_model
from app.services.case_retrieval_service import get_similar_cases
from app.state import State

llm = init_chat_model("groq:llama-3.3-70b-versatile")


def rd_agent(state: State) -> Dict:
    """
    R&D Agent:
    - Retrieves similar R&D cases from ChromaDB
    - Evaluates technical feasibility, innovation potential, and timelines
    - Outputs a structured recommendation
    """
    query = state["messages"][-1].content

    try:
        cases = get_similar_cases(query=query, domain="rd", k=5)
    except Exception as e:
        print(f"[rd_agent] Case retrieval failed: {e}")
        cases = []

    case_text = (
        "\n\n".join([str(case) for case in cases])
        if cases
        else "No relevant cases found."
    )

    prompt = f"""
You are an R&D Department AI Agent.

Your role:
- Evaluate the technical feasibility of the proposed initiative
- Assess innovation potential, research timelines, and resource requirements
- Use past similar R&D cases to guide decisions

User Query:
{query}

Relevant Past Cases:
{case_text}

Instructions:
1. Assess technical complexity and readiness level (TRL)
2. Estimate time-to-value and resource investment
3. Highlight risks such as technical debt or research dead-ends
4. Provide a clear recommendation
5. Estimate confidence (0 to 1)

Output Format (STRICT):
Response:
<your R&D recommendation>

Reasoning:
<technical justification>

Confidence:
<number between 0 and 1>
"""

    response = llm.invoke(prompt)
    parsed_output = parse_rd_output(response.content)

    return {
        "rd_output": parsed_output,
        "messages": state["messages"] + [response],
    }


def parse_rd_output(text: str) -> dict:
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
