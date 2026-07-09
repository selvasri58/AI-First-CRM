from contextlib import asynccontextmanager
import traceback

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage

from app.config import settings
from app.database import Base, engine
from app import models  # noqa: F401 - registers models on Base metadata
from app.schemas import ChatRequest, ChatResponse, InteractionStateSchema
from app.state import empty_interaction_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Convenience for local dev: ensures tables exist even if you didn't run
    # init.sql manually. Safe to call repeatedly (create_all is idempotent).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="AI-First CRM - HCP Interaction API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    """Single entry point the ChatPanel calls. `thread_id` scopes the
    LangGraph checkpointer's memory so each browser tab/session keeps its
    own interaction-in-progress; send the same thread_id for the whole
    lifetime of one "Log HCP Interaction" screen."""
    try:
        from app.agent import get_agent  # imported lazily - see agent.py
        agent = get_agent()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    config = {"configurable": {"thread_id": payload.thread_id}}

    # interaction_state has no reducer, so it's "last write wins": if we
    # always included it in the input dict, every turn would reset it to
    # empty, destroying prior progress. So we only seed it when this thread
    # truly has no checkpointed state yet (i.e. its very first message) -
    # every later turn omits the key entirely and LangGraph carries forward
    # whatever the checkpointer already has.
    existing = agent.get_state(config).values or {}
    input_state = {"messages": [HumanMessage(content=payload.message)]}
    if "interaction_state" not in existing:
        input_state["interaction_state"] = empty_interaction_state()

    try:
        result = agent.invoke(input_state, config)
    except Exception as e:
        print("\n" + "=" * 70)
        print("AGENT ERROR - full traceback below:")
        traceback.print_exc()
        print("=" * 70 + "\n")
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    reply = result["messages"][-1].content or "(no response text)"
    interaction_state = result.get("interaction_state") or empty_interaction_state()

    return ChatResponse(
        reply=reply,
        interaction_state=InteractionStateSchema(**interaction_state),
    )


@app.get("/api/interaction-state/{thread_id}", response_model=InteractionStateSchema)
def get_interaction_state(thread_id: str):
    """Lets the frontend re-fetch current form state on page reload without
    sending a new chat message (reads straight from the checkpointer)."""
    from app.agent import get_agent

    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = agent.get_state(config)
    state = (snapshot.values or {}).get("interaction_state") or empty_interaction_state()
    return InteractionStateSchema(**state)