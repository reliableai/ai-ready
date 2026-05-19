"""
agent_langgraph.py
==================

Same course-assistant agent, rebuilt as a LangGraph state machine with a
checkpointer. This is the shape LangChain recommends for new agentic
systems: memory is first-class state, control flow is explicit, and
time-travel debugging is free.

Graph:

        (entry)
           |
           v
      +---------+        tools_condition
      |  agent  | -------------------------- > (end, if no tool_calls)
      +---------+
           | tool_calls present
           v
      +---------+
      |  tools  |       (ToolNode runs all pending tool calls in parallel)
      +---------+
           |
           +------> back to agent

Install:
    uv add langgraph langchain-openai

Run:
    uv run python agent_langgraph.py

Environment:
    OPENAI_API_KEY    required
"""

from __future__ import annotations

import time
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

import tools_shared as ts


# --------------------------------------------------------------------------- #
# Tools                                                                       #
# --------------------------------------------------------------------------- #
@tool
def search_syllabus(query: str, k: int = 3) -> list[str]:
    """Retrieve top-k relevant snippets from the course syllabus."""
    return ts.search_syllabus(query, k)


@tool
def get_office_hours(day: str | None = None) -> dict:
    """Return scheduled office-hour slots; filter by weekday if provided."""
    return ts.get_office_hours(day)


@tool
def compute_grade(project: float, homework: float, exam: float,
                  participation: float) -> dict:
    """Compute a weighted final grade from four component scores (0-100)."""
    return ts.compute_grade(project, homework, exam, participation)


TOOLS = [search_syllabus, get_office_hours, compute_grade]

SYSTEM = SystemMessage(content=(
    "You are the AI Design 2026 course assistant. Help students with questions "
    "about the syllabus, office hours, and grade calculations. Use the provided "
    "tools when they help. Keep answers short."
))


# --------------------------------------------------------------------------- #
# State -- this IS the memory. add_messages is a reducer that appends.        #
# --------------------------------------------------------------------------- #
class State(TypedDict):
    messages: Annotated[list, add_messages]


def build_app():
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0).bind_tools(TOOLS)

    def agent_node(state: State) -> dict:
        # Prepend the system message once per invocation; state["messages"]
        # carries only user / assistant / tool turns.
        ai: AIMessage = llm.invoke([SYSTEM, *state["messages"]])
        return {"messages": [ai]}

    graph = StateGraph(State)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.set_entry_point("agent")
    # tools_condition inspects the last AIMessage: if it has tool_calls -> tools, else END.
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    # In-memory SQLite: every transition is checkpointed. Same thread_id =
    # same conversation across restarts. Swap for Postgres/Redis in prod.
    checkpointer = SqliteSaver.from_conn_string(":memory:")
    return graph.compile(checkpointer=checkpointer)


# --------------------------------------------------------------------------- #
# Demo                                                                        #
# --------------------------------------------------------------------------- #
def demo() -> None:
    app = build_app()
    config = {"configurable": {"thread_id": "demo-session"}}

    turns = [
        "What's the attendance policy?",
        "And when are your office hours?",
        "If I get 85 on the project, 90 on homework, 75 on the exam, and 100 "
        "on participation, what's my final grade?",
        "Remind me: where do we meet on Tuesdays?",
    ]

    for q in turns:
        print(f"\n--- USER: {q}")
        t0 = time.perf_counter()
        result = app.invoke({"messages": [HumanMessage(content=q)]}, config=config)
        reply = result["messages"][-1].content
        print(f"--- ASSISTANT ({time.perf_counter() - t0:.2f}s): {reply}")

    # Time-travel: inspect every checkpoint for this thread.
    print("\nCheckpoints for 'demo-session':")
    for cp in app.get_state_history(config):
        step = cp.metadata.get("step", "?")
        nxt = list(cp.next) if cp.next else ["(terminal)"]
        n_msgs = len(cp.values.get("messages", []))
        print(f"  step={step}  msgs={n_msgs}  next={nxt}")


if __name__ == "__main__":
    demo()
