"""
LX-6 reference solution — Instructor only.

Reference classifier for the mystery-trace exercise in
`../../exercises/lx6_diagnose_multi_agent/`. Target: 50/50 on the
seeded dataset.

Copy `mystery_spans.ndjson` and `TRUTH.json` from the exercise
folder into this folder first (or adjust the load path). The grading
harness is identical to the student version.

Run:  python solution.py
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict


EXPECTED_TOOL = {
    "db_agent":  "tool.db_query",
    "kb_agent":  "tool.kb_search",
    "web_agent": "tool.http",
}


def load_traces(path: str = "mystery_spans.ndjson") -> dict[str, list[dict]]:
    traces: dict[str, list[dict]] = defaultdict(list)
    with open(path) as f:
        for line in f:
            s = json.loads(line)
            traces[s["trace_id"]].append(s)
    return traces


def _build_index(spans: list[dict]):
    """Return (by_id, kids_of). kids_of[id] -> list of child spans."""
    by_id = {s["span_id"]: s for s in spans}
    kids: dict[str | None, list[dict]] = defaultdict(list)
    for s in spans:
        kids[s["parent_span_id"]].append(s)
    return by_id, kids


def classify_trace(spans: list[dict]) -> str:
    """Detect failure mode from the span tree.

    Order (strongest → weakest signal):
        cascading_repair  > role_confusion > silent_tool_error > planner_loop > ok

    Rationale:
      * A cascading-repair trace is also structurally noisy — two red
        tool spans plus a repair LLM — so we grab it first.
      * role_confusion is a deterministic mismatch between
        tool.owner and the expected tool kind — clear signal,
        easy to act on.
      * silent_tool_error lives on healthy-looking subtrees; we
        catch it before planner_loop so a trace that happens to
        contain both an empty-bytes tool AND a duplicate sub-agent
        gets routed to the data-quality bucket, not the cost-waste
        one.
      * planner_loop is the cheapest-to-fix, so it comes last.
    """
    by_id, kids = _build_index(spans)
    root = next(s for s in spans if s["parent_span_id"] is None)

    # --- cascading_repair ---------------------------------------------
    error_tool_spans = [
        s for s in spans
        if s["name"].startswith("tool.") and s["status"] == "ERROR"
    ]
    has_repair_llm = any(
        s["name"] == "llm.call"
        and (s["attributes"] or {}).get("gen_ai.step") == "orchestrator.repair"
        for s in spans
    )
    if len(error_tool_spans) >= 2 or (error_tool_spans and has_repair_llm):
        return "cascading_repair"

    # --- role_confusion -----------------------------------------------
    for s in spans:
        if not s["name"].startswith("tool."):
            continue
        attrs = s["attributes"] or {}
        owner = attrs.get("tool.owner")
        if owner in EXPECTED_TOOL and s["name"] != EXPECTED_TOOL[owner]:
            return "role_confusion"

    # --- silent_tool_error --------------------------------------------
    for s in spans:
        if not s["name"].startswith("tool."):
            continue
        if s["status"] != "OK":
            continue
        rb = (s["attributes"] or {}).get("tool.result_bytes", -1)
        if rb == 0:
            return "silent_tool_error"

    # --- planner_loop -------------------------------------------------
    root_children = kids[root["span_id"]]
    subagent_names = [c["name"] for c in root_children
                      if c["name"].startswith("subagent.")]
    dup = [n for n, cnt in Counter(subagent_names).items() if cnt >= 2]
    if dup:
        return "planner_loop"

    return "ok"


def main() -> None:
    traces = load_traces()
    truth = json.load(open("TRUTH.json"))

    per_trace: dict[str, tuple[str, str]] = {}
    for tid, spans in traces.items():
        per_trace[tid] = (classify_trace(spans), truth[tid])

    correct = sum(1 for p, t in per_trace.values() if p == t)
    total   = len(per_trace)
    print(f"overall: {correct}/{total} correct\n")

    buckets: dict[str, Counter] = defaultdict(Counter)
    for pred, t in per_trace.values():
        buckets[t][pred] += 1

    modes = ["ok", "planner_loop", "cascading_repair",
             "role_confusion", "silent_tool_error"]
    print("confusion matrix (rows=truth, cols=predicted)")
    print("  " + "".join(f"{m[:14]:>16s}" for m in modes))
    for t in modes:
        row = [f"{buckets[t][p]:>16d}" for p in modes]
        print(f"{t[:14]:>16s}" + "".join(row))


if __name__ == "__main__":
    main()
