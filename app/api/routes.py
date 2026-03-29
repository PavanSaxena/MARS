from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.master_agent import master_router

router = APIRouter()


class QueryRequest(BaseModel):
    query: str

@router.post("/query")
def query_system(request: QueryRequest):
    state = {"messages": [{"role": "user", "content": request.query}]}
    return master_router(state)