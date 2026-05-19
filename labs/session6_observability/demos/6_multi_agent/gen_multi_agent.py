# %% [markdown]
# # Demo 6 — multi-agent OTel traces with three intentional failure modes
#
# Pairs with Slides 27–28. One "ops-assistant" orchestrator routes each user
# question to one of three sub-agents (db_agent, kb_agent, web_agent) and
# synthesises the answer. Each sub-agent runs its own llm.call + tool.call
# sequence, all under the same trace_id.
#
#     orchestrator.task                          ← root
#       ├── orchestrator.plan                    ← LLM: which sub-agent?
#       ├── subagent.<name>                      ← e.g. subagent.db_agent
#       │    ├── llm.call                        ← sub-agent thinks
#       │    └── tool.<kind>                     ← SQL / KB / HTTP
#       └── orchestrator.synthesize              ← LLM: compose answer
#
# Three failure modes deliberately injected:
#
#   1. `planner_loop`   — orchestrator calls two sub-agents for the same
#                         question because the first one returned an unhelpful
#                         answer. Shows up as two subagent.* spans under one
#                         root with nearly identical queries. Latency balloons.
#   2. `cascading_repair` — sub-agent tool fails. Orchestrator catches the
#                         ERROR, switches to a different sub-agent, which also
#                         fails. Synthesize runs anyway and hedges. Multiple
#                         ERROR spans cascade up.
#   3. `role_confusion` — db_agent's llm.call decides to use the `kb.search`
#                         tool (not its own `db.query`). Span tree shows the
#                         wrong tool kind under the db_agent — the failure is
#                         visible *only* in the trace, not in any single log
#                         row.
#
# Run as a script (`python gen_multi_agent.py`) or step through cell-by-cell.

# %% Imports
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta


# %% Window, questions, models
NOW = datetime(2026, 4, 27, 18, 0, 0)
WINDOW_DAYS = 5
WINDOW_START = NOW - timedelta(days=WINDOW_DAYS)
N_TRACES = 60

# Questions split by the sub-agent that *should* handle them.
DB_QUESTIONS = [
    "How many tickets opened in the last 24 h?",
    "List the top 5 endpoints by p95 latency last week.",
    "Which tenants are over their quota this month?",
    "Show the daily active users for March 2026.",
]
KB_QUESTIONS = [
    "What's the rotation policy for API keys?",
    "Where's the runbook for a 5xx spike on checkout?",
    "Which retention policy applies to audit logs in the EU tenant?",
    "What's the escalation path for a Sev-2 incident?",
]
WEB_QUESTIONS = [
    "Is the status page reporting any Stripe incidents right now?",
    "What did AWS announce at re:Invent 2025 about S3 retention?",
    "Did GitHub release new SAML features this month?",
    "Is there an active CVE for openssl 3.0.12?",
]

MODELS = ["gpt-4o-mini", "gpt-4o"]


# %% Span helpers
def _hex(n: int) -> str:
    return hashlib.md5(f"{n}-demo6".encode()).hexdigest()[:16]


def mk(trace_id: str, parent: str | None, name: str,
       start: int, dur_ns: int, attributes: dict,
       status: str = "OK") -> dict:
    return {
        "trace_id":       trace_id,
        "span_id":        _hex(random.randint(0, 10**12)),
        "parent_span_id": parent,
        "name":           name,
        "start_ns":       start,
        "end_ns":         start + dur_ns,
        "attributes":     attributes,
        "status":         status,
    }


def make_llm_span(trace_id, parent, start, dur, *, model, step,
                  in_toks, out_toks, extras=None) -> dict:
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


# %% Sub-agent runner
def run_subagent(trace_id, parent, start_ns, agent_name: str,
                 question: str, model: str, rng: random.Random,
                 *, confused_tool: str | None = None,
                 tool_fails: bool = False) -> tuple[list[dict], int, bool]:
    """Emit spans for one sub-agent run. Returns (spans, end_ns, ok)."""
    spans: list[dict] = []
    sub_dur_target = int(rng.uniform(4e8, 8e8))   # rough envelope
    sub = mk(trace_id, parent, f"subagent.{agent_name}", start_ns,
             sub_dur_target, {
                 "agent.name":    agent_name,
                 "agent.question": question[:80],
             })
    spans.append(sub)

    # llm.call inside the sub-agent: decides what tool to call.
    cursor = start_ns + int(rng.uniform(1e6, 3e6))
    llm_dur = int(rng.lognormvariate(19.2, 0.25))
    spans.append(make_llm_span(trace_id, sub["span_id"], cursor, llm_dur,
                               model=model, step=f"{agent_name}.decide",
                               in_toks=rng.randint(200, 350),
                               out_toks=rng.randint(20, 60)))
    cursor += llm_dur + int(rng.uniform(5e5, 2e6))

    # tool call.
    tool_map = {
        "db_agent":  ("tool.db_query",    "SELECT ... FROM ..."),
        "kb_agent":  ("tool.kb_search",   f"kb.search('{question[:30]}')"),
        "web_agent": ("tool.http",        f"GET /search?q={question[:20]}"),
    }
    tool_name, tool_input = tool_map[agent_name]
    # Role-confusion: the sub-agent picks the *wrong* tool.
    if confused_tool:
        tool_name = confused_tool

    tool_dur = int(rng.lognormvariate(19.5, 0.3))
    tool_status = "ERROR" if tool_fails else "OK"
    tool_attrs = {
        "tool.name":  tool_name,
        "tool.input": tool_input[:80],
        "tool.owner": agent_name,
    }
    if tool_fails:
        tool_attrs["error.type"] = "upstream_5xx"
    spans.append(mk(trace_id, sub["span_id"], tool_name, cursor, tool_dur,
                    tool_attrs, status=tool_status))
    cursor += tool_dur + int(rng.uniform(5e5, 2e6))

    # Patch the sub-agent root's end.
    sub["end_ns"] = cursor
    if tool_fails:
        sub["status"] = "ERROR"
        sub["attributes"]["error.type"] = "tool_failed"

    return spans, cursor, not tool_fails


# %% Trace generator
def generate_trace(i: int, rng: random.Random) -> list[dict]:
    ts = WINDOW_START + timedelta(seconds=rng.random() * WINDOW_DAYS * 86400)
    day_frac = (ts - WINDOW_START).total_seconds() / 86400
    trace_id = _hex(i)
    t0 = int(ts.timestamp() * 1e9)
    model = rng.choice(MODELS)

    # Pick a question and its "correct" sub-agent.
    kind = rng.choice(["db", "kb", "web"])
    if kind == "db":
        question = rng.choice(DB_QUESTIONS); correct_agent = "db_agent"
    elif kind == "kb":
        question = rng.choice(KB_QUESTIONS); correct_agent = "kb_agent"
    else:
        question = rng.choice(WEB_QUESTIONS); correct_agent = "web_agent"

    # Decide whether to inject a failure mode.
    # Distributions shift over time — on day-4 onward we added a web-fallback
    # feature that accidentally caused a planner-loop uptick.
    r = rng.random()
    failure_mode: str | None = None
    if day_frac >= 4 and r < 0.12:
        failure_mode = "planner_loop"
    elif r < 0.18:
        failure_mode = "cascading_repair"
    elif r < 0.22:
        failure_mode = "role_confusion"

    spans: list[dict] = []

    # --- Root span ---------------------------------------------------------
    root = mk(trace_id, None, "orchestrator.task", t0, 0, {
        "agent.name":     "ops-assistant",
        "user.question":  question,
        "session.id":     f"sess_{_hex(i + 991)[:10]}",
    })
    spans.append(root)
    cursor = t0 + int(rng.uniform(1e6, 3e6))

    # --- orchestrator.plan -------------------------------------------------
    plan_dur = int(rng.lognormvariate(19.0, 0.25))
    spans.append(make_llm_span(trace_id, root["span_id"], cursor, plan_dur,
                               model=model, step="orchestrator.plan",
                               in_toks=rng.randint(220, 300),
                               out_toks=rng.randint(30, 70),
                               extras={"routing.target": correct_agent}))
    cursor += plan_dur + int(rng.uniform(5e5, 2e6))

    # --- Sub-agent(s) ------------------------------------------------------
    if failure_mode == "role_confusion":
        # db_agent calls kb.search instead of db_query.
        sub_spans, cursor, _ok = run_subagent(
            trace_id, root["span_id"], cursor, correct_agent, question,
            model, rng, confused_tool="tool.kb_search")
        spans.extend(sub_spans)

    elif failure_mode == "cascading_repair":
        # First sub-agent's tool fails; orchestrator retries via a second one.
        sub_spans, cursor, _ok = run_subagent(
            trace_id, root["span_id"], cursor, correct_agent, question,
            model, rng, tool_fails=True)
        spans.extend(sub_spans)
        cursor += int(rng.uniform(1e6, 3e6))

        # Retry span: orchestrator.repair — an LLM call that decides who
        # else to ask.
        repair_dur = int(rng.lognormvariate(19.1, 0.25))
        spans.append(make_llm_span(trace_id, root["span_id"], cursor, repair_dur,
                                   model=model, step="orchestrator.repair",
                                   in_toks=rng.randint(180, 260),
                                   out_toks=rng.randint(20, 50),
                                   extras={"error.recovered": False}))
        cursor += repair_dur + int(rng.uniform(5e5, 2e6))

        alt = rng.choice([a for a in ("db_agent", "kb_agent", "web_agent")
                          if a != correct_agent])
        sub_spans, cursor, _ok = run_subagent(
            trace_id, root["span_id"], cursor, alt, question,
            model, rng, tool_fails=True)
        spans.extend(sub_spans)

    elif failure_mode == "planner_loop":
        # First sub-agent returns a mediocre answer; orchestrator
        # (wrongly) asks a second one the same question.
        sub_spans, cursor, _ok = run_subagent(
            trace_id, root["span_id"], cursor, correct_agent, question,
            model, rng)
        spans.extend(sub_spans)
        cursor += int(rng.uniform(2e6, 5e6))

        sub_spans, cursor, _ok = run_subagent(
            trace_id, root["span_id"], cursor, correct_agent, question,
            model, rng)
        spans.extend(sub_spans)

    else:
        # Happy path.
        sub_spans, cursor, _ok = run_subagent(
            trace_id, root["span_id"], cursor, correct_agent, question,
            model, rng)
        spans.extend(sub_spans)

    cursor += int(rng.uniform(5e5, 2e6))

    # --- orchestrator.synthesize ------------------------------------------
    syn_dur = int(rng.lognormvariate(20.1, 0.3))
    any_error = any(s["status"] == "ERROR" for s in spans)
    spans.append(make_llm_span(trace_id, root["span_id"], cursor, syn_dur,
                               model=model, step="orchestrator.synthesize",
                               in_toks=(150 if any_error else rng.randint(700, 1300)),
                               out_toks=rng.randint(80, 180),
                               extras={"answer.confidence":
                                       "low" if any_error else "high"}))
    cursor += syn_dur

    # Patch root end + status.
    root["end_ns"] = cursor
    root["attributes"]["trace.total_latency_ms"] = (cursor - t0) // 1_000_000
    if failure_mode:
        root["attributes"]["failure_mode"] = failure_mode
    if any_error:
        root["status"] = "ERROR"

    return spans


# %% Driver
def main() -> None:
    rng = random.Random(19)
    all_spans: list[dict] = []
    failure_counts = {"planner_loop": 0, "cascading_repair": 0,
                      "role_confusion": 0, "ok": 0}

    for i in range(N_TRACES):
        trace = generate_trace(i, rng)
        all_spans.extend(trace)
        root = next(s for s in trace if s["parent_span_id"] is None)
        mode = root["attributes"].get("failure_mode", "ok")
        failure_counts[mode] += 1

    with open("spans.ndjson", "w") as f:
        for s in all_spans:
            f.write(json.dumps(s) + "\n")
    with open("spans.js", "w") as f:
        f.write("// Auto-generated by gen_multi_agent.py.\n")
        f.write("window.__SPANS__ = ")
        json.dump(all_spans, f)
        f.write(";\n")

    trace_ids = {s["trace_id"] for s in all_spans}
    errors   = {s["trace_id"] for s in all_spans if s["status"] == "ERROR"}
    print(f"wrote {len(all_spans)} spans across {len(trace_ids)} traces")
    print(f"  error traces: {len(errors)}")
    from collections import Counter
    kinds = Counter(s["name"] for s in all_spans)
    print(f"  span-name counts: {dict(kinds)}")
    print(f"  failure-mode distribution: {failure_counts}")


# %% Run
if __name__ == "__main__":
    main()
