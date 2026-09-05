from typing import Annotated, Dict, List, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list, add_messages]
    model: Optional[str]  # "<provider>:<model>" — see app.core.config.settings.AVAILABLE_MODELS
    route: Optional[str]  # "pipeline" | "chat" — set by app.agents.router.classify_intent
    finance_output: Optional[dict]
    rd_output: Optional[dict]
    legal_output: Optional[dict]
    operations_output: Optional[dict]
    final_output: Optional[str]
    # Keyed by department name ("Finance", "R&D", "Legal", "Operations").
    # Each value is a list of slim case dicts (see common.build_case_evidence).
    retrieved_cases: Optional[Dict[str, List[dict]]]
