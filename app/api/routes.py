from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agents.master_agent import run_graph

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    thread_id: str = "default"

class FinalDecision(BaseModel):
    decision: str
    # risk_level: str | None = None
    # roi: str | None = None
    # notes: str | None = None


class QueryResponse(BaseModel):
    key_insights: list[str]
    conflicts: list[str]
    final_decision: FinalDecision

def parse_result(text: str):
    sections = text.split("\n\n")

    data = {
        "key_insights": [],
        "conflicts": [],
        "final_decision": {}
    }

    for section in sections:
        if section.startswith("Key Insights:"):
            lines = section.split("\n")[1:]
            data["key_insights"] = [l.replace("* ", "").strip() for l in lines if l]

        elif section.startswith("Conflicts:"):
            lines = section.split("\n")[1:]
            data["conflicts"] = [l.strip() for l in lines if l and l != "None detected"]

        elif section.startswith("Final Decision:"):
            decision_text = "\n".join(section.split("\n")[1:])
            data["final_decision"] = {
                "decision": decision_text
            }

    return data

@router.post("/query", response_model=QueryResponse)
def query_system(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    raw_result = run_graph(user_input=request.query, thread_id=request.thread_id)

    structured = parse_result(raw_result)

    return structured
