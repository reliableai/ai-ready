"""
minimal_agent.py — the ~30-LoC core of the lab's agent.

The agent has one tool (`search`) and one LLM call that decides whether to
answer directly or to call the tool and then answer. We use a deterministic
*mock* LLM so the lab runs offline (no API keys). A commented block below
shows how to swap in a real provider.

Everything observability-related lives in `monitoring_lab.py`. This file is
kept intentionally small so the pedagogical core — the agent loop itself —
fits on one page.

# -- To use a real provider (optional) --------------------------------------
# from openai import OpenAI
# client = OpenAI()
# def llm_call(prompt: str) -> str:
#     r = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[{"role": "user", "content": prompt}],
#         response_format={"type": "json_object"},
#     )
#     return r.choices[0].message.content
# ---------------------------------------------------------------------------
"""
from __future__ import annotations
import json, random, re
from dataclasses import dataclass
from typing import Callable


# ---------- Prompt versions (students will break one of these) -------------

PROMPT_V1 = (
    "You are a tiny research assistant. Given a question, either answer "
    "directly or call the `search` tool. Respond ONLY with JSON of shape "
    '{"action": "answer"|"search", "query": str|null, "answer": str|null, '
    '"confidence": float}.'
)

# A deliberately-broken variant for Exercise 2: half the time, emits
# malformed JSON so students can watch guardrails repair/reject it.
PROMPT_V2 = PROMPT_V1 + "  Sometimes forget the closing brace."


# ---------- The one tool ---------------------------------------------------

_SEARCH_INDEX = {
    "capital of france": "Paris",
    "author of 1984": "George Orwell",
    "boiling point of water": "100°C at 1 atm",
    "tallest mountain": "Mount Everest",
}

def search_tool(query: str) -> str:
    """Return a canned result, or 'no results' for unknown queries."""
    return _SEARCH_INDEX.get(query.strip().lower(), "no results")


# ---------- The mock LLM ---------------------------------------------------

def mock_llm(prompt: str, seed: int | None = None, broken: bool = False) -> str:
    """
    A deterministic, seed-able stand-in for a real model. It pattern-matches
    the user's question, decides answer-vs-search, and returns JSON. When
    `broken=True`, it occasionally emits malformed JSON so students can
    exercise the guardrail repair path.
    """
    rnd = random.Random(seed)
    # Extract the trailing user question (very simple).
    m = re.search(r"Question:\s*(.+)$", prompt, flags=re.S)
    question = m.group(1).strip() if m else prompt.strip()
    ql = question.lower()

    # Cheap routing: if we "know" the answer, answer directly; else search.
    for key, value in _SEARCH_INDEX.items():
        if key in ql:
            payload = {"action": "answer", "query": None,
                       "answer": value, "confidence": 0.95}
            break
    else:
        payload = {"action": "search", "query": question,
                   "answer": None, "confidence": 0.5}

    out = json.dumps(payload)
    # Inject malformed JSON with ~50% probability when broken=True.
    if broken and rnd.random() < 0.5:
        out = out.rstrip("}")  # drop closing brace
    return out


# ---------- The agent loop (this is the ~30 LoC core) ----------------------

@dataclass
class AgentResult:
    answer: str
    tool_calls: int
    raw_decisions: list[dict]

def run_agent(
    question: str,
    llm: Callable[[str], str] = mock_llm,
    prompt_version: str = "v1",
    max_steps: int = 2,
) -> AgentResult:
    """Minimal ReAct-style loop: decide → (maybe search) → answer."""
    system = PROMPT_V1 if prompt_version == "v1" else PROMPT_V2
    decisions: list[dict] = []
    query_for_tool = None
    for _ in range(max_steps):
        prompt = f"{system}\n\nQuestion: {question}"
        if query_for_tool is not None:
            prompt += f"\nSearch result: {search_tool(query_for_tool)}"
        raw = llm(prompt)
        decision = json.loads(raw)          # may raise — guardrail catches it
        decisions.append(decision)
        if decision["action"] == "answer":
            return AgentResult(decision["answer"] or "", len(decisions) - 1, decisions)
        query_for_tool = decision["query"]
    return AgentResult("(no answer)", max_steps - 1, decisions)
