# LX-6 · Classifier notes (reference)

Companion to `solution.py`. Why this classifier scores 50/50, what
trade-offs are hiding in the `if`-order, and where it would break
on real production data.

## The rule order

```
  cascading_repair  > role_confusion > silent_tool_error > planner_loop > ok
```

The order is the most interesting design choice. Variants that
re-order these will still pass the exercise (the truth labels are
clean enough) but behave differently on ambiguous real traces.

- **`cascading_repair` first** because it means multiple things
  broke. Any trace with two ERROR tool spans is firmly in
  this bucket, even if the first tool also happened to return
  zero bytes (silent_tool_error) or fired under the wrong sub-agent
  (role_confusion). The stronger signal wins.
- **`role_confusion` second** because the confusion is visible the
  moment the tool span lands — no need to look at the synthesize
  step. It's also the bucket an on-call most wants to know about
  first: it indicates a *prompt regression* (the sub-agent's
  system message has decayed), which is usually fixable in minutes.
- **`silent_tool_error` third** because it's the subtlest. No
  ERROR, no structural anomaly — just a scalar attribute
  (`tool.result_bytes=0`) that the sub-agent's LLM didn't notice.
  This is the "my dashboard is green but my users are screaming"
  failure mode. Worth flagging, worth not over-flagging.
- **`planner_loop` last** because it's the cheapest category to
  live with. Nothing is *wrong*; we just paid for two retrievals
  when one would have done. A classifier that over-flags this
  generates alert noise; under-flagging costs money but not
  correctness.

## The three "could be mis-classified" traces

The seeded dataset doesn't have any by construction, but in
production you'd see:

1. **Planner loop that also confused a role.** Orchestrator calls
   db_agent twice; on the second call db_agent picks kb.search.
   We classify this as `role_confusion`. That's the right action —
   fix the sub-agent's prompt, and the loop (which was downstream of
   a bad decision) resolves too.
2. **Cascading repair where the second tool silently returns nothing.**
   Same rule — cascading wins. The silent tool is the second failure
   in a chain, not the headline.
3. **Silent tool error under a planner loop.** One of the two
   duplicated sub-agents returned 0 bytes. We classify as
   `silent_tool_error` (because we order it above planner_loop).
   Debatable: if the product already tolerates planner loops, the
   silent error is the actionable event; if not, you might prefer
   the loop. The order encodes the team's triage priorities.

## What a misclassification would look like

If you accidentally checked `silent_tool_error` before
`cascading_repair`, you'd route the 6 cascading traces in this
dataset to the data-quality team when they should be going to the
orchestrator owner. The confusion matrix would show 6 on the
`cascading_repair` row but in the `silent_tool_error` column —
perfect per-trace accuracy, perfectly wrong on-call decisions.
This is why "order the predicates from strongest to weakest" is
the most important rule of this exercise, not the predicates
themselves.

## Why `tool.result_bytes == 0` and not `== None`

Stock OTel emitter semantics: attributes default to "absent" rather
than "zero". Using `== 0` avoids firing on tool spans that simply
didn't record a byte count. In the dataset every tool span carries
the attribute, so the distinction doesn't matter; in real life you
want the strict check.

## Student variants seen

Four classifier patterns that students commonly ship:

- **Pure `root.status` check.** "Any trace with root.status=ERROR
  is cascading_repair; all else is ok." Gets 32 + 6 = 38/50 right.
  Misses role_confusion and silent_tool_error entirely. Misses
  planner_loop (root.status is OK when both sub-agents succeeded).
- **Counter-based.** Groups children by name, uses
  `Counter.most_common(1)[0][1] > 1` to spot planner_loop first.
  Often flips the order and gets ~45/50. Close enough to pass; fine.
- **Question-keyword cheat.** Scans `user.question` for words like
  "incident" and routes. Always fails the "each mode must fire"
  invariant because the question pool is tiny and doesn't cluster
  by mode.
- **LLM judge.** Dumps the trace JSON into a prompt and asks
  GPT-4o-mini to classify. Works surprisingly well on this dataset
  but blows past the "stdlib only" rule. Good discussion topic, not
  a valid submission.

## Running this against the live Demo 6 dataset

The solution will also correctly classify the Demo 6 traces (with
no `silent_tool_error` category in that dataset, it'll return the
three original modes only). Handy sanity check:

```bash
cd ../../demos/6_multi_agent
python gen_multi_agent.py
python -c "
import json, importlib.util
spec = importlib.util.spec_from_file_location(
    'sol', '../../solutions/lx6_diagnose_multi_agent/solution.py')
sol = importlib.util.module_from_spec(spec); spec.loader.exec_module(sol)
from collections import Counter
traces = sol.load_traces('spans.ndjson')
print(Counter(sol.classify_trace(v) for v in traces.values()))
"
```

## What the reference doesn't do

- **Doesn't alert.** Real deployment routes the label to PagerDuty
  with de-dup keys + escalation. Out of scope.
- **Doesn't rank by severity.** A cascading_repair on a paying
  tenant's question matters more than on an anonymous one. Would
  need `attrs["tenant.tier"]`.
- **Doesn't handle unknown modes.** A new failure mode shows up →
  classifier returns "ok", dashboard is green, on-call is asleep,
  users are screaming. In prod you'd track a "residual errors"
  bucket (traces with `root.status=ERROR` that *no* rule matched)
  and alert on *that* count trending up.
