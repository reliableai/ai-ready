# %% [markdown]
# # Demo 5 — generate OTel-shaped spans for a Stage-B research agent
#
# Writes ~40 traces (a few hundred spans) to `spans.ndjson` + `spans.js`,
# simulating a small RAG-style assistant:
#
#     user_question
#       └── research.task                      ← root span
#           ├── llm.call (plan)                ← decide which tools to call
#           ├── retrieval.search               ← vector-db lookup
#           │    └── tool.http (optional)      ← only on day-4+ when we added web fallback
#           └── llm.call (answer)              ← compose final answer
#
# The spans follow OTel's data model: `trace_id`, `span_id`, `parent_span_id`,
# `name`, `start_ns`, `end_ns`, `attributes`, `status`. On the `llm.call`
# spans we set the GenAI semantic-convention attributes
# (`gen_ai.request.model`, `gen_ai.usage.input_tokens`, etc.). On the
# `tool.*` spans we set a short arg/result excerpt.
#
# Two traces are deliberately unhealthy — one retrieval timeout, one where the
# plan step asked for a tool that doesn't exist and the answer step still ran
# with empty context. Both show up in the viewer with a red status badge.
#
# Run as a script (`python gen_spans.py`) or step through cell-by-cell.

# %% Imports
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta


# %% Window & questions
NOW = datetime(2026, 4, 27, 18, 0, 0)
WINDOW_DAYS = 7
WINDOW_START = NOW - timedelta(days=WINDOW_DAYS)
N_TRACES = 40

QUESTIONS = [
    "How do I rotate my API key?",
    "Is the v3 integration with Stripe still supported?",
    "What's the difference between reserved and on-demand instances?",
    "Show me last month's top 10 failing endpoints.",
    "Summarise the 2025 incident reports for the Europe region.",
    "Which retention policy applies to audit logs in the EU tenant?",
    "Is the SLA for 'GET /feed' different on the enterprise tier?",
    "Find the escalation runbook for a 5xx spike on checkout.",
    "What's the cheapest way to load-test a staging environment?",
    "When was the rate-limit bumped for team_id=42?",
]

MODELS = ["gpt-4o-mini", "gpt-4o"]


# %% Span helpers
def _hex(n: int) -> str:
    return hashlib.md5(f"{n}-demo5".encode()).hexdigest()[:16]


def mk_span(trace_id: str, parent: str | None, name: str,
            start: int, dur_ns: int, attributes: dict,
            status: str = "OK") -> dict:
    return {
        "trace_id":       trace_id,
        "span_id":        _hex(random.randint(0, 10**9)),
        "parent_span_id": parent,
        "name":           name,
        "start_ns":       start,
        "end_ns":         start + dur_ns,
        "attributes":     attributes,
        "status":         status,
    }


# %% Trace generator
def generate_trace(i: int, rng: random.Random) -> list[dict]:
    """Build one trace's worth of spans."""
    ts = WINDOW_START + timedelta(
        seconds=rng.random() * WINDOW_DAYS * 86400
    )
    day_frac = (ts - WINDOW_START).total_seconds() / 86400
    trace_id = _hex(i)
    t0 = int(ts.timestamp() * 1e9)           # start of the whole trace, in ns
    question = rng.choice(QUESTIONS)
    model    = rng.choice(MODELS)

    spans: list[dict] = []
    cursor = t0

    # --- Root span ---------------------------------------------------------
    root_start = cursor
    root_attrs = {
        "agent.name":   "research-assistant",
        "user.question": question,
        "session.id":   f"sess_{_hex(i + 77)[:10]}",
    }
    # We'll patch duration in at the end.
    root = mk_span(trace_id, None, "research.task", root_start, 0, root_attrs)
    spans.append(root)
    cursor += int(rng.uniform(1e6, 3e6))       # small gap before first child

    # --- Plan step (LLM call) ---------------------------------------------
    plan_dur = int(rng.lognormvariate(19.1, 0.3))       # ~200 ms
    plan_in  = rng.randint(180, 260)
    plan_out = rng.randint(20, 60)
    plan = mk_span(trace_id, root["span_id"], "llm.call", cursor, plan_dur, {
        "gen_ai.system":              "openai",
        "gen_ai.request.model":       model,
        "gen_ai.operation.name":      "chat.completions",
        "gen_ai.usage.input_tokens":  plan_in,
        "gen_ai.usage.output_tokens": plan_out,
        "gen_ai.step":                "plan",
        "prompt.excerpt":             f"Decide which tools to call for: {question[:40]}…",
        "completion.excerpt":         'Use retrieval.search with query="' + question[:30] + '"',
    })
    spans.append(plan)
    cursor += plan_dur + int(rng.uniform(5e5, 2e6))

    # --- Retrieval step ----------------------------------------------------
    ret_dur = int(rng.lognormvariate(20.0, 0.25))       # ~500 ms
    # 1 trace in ~20 has a retrieval timeout.
    retrieval_timeout = (i % 23 == 0)
    if retrieval_timeout:
        ret_dur = int(5e9)                              # 5 s

    ret_status = "ERROR" if retrieval_timeout else "OK"
    ret = mk_span(trace_id, root["span_id"], "retrieval.search", cursor, ret_dur, {
        "retrieval.top_k":          5,
        "retrieval.query":          question[:60],
        "retrieval.hit_count":      0 if retrieval_timeout else rng.randint(3, 7),
        "retrieval.index.name":     "kb.v2",
        "error.type":               "timeout" if retrieval_timeout else None,
    }, status=ret_status)
    spans.append(ret)

    # Optional http fallback — added on day 4 onward.
    if day_frac >= 4 and rng.random() < 0.35 and not retrieval_timeout:
        http_dur = int(rng.lognormvariate(19.3, 0.3))
        http = mk_span(trace_id, ret["span_id"], "tool.http", cursor + ret_dur // 4,
                       http_dur, {
            "http.method":    "GET",
            "http.url":       "https://api.internal/kb/search",
            "http.status":    200,
        })
        spans.append(http)

    cursor += ret_dur + int(rng.uniform(5e5, 2e6))

    # --- Answer step (LLM call) -------------------------------------------
    # On retrieval timeout we still call the model, but with empty context.
    # This is the "fail-open on retrieval, fail-closed nowhere" pattern; the
    # answer will be a hedge.
    ans_dur = int(rng.lognormvariate(20.3, 0.3))
    ans_in  = 120 if retrieval_timeout else rng.randint(600, 1200)
    ans_out = rng.randint(80, 180)
    ans = mk_span(trace_id, root["span_id"], "llm.call", cursor, ans_dur, {
        "gen_ai.system":              "openai",
        "gen_ai.request.model":       model,
        "gen_ai.operation.name":      "chat.completions",
        "gen_ai.usage.input_tokens":  ans_in,
        "gen_ai.usage.output_tokens": ans_out,
        "gen_ai.step":                "answer",
        "prompt.excerpt":             f"Context: {0 if retrieval_timeout else ans_in // 4} tokens · {question[:40]}…",
        "completion.excerpt":         ("I don't have enough information to answer that."
                                       if retrieval_timeout
                                       else f"Based on the docs: …answer to '{question[:30]}…'"),
    })
    spans.append(ans)
    cursor += ans_dur

    # Patch root duration.
    root["end_ns"] = cursor
    root["attributes"]["trace.total_latency_ms"] = (cursor - root_start) // 1_000_000
    if retrieval_timeout:
        root["status"] = "ERROR"
        root["attributes"]["error.type"] = "retrieval_timeout"

    return spans


# %% Driver
def main() -> None:
    rng = random.Random(7)
    all_spans: list[dict] = []
    for i in range(N_TRACES):
        all_spans.extend(generate_trace(i, rng))

    with open("spans.ndjson", "w") as f:
        for s in all_spans:
            f.write(json.dumps(s) + "\n")
    with open("spans.js", "w") as f:
        f.write("// Auto-generated by gen_spans.py.\n")
        f.write("window.__SPANS__ = ")
        json.dump(all_spans, f)
        f.write(";\n")

    # Summary
    trace_ids = {s["trace_id"] for s in all_spans}
    errors   = {s["trace_id"] for s in all_spans if s["status"] == "ERROR"}
    print(f"wrote {len(all_spans)} spans across {len(trace_ids)} traces")
    print(f"  error traces: {len(errors)}")
    from collections import Counter
    kinds = Counter(s["name"] for s in all_spans)
    print(f"  span-name counts: {dict(kinds)}")


# %% Run
if __name__ == "__main__":
    main()
