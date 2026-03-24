from typing import Dict
from langchain.chat_models import init_chat_model
from app.services.case_retrieval_service import get_similar_cases

# Initialize LLM (reuse config if already global)
llm = init_chat_model("groq:llama-3.3-70b-versatile")


def finance_agent(state) -> Dict:
    """
    Finance Agent:
    - Retrieves similar financial cases
    - Performs financial reasoning
    - Outputs structured recommendation
    """

    # Extract user query
    query = state["messages"][-1].content

    # Retrieve similar cases (ANN search)
    try:
        cases = get_similar_cases(query=query, domain="finance", k=5)
    except Exception:
        cases = []

    # Format cases for prompt
    case_text = "\n\n".join([str(case) for case in cases]) if cases else "No relevant cases found."

    # Build prompt (IMPORTANT for research quality)
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

    # LLM reasoning
    response = llm.invoke(prompt)

    content = response.content

    # (Optional but recommended) Parse structured output
    parsed_output = parse_finance_output(content)

    # Return into LangGraph state
    return {
        "finance_output": parsed_output,
        "messages": state["messages"] + [response]
    }


# -------------------------
# Helper: Parse structured output
# -------------------------

def parse_finance_output(text: str) -> dict:
    """
    Extract structured fields from LLM output.
    Keeps system robust for aggregation.
    """
    try:
        sections = {
            "response": "",
            "reasoning": "",
            "confidence": 0.5
        }

        current_key = None

        for line in text.split("\n"):
            line = line.strip()

            if line.lower().startswith("response"):
                current_key = "response"
                continue
            elif line.lower().startswith("reasoning"):
                current_key = "reasoning"
                continue
            elif line.lower().startswith("confidence"):
                current_key = "confidence"
                continue

            if current_key == "confidence":
                try:
                    sections["confidence"] = float(line)
                except:
                    pass
            elif current_key:
                sections[current_key] += line + " "

        return sections

    except Exception:
        return {
            "response": text,
            "reasoning": "Parsing failed",
            "confidence": 0.5
        }