from typing import Dict
from langchain.chat_models import init_chat_model
from app.services.case_retrieval_service import get_similar_cases
from app.state import State

llm = init_chat_model("groq:llama-3.3-70b-versatile")


def operations_agent(state: State) -> Dict:
    pass
