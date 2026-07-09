import time

from datetime import datetime

from groq import RateLimitError
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition

from app.config import settings
from app.state import AgentState
from app.tools import ALL_TOOLS


def build_system_prompt() -> str:
    # The model has no built-in access to a real clock - without this, it
    # guesses a plausible-looking but WRONG time (e.g. defaulting to some
    # generic "2:30 PM" pattern from training data) whenever the rep doesn't
    # state one explicitly. Injecting the actual current date/time here,
    # fresh on every call, is what lets it correctly resolve "today",
    # "just now", "this morning", etc. It reads the server process's local
    # system clock, so it's correct as long as the machine running the
    # backend has its OS timezone/clock set correctly (e.g. IST on a system
    # located in India) - no timezone conversion needed on top of that.
    now = datetime.now()
    current_dt_str = now.strftime("%A, %Y-%m-%d %H:%M")

    return f"""You are the AI Assistant embedded in a life-science field \
rep's CRM, in the "Log HCP Interaction" screen.

The current real date and time is: {current_dt_str} (24-hour clock). Use \
this as ground truth for resolving "today", "now", "this morning", "next \
Monday", etc. - do not guess or invent a different current time.

GOLDEN RULE: the left-hand form is 100% read-only. The rep can NEVER type \
into it directly. The ONLY way any field on that form gets filled in or \
changed is through you calling your tools based on what the rep tells you \
in this chat. Every single field change must go through a tool call - never \
just say you updated something without actually calling the tool.

How to behave:
- If the rep describes a visit/call/meeting for the first time in this \
  conversation (e.g. "Today I met with Dr. Smith and discussed product X \
  efficiency, sentiment was positive, shared brochures"), call Log_Interaction \
  with every entity you can extract: HCP name, interaction type, date, time, \
  attendees, topics, sentiment, outcomes, and any materials/samples mentioned.
- Date/time handling: if the rep states an explicit date and/or time, \
  normalize it to YYYY-MM-DD / 24-hour HH:MM using the current date/time \
  above as reference. If the rep does NOT mention a specific time at all, \
  leave the `time` argument out entirely (do not guess or default to a \
  round number like 2:30pm) - the system will fill in the actual current \
  time automatically. Same for `date`: if unstated, omit it rather than \
  guessing.
- If an interaction already exists in this conversation and the rep corrects \
  or adds specific details (e.g. "change the sentiment to negative and the \
  time to 4pm", "actually it was Dr. John"), call Edit_Interaction with ONLY \
  the fields that need to change. Never resend fields that aren't changing.
- If the HCP's name is ambiguous or you're not sure it exists yet, call \
  Fetch_HCP_Context to check before logging or editing.
- If the rep mentions specific brochures/samples by name and you want to \
  confirm/attach them explicitly (outside of an initial Log_Interaction \
  call), use Lookup_Items.
- If the rep mentions a future action (schedule a follow-up, send \
  something by a date, etc.), call Create_Follow_Up_Task.
- After a tool call succeeds, reply to the rep in a short, friendly \
  confirmation summarizing what changed, and proactively suggest a next \
  step (e.g. asking about a follow-up action) when appropriate.
- If the rep asks something unrelated to logging/editing this interaction, \
  just answer conversationally without calling tools.
"""


def invoke_with_rate_limit_retry(llm_with_tools, messages, max_attempts=4):
    """Groq's free/on-demand tier has a low tokens-per-minute cap, and a
    growing conversation (full history resent every turn) can trip it after
    just a handful of messages. The API's own error message tells us almost
    exactly how long to wait (often well under a second) - so retrying
    briefly here is far better UX than surfacing a raw 429 as a 500 error.
    """
    delay = 1.0
    for attempt in range(max_attempts):
        try:
            return llm_with_tools.invoke(messages)
        except RateLimitError as e:
            if attempt == max_attempts - 1:
                raise
            print(f"[agent] Groq rate limit hit (attempt {attempt + 1}/{max_attempts}), "
                  f"waiting {delay:.1f}s before retrying: {e}")
            time.sleep(delay)
            delay *= 2  # exponential backoff: 1s, 2s, 4s, ...


def build_agent():
    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy backend/.env.example to backend/.env "
            "and fill in your key from https://console.groq.com/keys"
        )

    llm_kwargs = dict(
        model=settings.GROQ_MODEL,
        api_key=settings.GROQ_API_KEY,
        temperature=0,
        timeout=30,  # seconds - fail fast instead of hanging indefinitely
        max_retries=1,
    )
    # openai/gpt-oss-20b and openai/gpt-oss-120b are "reasoning" models on Groq.
    # Their default reasoning_effort ("medium") can take 30-60+ seconds and,
    # per Groq's own community forum, occasionally returns an empty message
    # with no tool call at all on agentic/tool-use tasks. "low" is much
    # faster and noticeably more reliable for a simple extraction task like
    # this one. This param only applies to gpt-oss models; ChatGroq ignores
    # it harmlessly for other model families... actually it will raise if
    # passed to a model that doesn't support it, so only set it for gpt-oss.
    if "gpt-oss" in settings.GROQ_MODEL:
        llm_kwargs["reasoning_effort"] = "low"

    llm = ChatGroq(**llm_kwargs)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    def agent_node(state: AgentState):
        messages = state["messages"]
        # Rebuilt fresh every turn (not just once at graph-build time) so
        # the injected current date/time is always accurate, even for a
        # conversation that's been open a while.
        fresh_system = SystemMessage(content=build_system_prompt())
        if messages and isinstance(messages[0], SystemMessage):
            messages = [fresh_system] + list(messages[1:])
        else:
            messages = [fresh_system] + list(messages)

        response = invoke_with_rate_limit_retry(llm_with_tools, messages)

        # --- DEBUG LOGGING: prints every model turn to the terminal so we
        # can see exactly what's happening on each agent<->tools iteration
        # (tool name/args requested, or plain text). Remove once things are
        # working reliably. ---
        if response.tool_calls:
            for tc in response.tool_calls:
                print(f"[agent] -> tool call: {tc['name']}({tc['args']})")
        else:
            print(f"[agent] -> text response: {response.content!r}")

        # Documented gpt-oss-on-Groq failure mode: an AIMessage with empty
        # content AND no tool_calls - the model just didn't produce anything
        # usable. Retry once with a nudge rather than surfacing "(no response
        # text)" to the rep.
        if not response.content and not getattr(response, "tool_calls", None):
            nudge = HumanMessage(
                content=(
                    "(system: your previous response was empty - please "
                    "either call the appropriate tool now, or reply with a "
                    "short text message.)"
                )
            )
            response = invoke_with_rate_limit_retry(llm_with_tools, messages + [nudge])
            print(f"[agent] -> retry response: tool_calls={response.tool_calls!r} content={response.content!r}")
            if not response.content and not getattr(response, "tool_calls", None):
                response = AIMessage(
                    content=(
                        "I wasn't able to process that just now - could you "
                        "rephrase, or try again?"
                    )
                )

        return {"messages": [response]}

    def log_tool_results(state: AgentState):
        # Pass-through node purely for visibility: prints what each tool
        # actually returned (success message, or the validation/DB error
        # that's causing a retry loop) before handing back to the agent.
        last = state["messages"][-1]
        print(f"[tools] <- result: {getattr(last, 'content', last)!r}")
        return {}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(ALL_TOOLS, handle_tool_errors=False))
    graph.add_node("log_tool_results", log_tool_results)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "log_tool_results")
    graph.add_edge("log_tool_results", "agent")

    checkpointer = MemorySaver()
    compiled = graph.compile(checkpointer=checkpointer)
    # Hard cap on agent<->tools loop iterations. Without this, a model that
    # keeps calling a tool it's unhappy with (e.g. repeatedly retrying a
    # malformed call) can loop for a very long time before LangGraph's own
    # default limit kicks in - each iteration is a real Groq call, so even
    # a few dozen iterations at several seconds each adds up to minutes of
    # apparent "hanging" with no response. 15 is more than enough for this
    # app's tool flows and fails faster/clearer when something is looping.
    compiled.config = {"recursion_limit": 15}
    return compiled


# Singleton compiled graph, built lazily on first use so a missing API key
# only breaks the /api/chat endpoint, not the whole app (e.g. `/health" and
# docs still work without a key configured).
_agent_app = None


def get_agent():
    global _agent_app
    if _agent_app is None:
        _agent_app = build_agent()
    return _agent_app