from fastapi import APIRouter
from agents.master_agent import MasterAgent

router = APIRouter()
agent = MasterAgent()

@router.post("/query")
def query_system(request):

    result = agent.analyze(request["query"])

    return result