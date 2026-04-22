"""
agent_scratch.py
================

A full tool-calling agent, written by hand. No framework. The goal: make
every moving part visible so the framework versions in this folder have
an honest baseline to compare against.

What this agent does:
    * Maintains a conversation history (multi-turn memory).
    * Compresses older turns into a running summary when the window grows
      past a token budget ("summary + recent window" = the default
      strategy from L3).
    * Exposes three tools (search_syllabus, get_office_hours, compute_grade)
      via the OpenAI tool-calling schema and runs the standard tool loop:
          user turn -> model -> [tool call? -> dispatch -> feed result back]*
                                                                     -> final text
    * Logs every step as a structured event (observability without a vendor).

Run:
    uv run python agent_scratch.py

Environment:
    OPENAI_API_KEY         (or OPENROUTER_API_KEY)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

from openai import OpenAI

from tools_shared import OPENAI_TOOL_SCHEMAS, TOOL_DISPATCH


# --------------------------------------------------------------------------- #
# Client setup                                                                #
# --------------------------------------------------------------------------- #
def make_client() -> tuple[OpenAI, str]:
    if os.environ.get("OPENROUTER_API_KEY"):
        return (OpenAI(api_key=os.environ["OPENROUTER_API_KEY"],
                       base_url="https://openrouter.ai/api/v1"),
                "openai/gpt-4.1-mini")
    return OpenAI(), "gpt-4.1-mini"


SYSTEM_PROMPT = (
    "You are the AI Design 2026 course assistant. Help students with questions "
    "about the syllabus, office hours, and grade calculations. Use the provided "
    "tools when they help. If a question is ambiguous, ask one clarifying "
    "question before calling tools. Keep answers short."
)


# --------------------------------------------------------------------------- #
# Observability -- a minimal structured tracer.                               #
# --------------------------------------------------------------------------- #
@dataclass
class Trace:
    events: list[dict] = field(default_factory=list)

    def emit(self, kind: str, **payload) -> None:
        self.events.append({"t": time.time(), "kind": kind, **payload})
        # Print a terse live feed too.
        print(f"  [{kind}] {json.dumps(payload, default=str)[:120]}")


# --------------------------------------------------------------------------- #
# Memory: summary + recent window                                             #
# --------------------------------------------------------------------------- #
@dataclass
class Memory:
    """Summary of older turns + the last `window` message objects verbatim."""
    window: int = 8
    summary: str = ""
    recent: list[dict] = field(default_factory=list)

    def add(self, msg: dict) -> None:
        self.recent.append(msg)
        if len(self.recent) > self.window:
            self._compress()

    def _compress(self) -> None:
        """Summarize the oldest half of recent history into self.summary."""
        half = len(self.recent) // 2
        to_fold, self.recent = self.recent[:half], self.recent[half:]
        client, model = make_client()
        fold_text = json.dumps(to_fold, default=str)[:4000]
        r = client.chat.completions.create(
            model=model, temperature=0,
            messages=[
                {"role": "system", "content":
                 "Summarise the conversation fragment below in <=4 sentences. "
                 "Keep facts a follow-up question might need."},
                {"role": "user", "content":
                 f"Existing summary:\n{self.summary}\n\nFragment:\n{fold_text}"},
            ],
        )
        self.summary = (r.choices[0].message.content or "").strip()

    def render(self) -> list[dict]:
        """The list of messages to actually send to the model this turn."""
        msgs: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if self.summary:
            msgs.append({"role": "system",
                         "content": f"Conversation so far (summary):\n{self.summary}"})
        msgs.extend(self.recent)
        return msgs


# --------------------------------------------------------------------------- #
# The tool-calling loop                                                       #
# --------------------------------------------------------------------------- #
def run_turn(memory: Memory, user_msg: str, trace: Trace,
             max_steps: int = 5) -> str:
    """Take one user message through the agent loop; return the final reply."""
    client, model = make_client()
    memory.add({"role": "user", "content": user_msg})
    trace.emit("user", text=user_msg)

    for step in range(max_steps):
        trace.emit("llm_start", step=step, history_len=len(memory.recent))
        r = client.chat.completions.create(
            model=model, temperature=0,
            messages=memory.render(),
            tools=OPENAI_TOOL_SCHEMAS,
            tool_choice="auto",
        )
        msg = r.choices[0].message
        trace.emit("llm_end", step=step,
                   tokens_in=r.usage.prompt_tokens,
                   tokens_out=r.usage.completion_tokens,
                   tool_calls=len(msg.tool_calls or []))

        # Record whatever the model produced (text and/or tool calls).
        memory.add(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            return msg.content or ""

        # Dispatch each tool call and append the tool result as a new message.
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            trace.emit("tool_start", name=tc.function.name, args=args)
            try:
                result = TOOL_DISPATCH[tc.function.name](args)
                status = "ok"
            except Exception as e:  # noqa: BLE001
                result, status = {"error": str(e)}, "error"
            trace.emit("tool_end", name=tc.function.name, status=status)
            memory.add({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, default=str),
            })

    return "[agent stopped: max_steps reached]"


# --------------------------------------------------------------------------- #
# Demo                                                                        #
# --------------------------------------------------------------------------- #
def demo() -> None:
    memory, trace = Memory(), Trace()

    # Three turns that exercise all three tools and multi-turn memory.
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
        reply = run_turn(memory, q, trace)
        print(f"--- ASSISTANT ({time.perf_counter() - t0:.2f}s): {reply}")

    print(f"\n{sum(1 for e in trace.events if e['kind'] == 'llm_end')} LLM calls total; "
          f"{sum(1 for e in trace.events if e['kind'] == 'tool_start')} tool calls total.")
    if memory.summary:
        print(f"Running summary:\n  {memory.summary}")


if __name__ == "__main__":
    demo()
