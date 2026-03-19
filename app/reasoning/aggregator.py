def aggregator_agent(state: State):
    prompt = f"""
    You are a strategic decision-making AI.

    Inputs:
    Finance: {state['finance_output']}
    R&D: {state['rd_output']}
    Legal: {state['legal_output']}
    Operations: {state['operations_output']}

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
        "messages": state["messages"] + [response]
    }