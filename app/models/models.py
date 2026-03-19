from pydantic import BaseModel
from typing import List, Dict

class QueryRequest(BaseModel):
    query: str


class Case(BaseModel):
    id: str
    description: str
    outcome: str
    metadata: Dict


class AgentResponse(BaseModel):
    agent: str
    recommendation: str
    confidence: float
    explanation: str