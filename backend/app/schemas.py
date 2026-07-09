from typing import List, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    thread_id: str
    message: str


class InteractionStateSchema(BaseModel):
    """Mirrors exactly what the React/Redux left-panel form renders.
    Every field is optional because the form starts empty and fills in
    incrementally as the agent's tools populate it."""

    interaction_id: Optional[int] = None
    hcp_id: Optional[int] = None
    hcp_name: Optional[str] = None
    interaction_type: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    attendees: Optional[str] = None
    topics: Optional[str] = None
    materials_shared: List[str] = []
    samples_distributed: List[str] = []
    sentiment: Optional[str] = None
    outcomes: Optional[str] = None
    follow_up_actions: List[str] = []


class ChatResponse(BaseModel):
    reply: str
    interaction_state: InteractionStateSchema
