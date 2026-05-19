"""
agent_llamaindex.py
===================

Same course-assistant agent, rebuilt with LlamaIndex.

What the framework gives us:
    * `FunctionTool.from_defaults(...)` -> wraps any Python callable as a tool.
    * `FunctionAgent` (the modern AgentWorkflow API) -> handles the
      tool-calling loop, retries, and structured output.
    * `ChatMemoryBuffer` -> token-budgeted multi-turn memory.
    * Built-in observability via `Settings.callback_manager` and the
      Phoenix / Langfuse integrations (commented; uncomment in the lab).

Install:
    uv add llama-index llama-index-llms-openai

Run:
    uv run python agent_llamaindex.py

Environment:
    OPENAI_API_KEY    required
"""

from __future__ import annotations

import asyncio
import time

from llama_index.core import Settings
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI

import tools_shared as ts


SYSTEM = (
    "You are the AI Design 2026 course assistant. Help students with questions "
    "about the syllabus, office hours, and grade calculations. Use the provided "
    "tools when they help. Keep answers short."
)


def build_agent() -> tuple[FunctionAgent, ChatMemoryBuffer]:
    Settings.llm = OpenAI(model="gpt-4.1-mini", temperature=0)

    tools = [
        FunctionTool.from_defaults(
            fn=ts.search_syllabus,
            name="search_syllabus",
            description="Retrieve top-k relevant snippets from the course syllabus.",
        ),
        FunctionTool.from_defaults(
            fn=ts.get_office_hours,
            name="get_office_hours",
            description="Return scheduled office-hour slots; filter by weekday if provided.",
        ),
        FunctionTool.from_defaults(
            fn=ts.compute_grade,
            name="compute_grade",
            description="Compute a weighted final grade from four component scores (0-100).",
        ),
    ]

    memory = ChatMemoryBuffer.from_defaults(token_limit=2000)
    agent = FunctionAgent(tools=tools, llm=Settings.llm, system_prompt=SYSTEM)
    return agent, memory


# --------------------------------------------------------------------------- #
# Demo                                                                        #
# --------------------------------------------------------------------------- #
async def _async_demo() -> None:
    agent, memory = build_agent()
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
        # `agent.run` consumes a string + memory and returns the agent's reply,
        # threading tool calls under the hood.
        response = await agent.run(user_msg=q, memory=memory)
        print(f"--- ASSISTANT ({time.perf_counter() - t0:.2f}s): {response}")


def demo() -> None:
    asyncio.run(_async_demo())


if __name__ == "__main__":
    demo()
