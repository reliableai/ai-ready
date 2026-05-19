"""
agent_langchain.py
==================

Same course-assistant agent, rebuilt with LangChain.

What the framework gives us:
    * `@tool` decorator -> schema generated from type hints + docstring.
    * `ChatOpenAI.bind_tools(...)` -> tool-calling wired in one line.
    * `InMemoryChatMessageHistory` (and Redis / Postgres variants in prod) ->
      modern replacement for the classic Memory classes. Summary-style
      compression is available via `ConversationSummaryBufferMemory` -- we
      use the simple buffer here and discuss the options in the lecture.
    * `BaseCallbackHandler` -> vendor-free observability hook. Same hook
      subscribed by LangSmith, Langfuse, Phoenix, and OTel exporters.

Install:
    uv add langchain langchain-openai

Run:
    uv run python agent_langchain.py

Environment:
    OPENAI_API_KEY          required
    LANGCHAIN_TRACING_V2    optional, "true" enables LangSmith
    LANGCHAIN_API_KEY       optional
"""

from __future__ import annotations

import os
import time

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

import tools_shared as ts


# --------------------------------------------------------------------------- #
# Tools -- wrap the shared plain-Python functions.                            #
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
TOOLS_BY_NAME = {t.name: t for t in TOOLS}

SYSTEM = (
    "You are the AI Design 2026 course assistant. Help students with questions "
    "about the syllabus, office hours, and grade calculations. Use the provided "
    "tools when they help. Keep answers short."
)


# --------------------------------------------------------------------------- #
# Observability -- the same hook every vendor subscribes to.                  #
# --------------------------------------------------------------------------- #
class AgentTrace(BaseCallbackHandler):
    def __init__(self) -> None:
        self.tokens_in = self.tokens_out = 0
        self.llm_calls = self.tool_calls = 0

    def on_llm_end(self, response, **kwargs) -> None:
        self.llm_calls += 1
        usage = (response.llm_output or {}).get("token_usage", {})
        self.tokens_in  += usage.get("prompt_tokens", 0)
        self.tokens_out += usage.get("completion_tokens", 0)

    def on_tool_start(self, serialized, input_str, **kwargs) -> None:
        self.tool_calls += 1
        print(f"  [tool_start] {serialized.get('name', '?')} args={input_str}")

    def summary(self) -> str:
        return (f"{self.llm_calls} LLM calls, {self.tool_calls} tool calls, "
                f"{self.tokens_in} in / {self.tokens_out} out tokens")


# --------------------------------------------------------------------------- #
# Per-session memory store. Modern API; classic ConversationBufferMemory etc. #
# still work but are considered legacy.                                       #
# --------------------------------------------------------------------------- #
_STORE: dict[str, BaseChatMessageHistory] = {}


def get_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in _STORE:
        _STORE[session_id] = InMemoryChatMessageHistory()
    return _STORE[session_id]


# --------------------------------------------------------------------------- #
# The tool-calling loop. LangChain also ships `AgentExecutor` and             #
# `create_tool_calling_agent`, but for the lecture we write the loop by       #
# hand on top of `bind_tools` so the mapping to agent_scratch.py is 1:1.      #
# --------------------------------------------------------------------------- #
def run_turn(session_id: str, user_text: str, tracer: AgentTrace,
             max_steps: int = 5) -> str:
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0,
                     callbacks=[tracer]).bind_tools(TOOLS)
    history = get_history(session_id)
    history.add_message(HumanMessage(content=user_text))

    for _ in range(max_steps):
        msgs = [SystemMessage(content=SYSTEM), *history.messages]
        ai: AIMessage = llm.invoke(msgs)
        history.add_message(ai)

        if not ai.tool_calls:
            return ai.content

        for tc in ai.tool_calls:
            tool_fn = TOOLS_BY_NAME[tc["name"]]
            result = tool_fn.invoke(tc["args"], config={"callbacks": [tracer]})
            history.add_message(ToolMessage(content=str(result),
                                            tool_call_id=tc["id"]))

    return "[agent stopped: max_steps reached]"


# --------------------------------------------------------------------------- #
# Demo                                                                        #
# --------------------------------------------------------------------------- #
def demo() -> None:
    if os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true":
        print("LangSmith tracing is ON -- traces will appear in your project.")

    tracer = AgentTrace()
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
        reply = run_turn("demo-session", q, tracer)
        print(f"--- ASSISTANT ({time.perf_counter() - t0:.2f}s): {reply}")

    print(f"\n{tracer.summary()}")


if __name__ == "__main__":
    demo()
