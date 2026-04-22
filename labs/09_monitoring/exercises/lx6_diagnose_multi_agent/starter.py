"""
LX-6 · Diagnose a multi-agent trace dataset.

You've been handed `mystery_spans.ndjson` — 50 traces from an
ops-assistant orchestrator. Your pager went off because users are
complaining that answers are slow *and* sometimes wrong. The team
thinks there are several different things going on, not one. Your
job is to classify each trace by failure mode.

Four modes are in the data — three covered in Demo 6 plus one new
one:

  * planner_loop        — orchestrator called the same sub-agent
                          twice for one question. Cost waste,
                          visible as two `subagent.<same>` under one
                          root.
  * cascading_repair    — a tool failed, the orchestrator tried
                          another sub-agent, that failed too.
                          Multiple ERROR spans.
  * role_confusion      — a sub-agent called a tool that doesn't
                          belong to it (e.g. db_agent used kb.search).
                          status=OK but tool.name doesn't match owner.
  * silent_tool_error   — (new) tool span has status=OK but
                          `tool.result_bytes=0`. Looks healthy, isn't.

The rest (~32) are healthy `ok` traces.

Your job:

  1. Implement `classify_trace(spans)` to return exactly one of
     `"ok" | "planner_loop" | "cascading_repair" | "role_confusion"
      | "silent_tool_error"`.
  2. Run `python starter.py`. It'll compare your classification with
     `TRUTH.json` and print a confusion matrix.

Rules:

  * Don't read `TRUTH.json` from inside `classify_trace`. That's
    cheating. The grading block at the bottom of this file reads it.
  * You can use attributes liberally — `status`, `tool.name`,
    `tool.owner`, `tool.result_bytes`, `agent.name`. The span tree
    (parent/child) is fair game too.
  * Your classifier should make exactly one decision per trace.
    When several modes could apply, pick the stronger signal (e.g.
    cascading_repair > silent_tool_error because the former is
    strictly more broken).

Success criteria:

  * ≥ 45 / 50 traces classified correctly.
  * No mode gets 0 out of N — i.e. your classifier must fire at
    least once for each of the four failure modes.

Run:  python starter.py
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict


def load_traces(path: str = "mystery_spans.ndjson") -> dict[str, list[dict]]:
    traces: dict[str, list[dict]] = defaultdict(list)
    with open(path) as f:
        for line in f:
            s = json.loads(line)
            traces[s["trace_id"]].append(s)
    return traces


# ---------------------------------------------------------------------------
# The function you implement.
# ---------------------------------------------------------------------------

def classify_trace(spans: list[dict]) -> str:
    """Return one of:
       'ok' | 'planner_loop' | 'cascading_repair' |
       'role_confusion' | 'silent_tool_error'
    """
    # TODO — implement. Some hints:
    #
    # - cascading_repair: look for >= 2 spans with status=="ERROR"
    #   (or equivalently: a span whose name starts with `tool.` AND
    #   status=="ERROR", together with a following `orchestrator.repair`
    #   or another ERROR tool span).
    # - planner_loop: group children of the root by name. If any
    #   `subagent.<X>` appears more than once under the same root,
    #   it's a planner loop.
    # - role_confusion: for each sub-agent, check whether the tool
    #   it emitted matches its "expected" kind. A rough mapping:
    #     db_agent  → tool.db_query
    #     kb_agent  → tool.kb_search
    #     web_agent → tool.http
    # - silent_tool_error: any `tool.*` span with status=="OK" but
    #   `tool.result_bytes==0` (or missing and numeric-zero-ish).
    #
    # Order matters. A trace with a red tool span AND a bogus tool
    # name is a cascading_repair, not a role_confusion. Pick the
    # biggest failure you see and return it.
    raise NotImplementedError("implement classify_trace()")


# ---------------------------------------------------------------------------
# Grading — don't edit.
# ---------------------------------------------------------------------------

def main() -> None:
    traces = load_traces()
    truth = json.load(open("TRUTH.json"))

    per_trace: dict[str, tuple[str, str]] = {}
    for tid, spans in traces.items():
        try:
            pred = classify_trace(spans)
        except NotImplementedError:
            print("classify_trace() isn't implemented yet — get to it.")
            return
        per_trace[tid] = (pred, truth[tid])

    correct = sum(1 for p, t in per_trace.values() if p == t)
    total   = len(per_trace)
    print(f"overall: {correct}/{total} correct\n")

    # Per-mode accuracy.
    buckets: dict[str, Counter] = defaultdict(Counter)
    for pred, t in per_trace.values():
        buckets[t][pred] += 1

    modes = ["ok", "planner_loop", "cascading_repair",
             "role_confusion", "silent_tool_error"]
    print("confusion matrix  (rows=truth, cols=predicted)")
    print("  " + "".join(f"{m[:14]:>16s}" for m in modes))
    for t in modes:
        row = [f"{buckets[t][p]:>16d}" for p in modes]
        print(f"{t[:14]:>16s}" + "".join(row))
    print()

    # Per-mode detection fires-at-least-once check.
    fired = Counter(p for p, _ in per_trace.values())
    missing = [m for m in modes if m != "ok" and fired[m] == 0]
    if missing:
        print(f"  WARNING: classifier never fired for: {missing}")

    # Summary pass/fail.
    if correct >= 45 and not missing:
        print("PASS — file a PR with your patched starter.py.")
    else:
        print("not yet — keep iterating on classify_trace().")


if __name__ == "__main__":
    main()
