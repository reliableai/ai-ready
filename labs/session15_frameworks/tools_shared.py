"""
tools_shared.py
===============

The three tools used by every framework variant in this lab. Plain Python,
no framework imports, so each agent implementation wraps them in whatever
type system it prefers (OpenAI tool schema, LangChain @tool, LlamaIndex
FunctionTool, LangGraph ToolNode).

Tools:
    search_syllabus(query)        -> list[str]         (embedding retrieval)
    get_office_hours(day=None)    -> dict              (structured lookup)
    compute_grade(project, ...)   -> dict              (pure function)

The retrieval tool uses the tiny toy syllabus as its corpus. In a real
system this would hit a vector store; keeping it in-process keeps the lab
free of external infra.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
from openai import OpenAI


# --------------------------------------------------------------------------- #
# Corpus and OpenAI client                                                    #
# --------------------------------------------------------------------------- #
SYLLABUS: list[str] = [
    "AI Design 2026 meets Tuesdays and Thursdays, 10:30-12:00, in Room A205.",
    "Late homework is accepted up to 48 hours late with a 25% penalty per 24 hours.",
    "Office hours are Wednesday 14:00-16:00 in Room A310, or by email appointment.",
    "The course covers building AI systems with LLMs as components: agents, "
    "tools, memory, evaluation, monitoring, and frameworks.",
    "Attendance is recommended but not required. Recordings are posted within 48 hours.",
    "The final project is done in groups of 2-3 students and is presented in week 12.",
    "Prerequisites are Python proficiency and basic familiarity with HTTP APIs.",
    "The reading list is posted on the course site and is updated weekly.",
]

GRADE_WEIGHTS = {"project": 0.40, "homework": 0.30, "exam": 0.20, "participation": 0.10}


def _client() -> tuple[OpenAI, str]:
    """(OpenAI client, embedding-model-name). Used by search_syllabus only."""
    if os.environ.get("OPENROUTER_API_KEY"):
        return (
            OpenAI(api_key=os.environ["OPENROUTER_API_KEY"],
                   base_url="https://openrouter.ai/api/v1"),
            "openai/text-embedding-3-small",
        )
    return OpenAI(), "text-embedding-3-small"


@dataclass
class _Indexed:
    text: str
    vec: np.ndarray


_INDEX: list[_Indexed] | None = None


def _build_index() -> list[_Indexed]:
    global _INDEX
    if _INDEX is None:
        client, model = _client()
        r = client.embeddings.create(model=model, input=SYLLABUS)
        _INDEX = [_Indexed(t, np.asarray(e.embedding, dtype=np.float32))
                  for t, e in zip(SYLLABUS, r.data)]
    return _INDEX


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return 0.0 if denom == 0 else float(a @ b) / denom


# --------------------------------------------------------------------------- #
# Tool 1 -- retrieval                                                         #
# --------------------------------------------------------------------------- #
def search_syllabus(query: str, k: int = 3) -> list[str]:
    """Top-k syllabus snippets for a query, by cosine similarity."""
    idx = _build_index()
    client, model = _client()
    qv = np.asarray(
        client.embeddings.create(model=model, input=query).data[0].embedding,
        dtype=np.float32,
    )
    scored = [(it.text, _cosine(qv, it.vec)) for it in idx]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [t for t, _ in scored[:k]]


# --------------------------------------------------------------------------- #
# Tool 2 -- deterministic structured lookup                                   #
# --------------------------------------------------------------------------- #
def get_office_hours(day: str | None = None) -> dict:
    """Scheduled office hours. If 'day' matches, return that slot; else all."""
    slots = [{"day": "Wednesday", "start": "14:00", "end": "16:00", "room": "A310"}]
    if day:
        slots = [s for s in slots if s["day"].lower() == day.lower()]
    return {"slots": slots, "email_fallback": "fabio.casati@unitn.it"}


# --------------------------------------------------------------------------- #
# Tool 3 -- pure function                                                     #
# --------------------------------------------------------------------------- #
def compute_grade(project: float, homework: float, exam: float,
                  participation: float) -> dict:
    """Apply the 40/30/20/10 weights to four component grades (0-100)."""
    components = {"project": project, "homework": homework,
                  "exam": exam, "participation": participation}
    final = sum(GRADE_WEIGHTS[k] * v for k, v in components.items())
    return {"components": components, "weights": GRADE_WEIGHTS,
            "final_grade": round(final, 2)}


# --------------------------------------------------------------------------- #
# OpenAI tool-schema form -- used by agent_scratch.py                         #
# --------------------------------------------------------------------------- #
OPENAI_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_syllabus",
            "description": "Retrieve top-k relevant snippets from the course syllabus.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural-language query."},
                    "k":     {"type": "integer", "description": "How many snippets.", "default": 3},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_office_hours",
            "description": "Return scheduled office-hour slots. Optionally filter by weekday name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {"type": "string", "description": "e.g. 'Wednesday'. Omit for all days."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_grade",
            "description": "Compute a weighted final grade from four component scores (0-100).",
            "parameters": {
                "type": "object",
                "properties": {
                    "project":       {"type": "number"},
                    "homework":      {"type": "number"},
                    "exam":          {"type": "number"},
                    "participation": {"type": "number"},
                },
                "required": ["project", "homework", "exam", "participation"],
            },
        },
    },
]


TOOL_DISPATCH = {
    "search_syllabus":  lambda args: search_syllabus(**args),
    "get_office_hours": lambda args: get_office_hours(**args),
    "compute_grade":    lambda args: compute_grade(**args),
}
