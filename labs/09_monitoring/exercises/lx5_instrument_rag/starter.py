"""
LX-5 · Instrument a RAG function with OTel-shaped spans.

You've been handed a small research-assistant RAG pipeline — three
stages (plan → retrieve → answer). Right now it only prints flat
lines. Your job is to wrap each stage in a span so the Demo 5 viewer
can render a waterfall.

What you need to do:

  1. Finish the `Tracer` class below so it produces span dicts with
     `trace_id`, `span_id`, `parent_span_id`, `name`, `start_ns`,
     `end_ns`, `attributes`, `status`.
  2. Wrap the three stages in `run_query()` with `tracer.span(...)`
     context managers, so that:
       - `research.task` is the root span (no parent).
       - `llm.call` (step=plan) and `llm.call` (step=answer) and
         `retrieval.search` are children of the root.
  3. Set the right GenAI attributes on llm.call spans — at minimum
     `gen_ai.system`, `gen_ai.request.model`, `gen_ai.operation.name`,
     `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`.
  4. Run `python starter.py` and open `trace_viewer.html`. You should
     see 20 traces in the left pane; clicking any one shows the
     3-bar waterfall.

See README.md for success criteria and hints. There's a reference
implementation in `../../solutions/lx5_instrument_rag/solution.py` —
try it yourself first.

Run:  python starter.py
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
# Tracer — you fill this in.
# ---------------------------------------------------------------------------

class Tracer:
    """A tiny span recorder.

    Your job:
      - Maintain a stack of "currently open" spans so `start_span` can
        pick the right parent automatically.
      - Hand back a `span` dict that `span(...)` (the context manager)
        can mutate — e.g. setting attributes or status.
      - On context-manager exit, set `end_ns` and append the span to
        `self.spans`. If the block raised, mark the span ERROR and
        re-raise.

    The Demo 5 viewer expects exactly these keys:
        trace_id, span_id, parent_span_id, name,
        start_ns, end_ns, attributes, status
    """

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.spans: list[dict] = []
        self._stack: list[str] = []      # stack of span_ids

    def start_span(self, name: str, attributes: dict | None = None) -> dict:
        # TODO: generate a span_id, take parent from the stack top (or
        # None if the stack is empty), record start_ns, push onto the
        # stack. Don't append to `self.spans` yet — we'll do that in
        # `end_span`. Return the span dict so the caller can mutate it.
        raise NotImplementedError("implement start_span()")

    def end_span(self, span: dict, status: str = "OK") -> None:
        # TODO: set end_ns, set status, pop the stack, append to
        # self.spans.
        raise NotImplementedError("implement end_span()")

    @contextmanager
    def span(self, name: str, attributes: dict | None = None):
        """Use this as `with tracer.span("foo") as s: ...`."""
        s = self.start_span(name, attributes)
        try:
            yield s
            self.end_span(s, status="OK")
        except Exception:
            self.end_span(s, status="ERROR")
            raise


# ---------------------------------------------------------------------------
# Fake RAG stages. Don't edit the bodies — wrap them with spans.
# ---------------------------------------------------------------------------

def fake_plan(question: str, model: str, rng: random.Random) -> tuple[int, int, str]:
    """Pretend to call an LLM to plan which tools to use.

    Returns (input_tokens, output_tokens, chosen_query).
    """
    time.sleep(rng.uniform(0.01, 0.03))        # tiny fake latency
    in_tokens = rng.randint(180, 260)
    out_tokens = rng.randint(20, 60)
    return in_tokens, out_tokens, question[:40]


def fake_retrieve(query: str, rng: random.Random) -> list[str]:
    """Pretend to hit a vector DB."""
    time.sleep(rng.uniform(0.02, 0.06))
    return [f"doc_{i}" for i in range(rng.randint(3, 7))]


def fake_answer(question: str, docs: list[str], model: str,
                rng: random.Random) -> tuple[int, int, str]:
    """Pretend to call an LLM to compose the answer."""
    time.sleep(rng.uniform(0.05, 0.15))
    in_tokens = rng.randint(600, 1200)
    out_tokens = rng.randint(80, 180)
    return in_tokens, out_tokens, f"Based on {len(docs)} docs: …answer to '{question[:30]}…'"


# ---------------------------------------------------------------------------
# The pipeline — wire up the tracer here.
# ---------------------------------------------------------------------------

def run_query(i: int, rng: random.Random) -> list[dict]:
    """Run one research query and return the spans it produced."""
    trace_id = _hex(i)
    tracer = Tracer(trace_id)
    question = rng.choice(QUESTIONS)
    model    = rng.choice(MODELS)

    # TODO: wrap everything below in `with tracer.span("research.task", ...)`.
    # TODO: wrap each stage call in its own child span.
    #   - plan            → "llm.call" with gen_ai.step="plan"
    #   - retrieve        → "retrieval.search"
    #   - answer          → "llm.call" with gen_ai.step="answer"
    # On each llm.call, set the gen_ai.* attributes.
    # On retrieval.search, set retrieval.query / retrieval.hit_count.

    plan_in, plan_out, query = fake_plan(question, model, rng)
    docs = fake_retrieve(query, rng)
    ans_in, ans_out, answer = fake_answer(question, docs, model, rng)

    # Right now `tracer.spans` is empty — implement the tracer above
    # and wire up the spans so this list has 4 entries (1 root + 3 children).
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
        f.write("// Auto-generated by starter.py.\n")
        f.write("window.__SPANS__ = ")
        json.dump(all_spans, f)
        f.write(";\n")

    trace_ids = {s.get("trace_id") for s in all_spans}
    from collections import Counter
    kinds = Counter(s.get("name") for s in all_spans)
    print(f"wrote {len(all_spans)} spans across {len(trace_ids)} traces")
    print(f"  span-name counts: {dict(kinds)}")
    if not all_spans:
        print("\n  (nothing here yet — you need to finish the Tracer "
              "and wire up the spans.)")


if __name__ == "__main__":
    main()
