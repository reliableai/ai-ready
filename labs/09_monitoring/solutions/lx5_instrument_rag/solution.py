"""
LX-5 reference solution — Instructor only.

Reference implementation of the instrumentation exercise in
`../../exercises/lx5_instrument_rag/starter.py`. Common variants:

  * A student who records `time.time()` (float seconds) and multiplies
    by 1e9 — fine, same precision modulo FP noise.
  * A student who passes `parent=parent_id` explicitly at every call
    site — verbose but correct; skip the stack. Worth discussing.
  * A student who uses a real `opentelemetry.trace.Tracer`. Also
    correct and the ideal production answer; the eight-key dict still
    gets emitted by the SDK's exporter, so the viewer works
    unchanged.

Run:  python solution.py
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from contextlib import contextmanager
from datetime import datetime, timedelta


NOW = datetime(2026, 4, 27, 18, 0, 0)
WINDOW_DAYS = 3
WINDOW_START = NOW - timedelta(days=WINDOW_DAYS)
N_TRACES = 20

QUESTIONS = [
    "How do I rotate my API key?",
    "What's the SLA on the enterprise tier?",
    "Summarise last week's incidents.",
    "Which models are cheapest for summarisation?",
    "Find the runbook for a 5xx spike.",
    "How do I enable audit logs?",
    "What retention applies to deleted tenants?",
    "Show me the cost dashboard query.",
]

MODELS = ["gpt-4o-mini", "gpt-4o"]


def _hex(n: int) -> str:
    return hashlib.md5(f"{n}-lx5".encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Tracer — reference implementation.
# ---------------------------------------------------------------------------

class Tracer:
    """A tiny span recorder with stack-based parent selection."""

    _counter = 0  # monotonic source for deterministic span_ids

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.spans: list[dict] = []
        self._stack: list[str] = []

    def _new_span_id(self) -> str:
        Tracer._counter += 1
        return _hex(Tracer._counter)

    def start_span(self, name: str, attributes: dict | None = None) -> dict:
        parent = self._stack[-1] if self._stack else None
        span = {
            "trace_id":       self.trace_id,
            "span_id":        self._new_span_id(),
            "parent_span_id": parent,
            "name":           name,
            "start_ns":       time.time_ns(),
            "end_ns":         0,           # patched in end_span
            "attributes":     dict(attributes or {}),
            "status":         "OK",        # patched in end_span
        }
        self._stack.append(span["span_id"])
        return span

    def end_span(self, span: dict, status: str = "OK") -> None:
        span["end_ns"] = time.time_ns()
        span["status"] = status
        # Pop regardless of outcome — otherwise an error leaks into
        # the parent of the next span.
        if self._stack and self._stack[-1] == span["span_id"]:
            self._stack.pop()
        self.spans.append(span)

    @contextmanager
    def span(self, name: str, attributes: dict | None = None):
        s = self.start_span(name, attributes)
        try:
            yield s
            self.end_span(s, status="OK")
        except Exception:
            self.end_span(s, status="ERROR")
            raise


# ---------------------------------------------------------------------------
# Fake RAG stages — unchanged from starter.
# ---------------------------------------------------------------------------

def fake_plan(question: str, model: str, rng: random.Random) -> tuple[int, int, str]:
    time.sleep(rng.uniform(0.01, 0.03))
    in_tokens = rng.randint(180, 260)
    out_tokens = rng.randint(20, 60)
    return in_tokens, out_tokens, question[:40]


def fake_retrieve(query: str, rng: random.Random) -> list[str]:
    time.sleep(rng.uniform(0.02, 0.06))
    return [f"doc_{i}" for i in range(rng.randint(3, 7))]


def fake_answer(question: str, docs: list[str], model: str,
                rng: random.Random) -> tuple[int, int, str]:
    time.sleep(rng.uniform(0.05, 0.15))
    in_tokens = rng.randint(600, 1200)
    out_tokens = rng.randint(80, 180)
    return in_tokens, out_tokens, f"Based on {len(docs)} docs: …answer to '{question[:30]}…'"


# ---------------------------------------------------------------------------
# The pipeline with spans wired up.
# ---------------------------------------------------------------------------

def run_query(i: int, rng: random.Random) -> list[dict]:
    trace_id = _hex(i)
    tracer = Tracer(trace_id)
    question = rng.choice(QUESTIONS)
    model    = rng.choice(MODELS)

    with tracer.span("research.task", {
        "agent.name":    "research-assistant",
        "user.question": question,
    }) as root:

        with tracer.span("llm.call", {
            "gen_ai.system":         "openai",
            "gen_ai.request.model":  model,
            "gen_ai.operation.name": "chat.completions",
            "gen_ai.step":           "plan",
        }) as plan_s:
            plan_in, plan_out, query = fake_plan(question, model, rng)
            plan_s["attributes"]["gen_ai.usage.input_tokens"]  = plan_in
            plan_s["attributes"]["gen_ai.usage.output_tokens"] = plan_out

        with tracer.span("retrieval.search", {
            "retrieval.query": query,
            "retrieval.top_k": 5,
        }) as ret_s:
            docs = fake_retrieve(query, rng)
            ret_s["attributes"]["retrieval.hit_count"] = len(docs)
            ret_s["attributes"]["retrieval.index.name"] = "kb.v2"

        with tracer.span("llm.call", {
            "gen_ai.system":         "openai",
            "gen_ai.request.model":  model,
            "gen_ai.operation.name": "chat.completions",
            "gen_ai.step":           "answer",
        }) as ans_s:
            ans_in, ans_out, answer = fake_answer(question, docs, model, rng)
            ans_s["attributes"]["gen_ai.usage.input_tokens"]  = ans_in
            ans_s["attributes"]["gen_ai.usage.output_tokens"] = ans_out

        root["attributes"]["trace.total_latency_ms"] = (
            (time.time_ns() - root["start_ns"]) // 1_000_000
        )

    return tracer.spans


def main() -> None:
    rng = random.Random(42)
    all_spans: list[dict] = []
    for i in range(N_TRACES):
        all_spans.extend(run_query(i, rng))

    with open("spans.ndjson", "w") as f:
        for s in all_spans:
            f.write(json.dumps(s) + "\n")
    with open("spans.js", "w") as f:
        f.write("// Auto-generated by solution.py.\n")
        f.write("window.__SPANS__ = ")
        json.dump(all_spans, f)
        f.write(";\n")

    from collections import Counter
    trace_ids = {s["trace_id"] for s in all_spans}
    kinds = Counter(s["name"] for s in all_spans)
    print(f"wrote {len(all_spans)} spans across {len(trace_ids)} traces")
    print(f"  span-name counts: {dict(kinds)}")


if __name__ == "__main__":
    main()
