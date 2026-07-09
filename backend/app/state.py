from typing import Annotated, List, Optional, TypedDict

from langgraph.graph.message import add_messages


class InteractionState(TypedDict, total=False):
    """Mirrors the React/Redux left-panel form shape exactly."""

    interaction_id: Optional[int]
    hcp_id: Optional[int]
    hcp_name: Optional[str]
    interaction_type: Optional[str]
    date: Optional[str]
    time: Optional[str]
    attendees: Optional[str]
    topics: Optional[str]
    materials_shared: List[str]
    samples_distributed: List[str]
    sentiment: Optional[str]
    outcomes: Optional[str]
    follow_up_actions: List[str]


def empty_interaction_state() -> InteractionState:
    return {
        "interaction_id": None,
        "hcp_id": None,
        "hcp_name": None,
        "interaction_type": None,
        "date": None,
        "time": None,
        "attendees": None,
        "topics": None,
        "materials_shared": [],
        "samples_distributed": [],
        "sentiment": None,
        "outcomes": None,
        "follow_up_actions": [],
    }


class AgentState(TypedDict):
    """The full LangGraph graph state, persisted per-thread by the checkpointer."""

    messages: Annotated[list, add_messages]
    interaction_state: InteractionState
