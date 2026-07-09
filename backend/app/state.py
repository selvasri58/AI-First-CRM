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


def merge_interaction_state(
    current: Optional[InteractionState], new: Optional[InteractionState]
) -> InteractionState:
    """Reducer for the interaction_state channel.

    Normally only one tool per turn writes here, so this is just "new wins".
    But some models (e.g. llama-4-scout) will occasionally fire two tools in
    the same turn that both touch interaction_state (e.g. Lookup_Items +
    Edit_Interaction attaching the same item). Without a reducer, LangGraph
    raises InvalidUpdateError the moment two writes land on the same key in
    the same step - "last write wins" isn't even an option, it just crashes.
    This merges them field-by-field instead: for each field, whichever of
    the two updates has a non-empty value for it wins (arbitrarily "new"
    first, falling back to "current" for anything "new" left blank), so
    neither tool's contribution is silently lost.
    """
    if current is None:
        return new or {}
    if new is None:
        return current
    merged = dict(current)
    for key, value in new.items():
        if isinstance(value, list):
            if value:
                merged[key] = value
        elif value is not None:
            merged[key] = value
    return merged


class AgentState(TypedDict):
    """The full LangGraph graph state, persisted per-thread by the checkpointer."""

    messages: Annotated[list, add_messages]
    interaction_state: Annotated[InteractionState, merge_interaction_state]