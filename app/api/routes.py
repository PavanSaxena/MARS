from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agents.master_agent import run_graph

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    thread_id: str = "default"


class QueryResponse(BaseModel):
    result: str


@router.post("/query", response_model=QueryResponse)
def query_system(request: QueryRequest):
    """
    Submit a strategic query to the multi-agent decision system.
    The graph runs Finance, R&D, Legal, and Operations agents in parallel,
    then aggregates their outputs into a final recommendation.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    result = run_graph(user_input=request.query, thread_id=request.thread_id)
    return QueryResponse(result=result)
