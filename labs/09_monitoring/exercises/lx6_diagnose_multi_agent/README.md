# LX-6 · Diagnose a multi-agent trace dataset

Pairs with [Demo 6](../../demos/6_multi_agent/README.md). ~45 minutes.

## Background

You're the on-call engineer for the **ops-assistant**. Users are
complaining that the assistant is *slow* on some questions and
*wrong* on others. Your observability stack captured traces for all
of it — 50 traces' worth, sitting in `mystery_spans.ndjson`. A
(less experienced) teammate has already confirmed the shape of each
trace: root `orchestrator.task`, a planner LLM call, one or more
sub-agent sub-trees, a synthesize LLM call. What they couldn't do
is *characterise* the failures.

Three failure modes are familiar from Demo 6 — `planner_loop`,
`cascading_repair`, `role_confusion`. A fourth is new and nasty:

> **`silent_tool_error`** — the tool span has `status="OK"` but
> `tool.result_bytes=0`. The sub-agent's LLM never realises it got
> an empty page, and the synthesize step writes an answer based on
> nothing. Every existing dashboard shows these as healthy traces.

The product team wants a per-category count so they can prioritise.
Your job is to write the classifier.

## Task

1. Implement `classify_trace(spans: list[dict]) -> str` in
   `starter.py`. It must return exactly one of:
   `"ok" | "planner_loop" | "cascading_repair" | "role_confusion"
   | "silent_tool_error"`.
2. Run `python starter.py`. The harness reads `TRUTH.json` and
   prints a 5x5 confusion matrix plus an overall pass/fail.
3. Pass criteria: ≥ 45 / 50 overall AND each non-ok mode fires at
   least once (so a "return 'ok' always" classifier can't pass).
4. (Optional) Open `trace_viewer.html` to eyeball a few traces your
   classifier misclassified, and decide whether to tighten your
   predicates.

## Rules

1. **Don't read `TRUTH.json` inside `classify_trace`.** That's the
   point of the exercise — your classifier has to reason from the
   span tree alone.
2. **Return exactly one label.** Some traces could plausibly match
   two rules (e.g. a cascading_repair also has zero-byte error
   payloads). Pick the strongest / most-actionable label. The grading
   rubric treats `cascading_repair` as stronger than
   `silent_tool_error`.
3. **No external libraries needed.** Stdlib only — `json`,
   `collections`. If you reach for numpy, you're probably overfitting.

## How to run

```bash
python starter.py       # reads mystery_spans.ndjson + TRUTH.json
```

Output looks roughly like:

```
overall: 47/50 correct

confusion matrix  (rows=truth, cols=predicted)
                              ok  planner_loop cascading_rep role_confusion silent_tool_er
              ok              31             0             0              0              1
    planner_loop               0             6             0              0              0
 cascading_repair               0             0             6              0              0
  role_confusion               1             0             0              2              0
 silent_tool_er               0             0             0              0              3

PASS — file a PR with your patched starter.py.
```

## Trace viewer

A copy of the Demo 6 viewer is included — open `trace_viewer.html`
to browse the 50 mystery traces. Since we stripped the `failure_mode`
attribute, the left panel won't show mode badges. That's
intentional; your classifier is *doing* the labelling.

## What to submit

- Your patched `starter.py` (or a `solution.py` variant).

## Success criteria

1. `python starter.py` prints `PASS` (≥ 45/50 correct, all four
   non-ok modes fire at least once).
2. Your misclassifications, if any, should be in the direction of
   over-reporting (false positives on failure modes) rather than
   under-reporting — we'd rather triage a false alarm than miss a
   real problem. One short comment at the top of your classifier
   naming the trade-off is plenty.

## Hints

- **Ordering matters.** The first time you return, you've committed.
  If a trace has two ERROR tool spans *and* a zero-byte tool span, you
  want to call it `cascading_repair` before `silent_tool_error`. Order
  your `if` statements from strongest to weakest signal.
- **Group children by name.** `planner_loop` is detected by
  "same `subagent.<name>` appears ≥ 2 times as a direct child of the
  root". A quick `Counter` does it.
- **Expected tool map.** For `role_confusion`, a 3-entry dict is all
  you need. The `tool.owner` attribute names the sub-agent; the
  `tool.name` tells you which tool ran. If they disagree, it's
  confusion.
- **Zero bytes.** `silent_tool_error` can be detected by walking every
  `tool.*` span and checking `status == "OK" and
  attributes.get("tool.result_bytes") == 0`. Be sure you're looking
  only at tool spans, not llm.call or sub-agent spans.
- **Cascading vs single ERROR.** A single ERROR span (rare in this
  dataset) isn't by itself `cascading_repair`. The hallmark of
  cascading is *two or more ERROR spans* plus an
  `orchestrator.repair` LLM span between them. Either signal alone
  would work for this dataset.

## Common pitfalls

- **Counting spans instead of looking at parent-child.** "If N>4
  spans, it's a planner loop" works on day one and breaks the moment
  someone adds a new kind of sub-agent to the product. Reason from
  the *tree structure*, not from flat counts.
- **Trusting `root.status`.** The orchestrator root propagates ERROR
  from any child, so `root.status == "ERROR"` doesn't tell you
  *which* child failed. You need to descend into the tree.
- **Assuming `tool.result_bytes` exists on every tool span.** We
  emit it on every span in this dataset, but in real life it might
  be absent. Use `attrs.get("tool.result_bytes", -1) == 0` so a
  missing attribute doesn't accidentally fire `silent_tool_error`.
- **Pattern-matching on questions instead of structure.** Don't
  classify by keyword in `user.question` — the exercise is explicitly
  about the *span graph*. A classifier that peeks at the question is
  fragile and doesn't transfer.

## What this drills

- **Trace as a diagnostic data structure.** Every failure mode in
  this exercise maps to a structural rule over the span tree. Learn
  those rules once and you can spot them on any agent framework.
- **Adding a new failure mode without changing the instrumentation.**
  `silent_tool_error` exists purely because the sub-agents don't
  check their own tool results. Detecting it required no new
  attribute, just a new predicate over the existing ones. That's the
  power of a well-designed span schema — new monitoring categories
  are read-side work only.
- **Taxonomy design.** "Pick the strongest label" is a product
  decision, not a technical one. You're committing to a routing
  rule: cascading-repair alerts page the orchestrator owner,
  role-confusion alerts page the sub-agent's team, silent-tool-error
  alerts page the data team. If two rules fire you don't want three
  pages.

## What's out of scope

- **An LLM-as-classifier approach.** You could feed each trace to an
  LLM and ask "what failure mode?". It would work. We're holding you
  to a structural classifier so you learn the rules.
- **Alerting / throttling / deduplication.** A real system would
  group by session_id, de-dupe within a 5-minute window, and only
  page on the *first* occurrence. This exercise is per-trace.
- **Other failure modes.** In the wild you'd see infinite-loops
  (the agent calls itself 20 times), token-overflow (synthesize
  runs with 16k+ input tokens because the sub-agents returned too
  much), and unauthorised-tool-use (a sub-agent calls a tool it
  shouldn't have access to). All tractable with the same pattern.
