"""
The 5 LangGraph tools for the AI-First CRM HCP Interaction agent:

1. Fetch_HCP_Context   - resolve/disambiguate an HCP name to a DB record.
2. Log_Interaction     - create a new interaction row (mandatory).
3. Edit_Interaction    - partially update the current interaction (mandatory).
4. Lookup_Items        - resolve material/sample names to DB IDs.
5. Create_Follow_Up_Task - create a task row + update Follow-up Actions.

Design note on state mutation:
Tools that change what the left-hand form should display return a
`Command(update=...)` object. LangGraph's ToolNode merges that update into
the shared graph state (see app/state.py) which is what gets serialized
back to the FastAPI response -> Redux store -> React form on every turn.
Tools receive the current state read-only via `InjectedState` so they never
have to be told the current interaction id / hcp id by the LLM - it's
tracked by the graph itself.
"""

from datetime import date as date_cls, time as time_cls
from typing import Annotated, List, Optional

from dateutil import parser as dateutil_parser
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from sqlalchemy import or_

from app.database import get_session
from app.models import HCPProfile, Interaction, Material, MaterialType, InteractionMaterial, Task
from app.state import AgentState, InteractionState


# ---------------------------------------------------------------------------
# Small internal helpers (not exposed as tools themselves)
# ---------------------------------------------------------------------------

def _parse_date(value: Optional[str]) -> Optional[date_cls]:
    if not value:
        return None
    try:
        return dateutil_parser.parse(value).date()
    except (ValueError, OverflowError):
        return None


def _parse_time(value: Optional[str]) -> Optional[time_cls]:
    if not value:
        return None
    try:
        return dateutil_parser.parse(value).time()
    except (ValueError, OverflowError):
        return None


def _resolve_hcp(db, hcp_name: str) -> tuple[Optional[HCPProfile], List[HCPProfile]]:
    """Returns (best_match_or_None, all_candidates). Case-insensitive,
    partial-name tolerant (e.g. "Smith" matches "Dr. Smith")."""
    if not hcp_name:
        return None, []
    candidates = (
        db.query(HCPProfile)
        .filter(HCPProfile.name.ilike(f"%{hcp_name.strip()}%"))
        .all()
    )
    if len(candidates) == 1:
        return candidates[0], candidates
    if len(candidates) > 1:
        # Prefer an exact (case-insensitive) name match among the candidates.
        exact = [c for c in candidates if c.name.lower() == hcp_name.strip().lower()]
        if exact:
            return exact[0], candidates
        return None, candidates  # ambiguous
    return None, []


def _get_or_create_material(db, name: str, item_type: Optional[str]) -> Material:
    match = (
        db.query(Material)
        .filter(Material.name.ilike(f"%{name.strip()}%"))
        .first()
    )
    if match:
        return match
    inferred_type = MaterialType.sample if (item_type or "").lower() == "sample" else MaterialType.material
    new_item = Material(name=name.strip(), type=inferred_type)
    db.add(new_item)
    db.flush()
    return new_item


def _link_items_to_interaction(db, interaction_id: int, names: List[str], item_type: str) -> List[Material]:
    resolved = []
    for name in names:
        mat = _get_or_create_material(db, name, item_type)
        exists = (
            db.query(InteractionMaterial)
            .filter_by(interaction_id=interaction_id, material_id=mat.material_id)
            .first()
        )
        if not exists:
            db.add(InteractionMaterial(interaction_id=interaction_id, material_id=mat.material_id))
        resolved.append(mat)
    return resolved


def _interaction_to_state(db, interaction: Interaction) -> InteractionState:
    """Builds the exact shape the React/Redux left form expects."""
    materials = [
        link.material.name
        for link in interaction.materials_links
        if link.material.type == MaterialType.material
    ]
    samples = [
        link.material.name
        for link in interaction.materials_links
        if link.material.type == MaterialType.sample
    ]
    follow_ups = [
        f"{t.description}" + (f" (due {t.due_date.isoformat()})" if t.due_date else "")
        for t in interaction.tasks
    ]
    return {
        "interaction_id": interaction.id,
        "hcp_id": interaction.hcp_id,
        "hcp_name": interaction.hcp.name if interaction.hcp else None,
        "interaction_type": interaction.interaction_type,
        "date": interaction.date.isoformat() if interaction.date else None,
        "time": interaction.time.strftime("%H:%M") if interaction.time else None,
        "attendees": interaction.attendees,
        "topics": interaction.topics,
        "materials_shared": materials,
        "samples_distributed": samples,
        "sentiment": interaction.sentiment,
        "outcomes": interaction.outcomes,
        "follow_up_actions": follow_ups,
    }


# ---------------------------------------------------------------------------
# Tool 1: Fetch_HCP_Context
# ---------------------------------------------------------------------------

@tool
def Fetch_HCP_Context(hcp_name: str) -> str:
    """Search hcp_profiles to disambiguate a doctor/HCP's name and retrieve
    their database ID and specialty before logging or editing an interaction.
    Always call this first if you are not already certain which HCP record
    a name refers to (e.g. multiple doctors could share a last name).

    Args:
        hcp_name: The HCP's name as mentioned by the user (can be partial,
            e.g. "Smith" or "Dr. Smith").
    """
    db = get_session()
    try:
        best, candidates = _resolve_hcp(db, hcp_name)
        if best:
            return (
                f"Found HCP: id={best.hcp_id}, name='{best.name}', "
                f"specialty='{best.specialty or 'unknown'}'."
            )
        if candidates:
            options = "; ".join(f"id={c.hcp_id} name='{c.name}' ({c.specialty})" for c in candidates)
            return (
                f"Multiple possible matches for '{hcp_name}': {options}. "
                "Ask the user which one they mean before proceeding."
            )
        return (
            f"No existing HCP profile found matching '{hcp_name}'. "
            "You may proceed with logging using this name as free text; "
            "a new hcp_profiles record can be created if the user confirms."
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 2: Log_Interaction (mandatory)
# ---------------------------------------------------------------------------

@tool
def Log_Interaction(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    hcp_name: str,
    interaction_type: str = "Meeting",
    date: Optional[str] = None,
    time: Optional[str] = None,
    attendees: Optional[str] = None,
    topics: Optional[str] = None,
    sentiment: Optional[str] = None,
    outcomes: Optional[str] = None,
    materials_shared: Optional[List[str]] = None,
    samples_distributed: Optional[List[str]] = None,
) -> Command:
    """Create a brand-new interaction record. Call this the first time the
    user describes a field visit / call / meeting with an HCP in a single
    message, e.g. "Today I met with Dr. Smith and discussed product X
    efficiency. The sentiment was positive, and I shared the brochures."

    Extract every entity you can from the user's sentence: HCP name,
    interaction type (default "Meeting" if not stated), date (default to
    today if not stated), time (default to current time if not stated),
    attendees, topics discussed, sentiment (Positive/Neutral/Negative), any
    materials or samples mentioned, and outcomes if stated. Normalize dates
    to YYYY-MM-DD and times to 24-hour HH:MM before calling this tool.

    Args:
        hcp_name: Name of the healthcare professional.
        interaction_type: e.g. "Meeting", "Call", "Conference".
        date: ISO date (YYYY-MM-DD). Defaults to today if omitted.
        time: 24-hour time (HH:MM). Defaults to now if omitted.
        attendees: Free-text list of who attended.
        topics: What was discussed.
        sentiment: One of "Positive", "Neutral", "Negative".
        outcomes: Any stated outcomes/agreements.
        materials_shared: Names of any printed materials/brochures mentioned.
        samples_distributed: Names of any drug samples mentioned.
    """
    from datetime import datetime as dt

    db = get_session()
    try:
        hcp, candidates = _resolve_hcp(db, hcp_name)
        if hcp is None and len(candidates) > 1:
            options = ", ".join(c.name for c in candidates)
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                f"Ambiguous HCP name '{hcp_name}'. Possible matches: "
                                f"{options}. Please ask the user to clarify before logging."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )
        if hcp is None:
            # No match at all - create a new lightweight profile so the
            # interaction can still be logged (agent should mention this).
            hcp = HCPProfile(name=hcp_name.strip(), specialty=None)
            db.add(hcp)
            db.flush()

        parsed_date = _parse_date(date) or dt.now().date()
        parsed_time = _parse_time(time) or dt.now().time().replace(microsecond=0)

        interaction = Interaction(
            hcp_id=hcp.hcp_id,
            interaction_type=interaction_type,
            date=parsed_date,
            time=parsed_time,
            attendees=attendees,
            topics=topics,
            sentiment=sentiment,
            outcomes=outcomes,
        )
        db.add(interaction)
        db.flush()

        if materials_shared:
            _link_items_to_interaction(db, interaction.id, materials_shared, "material")
        if samples_distributed:
            _link_items_to_interaction(db, interaction.id, samples_distributed, "sample")

        db.commit()
        db.refresh(interaction)

        new_state = _interaction_to_state(db, interaction)

        populated = [
            k
            for k in ("hcp_name", "date", "time", "topics", "sentiment", "materials_shared", "samples_distributed")
            if new_state.get(k)
        ]
        summary = ", ".join(populated) if populated else "the basic details"

        return Command(
            update={
                "interaction_state": new_state,
                "messages": [
                    ToolMessage(
                        content=(
                            "Interaction logged successfully! "
                            f"The details ({summary}) have been automatically populated "
                            "based on your summary. Would you like to add a specific "
                            "follow-up action, such as scheduling a meeting?"
                        ),
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 3: Edit_Interaction (mandatory)
# ---------------------------------------------------------------------------

@tool
def Edit_Interaction(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    hcp_name: Optional[str] = None,
    interaction_type: Optional[str] = None,
    date: Optional[str] = None,
    time: Optional[str] = None,
    attendees: Optional[str] = None,
    topics: Optional[str] = None,
    sentiment: Optional[str] = None,
    outcomes: Optional[str] = None,
    add_materials_shared: Optional[List[str]] = None,
    add_samples_distributed: Optional[List[str]] = None,
) -> Command:
    """Apply a fuzzy, PARTIAL update to the interaction currently shown on
    the left-hand form. Only pass the fields the user actually wants
    changed - every argument you omit (leave as None) is left completely
    untouched. Use this for corrections like "Change the sentiment to
    negative and the time to 4 PM" or "Actually the doctor's name was Dr.
    John, not Dr. Smith".

    There must already be a logged interaction in this conversation (call
    Log_Interaction first if there isn't one yet).

    Args:
        hcp_name: New HCP name, only if it needs correcting.
        interaction_type: New interaction type, only if changed.
        date: New ISO date (YYYY-MM-DD), only if changed.
        time: New 24-hour time (HH:MM), only if changed.
        attendees: New attendees text, only if changed.
        topics: New topics text, only if changed.
        sentiment: New sentiment ("Positive"/"Neutral"/"Negative"), only if changed.
        outcomes: New outcomes text, only if changed.
        add_materials_shared: Additional material names to attach (does not remove existing ones).
        add_samples_distributed: Additional sample names to attach (does not remove existing ones).
    """
    current = state.get("interaction_state") or {}
    interaction_id = current.get("interaction_id")

    if not interaction_id:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=(
                            "There is no interaction logged yet in this conversation. "
                            "Please log one first (e.g. describe the visit) before "
                            "requesting an edit."
                        ),
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    db = get_session()
    try:
        interaction = db.query(Interaction).filter_by(id=interaction_id).first()
        if not interaction:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Interaction id {interaction_id} no longer exists in the database.",
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        changed_fields = []

        if hcp_name:
            hcp, candidates = _resolve_hcp(db, hcp_name)
            if hcp is None and len(candidates) > 1:
                options = ", ".join(c.name for c in candidates)
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                content=f"Ambiguous HCP name '{hcp_name}'. Possible matches: {options}.",
                                tool_call_id=tool_call_id,
                            )
                        ]
                    }
                )
            if hcp is None:
                hcp = HCPProfile(name=hcp_name.strip(), specialty=None)
                db.add(hcp)
                db.flush()
            interaction.hcp_id = hcp.hcp_id
            changed_fields.append("HCP name")

        if interaction_type:
            interaction.interaction_type = interaction_type
            changed_fields.append("interaction type")
        if date:
            parsed = _parse_date(date)
            if parsed:
                interaction.date = parsed
                changed_fields.append("date")
        if time:
            parsed = _parse_time(time)
            if parsed:
                interaction.time = parsed
                changed_fields.append("time")
        if attendees:
            interaction.attendees = attendees
            changed_fields.append("attendees")
        if topics:
            interaction.topics = topics
            changed_fields.append("topics")
        if sentiment:
            interaction.sentiment = sentiment
            changed_fields.append("sentiment")
        if outcomes:
            interaction.outcomes = outcomes
            changed_fields.append("outcomes")
        if add_materials_shared:
            _link_items_to_interaction(db, interaction.id, add_materials_shared, "material")
            changed_fields.append("materials shared")
        if add_samples_distributed:
            _link_items_to_interaction(db, interaction.id, add_samples_distributed, "sample")
            changed_fields.append("samples distributed")

        db.commit()
        db.refresh(interaction)

        new_state = _interaction_to_state(db, interaction)

        if not changed_fields:
            message = "No recognizable fields were provided to update - nothing changed."
        else:
            message = (
                f"Interaction updated! Changed: {', '.join(changed_fields)}. "
                "All other fields were left untouched."
            )

        return Command(
            update={
                "interaction_state": new_state,
                "messages": [ToolMessage(content=message, tool_call_id=tool_call_id)],
            }
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 4: Lookup_Items
# ---------------------------------------------------------------------------

@tool
def Lookup_Items(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    item_names: List[str],
    item_type: Optional[str] = None,
) -> Command:
    """Query the materials table to find accurate database IDs for
    "Materials" (e.g. brochures, leave-behinds) and "Samples" (e.g. drug
    samples) mentioned in the chat, distinguishing between the two types.
    If an item doesn't exist yet, it will be created so it can still be
    attached. If there is a currently logged interaction, matched items are
    automatically attached to it and the left form is updated.

    Args:
        item_names: The material/sample names mentioned by the user.
        item_type: "material" or "sample" if known; if omitted, each name
            is matched against existing records of either type first.
    """
    current = state.get("interaction_state") or {}
    interaction_id = current.get("interaction_id")

    db = get_session()
    try:
        resolved = []
        for name in item_names:
            mat = _get_or_create_material(db, name, item_type)
            resolved.append(mat)
        db.commit()

        summary = "; ".join(f"{m.name} (id={m.material_id}, type={m.type.value})" for m in resolved)

        if not interaction_id:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                f"Found/created items: {summary}. No interaction is currently "
                                "logged, so nothing was attached yet - log an interaction first."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        interaction = db.query(Interaction).filter_by(id=interaction_id).first()
        for mat in resolved:
            exists = (
                db.query(InteractionMaterial)
                .filter_by(interaction_id=interaction_id, material_id=mat.material_id)
                .first()
            )
            if not exists:
                db.add(InteractionMaterial(interaction_id=interaction_id, material_id=mat.material_id))
        db.commit()
        db.refresh(interaction)

        new_state = _interaction_to_state(db, interaction)

        return Command(
            update={
                "interaction_state": new_state,
                "messages": [
                    ToolMessage(
                        content=f"Found/created and attached to the current interaction: {summary}.",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 5: Create_Follow_Up_Task
# ---------------------------------------------------------------------------

@tool
def Create_Follow_Up_Task(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    description: str,
    due_date: Optional[str] = None,
) -> Command:
    """Extract a future action/date from the chat and create a follow-up
    task, e.g. "Schedule a follow-up meeting next month" or "Remind me to
    send the study data by Friday". Updates the Follow-up Actions field on
    the left form. Requires a currently logged interaction (its HCP is used
    for the task).

    Args:
        description: What needs to be done.
        due_date: ISO date (YYYY-MM-DD) if a due date was mentioned, else omit.
    """
    current = state.get("interaction_state") or {}
    interaction_id = current.get("interaction_id")
    hcp_id = current.get("hcp_id")

    if not interaction_id or not hcp_id:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=(
                            "There is no interaction logged yet, so I don't know which HCP "
                            "this follow-up is for. Please log an interaction first."
                        ),
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    db = get_session()
    try:
        parsed_due = _parse_date(due_date)
        task = Task(
            hcp_id=hcp_id,
            interaction_id=interaction_id,
            description=description,
            due_date=parsed_due,
        )
        db.add(task)
        db.commit()

        interaction = db.query(Interaction).filter_by(id=interaction_id).first()
        db.refresh(interaction)
        new_state = _interaction_to_state(db, interaction)

        due_txt = f" (due {parsed_due.isoformat()})" if parsed_due else ""
        return Command(
            update={
                "interaction_state": new_state,
                "messages": [
                    ToolMessage(
                        content=f"Follow-up task created: \"{description}\"{due_txt}.",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


ALL_TOOLS = [
    Fetch_HCP_Context,
    Log_Interaction,
    Edit_Interaction,
    Lookup_Items,
    Create_Follow_Up_Task,
]
