import operator
from typing import Annotated, List, TypedDict

class AgentState(TypedDict):
    query: str           # The user's goal
    current_draft: str   # The report being built
    critique: str        # Feedback from the editor
    revision_count: int  # Safety break (stops at 3 loops)
    approved: bool       # The "Exit" signal
    exit_requested: bool # Graceful CLI exit requested by user
    # Paper trail for the auditor; append across steps.
    sources_text: Annotated[List[str], operator.add]