"""
Generator for the LX-6 mystery dataset.

Produces a 50-trace `mystery_spans.ndjson` from an ops-assistant
orchestrator similar to Demo 6, but:

  * Strips the `failure_mode` attribute from root spans (that's what
    the student has to derive).
  * Mixes in one "new" failure mode on ~3 traces that wasn't in
    Demo 6 — **silent_tool_error**: the tool span has status=OK but
    its `tool.result_bytes=0`, and the sub-agent's llm.call still
    claims success. This tests whether the student checks status
    attributes vs just the `status` enum.

The paired `TRUTH.json` is written alongside so the student's script
can self-grade.

This file is not part of the exercise students see — it's shipped in
the exercise folder as a generator so instructors can regenerate the
dataset if they want to change the distribution. Students should
work from `mystery_spans.ndjson` directly.

Run:  python gen_mystery.py
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta


NOW = datetime(2026, 4, 27, 18, 0, 0)
WINDOW_DAYS = 5
WINDOW_START = NOW - timedelta(days=WINDOW_DAYS)
N_TRACES = 50

DB_QUESTIONS = [
    "How many tickets opened last week?",
    "Top 5 endpoints by p95 last week.",
    "Tenants over quota this month.",
    "Daily active users for March 2026.",
]
KB_QUESTIONS = [
    "What's the rotation policy for API keys?",
    "Runbook for a 5xx spike on checkout?",
    "Retention policy for EU audit logs?",
    "Escalation path for a Sev-2?",
]
WEB_QUESTIONS = [
    "Is Stripe reporting an incident?",
    "AWS re:Invent 2025 S3 announcements.",
    "GitHub SAML features this month.",
    "Active CVE for openssl 3.0.12.",
]

MODELS = ["gpt-4o-mini", "gpt-4o"]


def _hex(n: int) -> str:
    return hashlib.md5(f"{n}-lx6".encode()).hexdigest()[:16]


def mk(trace_id, parent, name, start, dur, attrs, status="OK"):
    return {
        "trace_id":       trace_id,
        "span_id":        _hex(random.randint(0, 10**12)),
        "parent_span_id": parent,
        "name":           name,
        "start_ns":       start,
        "end_ns":         start + dur,
        "attributes":     attrs,
        "status":         status,
    }


def llm_span(trace_id, parent, start, dur, *, model, step,
             in_toks, out_toks, extras=None):
    attrs = {
        "gen_ai.system":              "openai",
        "gen_ai.request.model":       model,
        "gen_ai.operation.name":      "chat.completions",
        "gen_ai.usage.input_tokens":  in_toks,
        "gen_ai.usage.output_tokens": out_toks,
        "gen_ai.step":                step,
    }
    if extras:
        attrs.update(extras)
    return mk(trace_id, parent, "llm.call", start, dur, attrs)


def sub_agent_run(trace_id, parent, start, agent, question, model, rng,
                  *, confused_tool=None, tool_fails=False,
                  silent_zero_bytes=False):
    spans = []
    sub = mk(trace_id, parent, f"subagent.{agent}", start,
             int(rng.uniform(4e8, 8e8)),
             {"agent.name": agent, "agent.question": question[:80]})
    spans.append(sub)
    cur = start + int(rng.uniform(1e6, 3e6))
    lllm_dur = int(rng.lognormvariate(19.2, 0.25))
    spans.append(llm_span(trace_id, sub["span_id"], cur, lllm_dur,
                          model=model, step=f"{agent}.decide",
                          in_toks=rng.randint(200, 350),
                          out_toks=rng.randint(20, 60)))
    cur += lllm_dur + int(rng.uniform(5e5, 2e6))

    tool_map = {
        "db_agent":  ("tool.db_query",  "SELECT ..."),
        "kb_agent":  ("tool.kb_search", f"kb.search('{question[:30]}')"),
        "web_agent": ("tool.http",      f"GET /search?q={question[:20]}"),
    }
    tool_name, tool_input = tool_map[agent]
    if confused_tool:
        tool_name = confused_tool

    tool_dur = int(rng.lognormvariate(19.5, 0.3))
    status = "ERROR" if tool_fails else "OK"
    attrs = {
        "tool.name":  tool_name,
        "tool.input": tool_input[:80],
        "tool.owner": agent,
    }
    if tool_fails:
        attrs["error.type"] = "upstream_5xx"
        attrs["tool.result_bytes"] = 0
    elif silent_zero_bytes:
        # Status OK but payload is empty — the new failure mode.
        attrs["tool.result_bytes"] = 0
    else:
        attrs["tool.result_bytes"] = rng.randint(1200, 8000)
    spans.append(mk(trace_id, sub["span_id"], tool_name, cur, tool_dur,
                    attrs, status=status))
    cur += tool_dur + int(rng.uniform(5e5, 2e6))

    sub["end_ns"] = cur
    if tool_fails:
        sub["status"] = "ERROR"
    return spans, cur, not tool_fails


def build_trace(i, rng, mode_assignments):
    ts = WINDOW_START + timedelta(seconds=rng.random() * WINDOW_DAYS * 86400)
    trace_id = _hex(i)
    t0 = int(ts.timestamp() * 1e9)
    model = rng.choice(MODELS)

    kind = rng.choice(["db", "kb", "web"])
    agents = {"db": "db_agent", "kb": "kb_agent", "web": "web_agent"}
    pool = {"db": DB_QUESTIONS, "kb": KB_QUESTIONS, "web": WEB_QUESTIONS}[kind]
    question = rng.choice(pool)
    correct_agent = agents[kind]
    mode = mode_assignments[i]

    spans = []
    # Root. Note: no failure_mode attr — that's what the student
    # has to derive.
    root = mk(trace_id, None, "orchestrator.task", t0, 0, {
        "agent.name":    "ops-assistant",
        "user.question": question,
        "session.id":    f"sess_{_hex(i + 7777)[:10]}",
    })
    spans.append(root)
    cur = t0 + int(rng.uniform(1e6, 3e6))

    plan_dur = int(rng.lognormvariate(19.0, 0.25))
    spans.append(llm_span(trace_id, root["span_id"], cur, plan_dur,
                          model=model, step="orchestrator.plan",
                          in_toks=rng.randint(220, 300),
                          out_toks=rng.randint(30, 70),
                          extras={"routing.target": correct_agent}))
    cur += plan_dur + int(rng.uniform(5e5, 2e6))

    if mode == "role_confusion":
        sub_spans, cur, _ = sub_agent_run(
            trace_id, root["span_id"], cur, correct_agent, question,
            model, rng, confused_tool="tool.kb_search")
        spans.extend(sub_spans)

    elif mode == "cascading_repair":
        sub_spans, cur, _ = sub_agent_run(
            trace_id, root["span_id"], cur, correct_agent, question,
            model, rng, tool_fails=True)
        spans.extend(sub_spans)
        cur += int(rng.uniform(1e6, 3e6))
        repair_dur = int(rng.lognormvariate(19.1, 0.25))
        spans.append(llm_span(trace_id, root["span_id"], cur, repair_dur,
                              model=model, step="orchestrator.repair",
                              in_toks=rng.randint(180, 260),
                              out_toks=rng.randint(20, 50)))
        cur += repair_dur + int(rng.uniform(5e5, 2e6))
        alt = rng.choice([a for a in ("db_agent", "kb_agent", "web_agent")
                          if a != correct_agent])
        sub_spans, cur, _ = sub_agent_run(
            trace_id, root["span_id"], cur, alt, question,
            model, rng, tool_fails=True)
        spans.extend(sub_spans)

    elif mode == "planner_loop":
        sub_spans, cur, _ = sub_agent_run(
            trace_id, root["span_id"], cur, correct_agent, question,
            model, rng)
        spans.extend(sub_spans)
        cur += int(rng.uniform(2e6, 5e6))
        sub_spans, cur, _ = sub_agent_run(
            trace_id, root["span_id"], cur, correct_agent, question,
            model, rng)
        spans.extend(sub_spans)

    elif mode == "silent_tool_error":
        sub_spans, cur, _ = sub_agent_run(
            trace_id, root["span_id"], cur, correct_agent, question,
            model, rng, silent_zero_bytes=True)
        spans.extend(sub_spans)

    else:
        sub_spans, cur, _ = sub_agent_run(
            trace_id, root["span_id"], cur, correct_agent, question,
            model, rng)
        spans.extend(sub_spans)

    cur += int(rng.uniform(5e5, 2e6))
    syn_dur = int(rng.lognormvariate(20.1, 0.3))
    any_err = any(s["status"] == "ERROR" for s in spans)
    spans.append(llm_span(trace_id, root["span_id"], cur, syn_dur,
                          model=model, step="orchestrator.synthesize",
                          in_toks=(150 if any_err else rng.randint(700, 1300)),
                          out_toks=rng.randint(80, 180)))
    cur += syn_dur

    root["end_ns"] = cur
    root["attributes"]["trace.total_latency_ms"] = (cur - t0) // 1_000_000
    if any_err:
        root["status"] = "ERROR"
    return spans


def main():
    rng = random.Random(101)
    # Assign modes deterministically.
    modes = (["ok"] * 32 +
             ["planner_loop"] * 6 +
             ["cascading_repair"] * 6 +
             ["role_confusion"] * 3 +
             ["silent_tool_error"] * 3)
    rng.shuffle(modes)
    assert len(modes) == N_TRACES

    all_spans = []
    truth: dict[str, str] = {}
    for i in range(N_TRACES):
        trace = build_trace(i, rng, modes)
        root = next(s for s in trace if s["parent_span_id"] is None)
        truth[root["trace_id"]] = modes[i]
        all_spans.extend(trace)

    with open("mystery_spans.ndjson", "w") as f:
        for s in all_spans:
            f.write(json.dumps(s) + "\n")
    with open("mystery_spans.js", "w") as f:
        f.write("// Auto-generated by gen_mystery.py.\n")
        f.write("window.__SPANS__ = ")
        json.dump(all_spans, f)
        f.write(";\n")
    with open("TRUTH.json", "w") as f:
        json.dump(truth, f, indent=2, sort_keys=True)

    from collections import Counter
    dist = Counter(modes)
    print(f"wrote {len(all_spans)} spans across {N_TRACES} traces")
    print(f"  truth distribution: {dict(dist)}")


if __name__ == "__main__":
    main()
