from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list, add_messages]
    model: Optional[str]  # "<provider>:<model>" — see app.core.config.settings.AVAILABLE_MODELS
    finance_output: Optional[dict]
    rd_output: Optional[dict]
    legal_output: Optional[dict]
    operations_output: Optional[dict]
    final_output: Optional[str]
