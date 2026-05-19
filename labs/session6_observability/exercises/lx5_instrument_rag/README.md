# LX-5 · Instrument a RAG function with OTel spans

Pairs with [Demo 5](../../demos/5_otel_traces/README.md). ~40 minutes.

## Background

Demo 5 ships a fully-instrumented agent and a working waterfall
viewer. This exercise goes the other direction: you're handed a plain
Python RAG function and have to *add the instrumentation yourself*.
The goal is not to memorise the OTel SDK — it's to internalise the
shape of a span and what "parent-child" means in code, so you can
review an instrumented codebase and spot the mistakes.

You don't need to install anything. `starter.py` includes a
~20-line `Tracer` class scaffolding. You fill in three methods and
wrap three function calls.

## Task

1. **Finish the `Tracer` class.** Implement `start_span(name, attrs)`
   and `end_span(span, status)`. `start_span` should generate a 16-hex
   span_id, take the parent from the stack (None if empty), record
   `start_ns`, push the new span_id onto the stack, and return the
   span dict. `end_span` should record `end_ns`, set `status`, pop the
   stack, and append the span to `self.spans`. The context manager
   `span(...)` is already wired up — it calls these two.
2. **Wrap `run_query`.** Put the whole body in a `research.task`
   root span. Wrap the plan call in a `llm.call` span with
   `gen_ai.step="plan"`. Wrap retrieval in a `retrieval.search` span.
   Wrap the answer call in a `llm.call` span with
   `gen_ai.step="answer"`.
3. **Set GenAI attributes.** On each `llm.call` span, set at minimum:
   `gen_ai.system = "openai"`, `gen_ai.request.model = model`,
   `gen_ai.operation.name = "chat.completions"`,
   `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`.
4. **Set retrieval attributes.** On the `retrieval.search` span, set
   `retrieval.query` (truncated is fine), `retrieval.top_k`,
   `retrieval.hit_count`.
5. **Run and view.** `python starter.py` → open `trace_viewer.html`.
   You should see 20 traces listed; clicking any one should show a
   clean 4-bar waterfall (root + plan + retrieval + answer).

## Rules

1. **Don't change the fake RAG stages** (`fake_plan`,
   `fake_retrieve`, `fake_answer`). They simulate real LLM calls and
   return the numbers your spans need to record.
2. **Use the context manager** (`with tracer.span(...) as s:`) rather
   than manually calling `start_span` / `end_span`. The point is
   exception-safe end times. If retrieval throws, the span still
   closes with `ERROR`.
3. **Set attributes inside the block**, once you have the return
   values. The scaffolding accepts an initial `attributes` arg but
   you'll mostly mutate `s["attributes"]` with the token counts after
   the stage returns.
4. **One tracer per query, not one per process.** Each call to
   `run_query` gets its own `Tracer` with a fresh `trace_id`. The
   spans from different queries should never share a trace_id.

## How to run

```bash
python starter.py           # writes spans.ndjson + spans.js
open trace_viewer.html      # or double-click it
```

The viewer is identical to the one from Demo 5 — same three-pane
layout, same URL deep-linking (`?trace_id=…`).

## What to submit

- Your completed `starter.py` (or a separate `solution.py`). Whichever
  file runs `python <file>.py` to produce `spans.ndjson`.

## Success criteria

1. `python starter.py` runs cleanly and prints:
   `wrote 80 spans across 20 traces` (4 spans per trace).
2. The span-name counter prints:
   `{'research.task': 20, 'llm.call': 40, 'retrieval.search': 20}`.
3. Opening `trace_viewer.html` lists 20 traces. Clicking any row
   shows the root-plan-retrieval-answer waterfall with four indented
   bars.
4. Clicking the `llm.call (plan)` span in the attribute panel shows
   `gen_ai.system`, `gen_ai.request.model`, `gen_ai.operation.name`,
   and both token counts.
5. Clicking the `retrieval.search` span shows `retrieval.query`,
   `retrieval.top_k`, `retrieval.hit_count`.

## Hints

- **`span_id` generation.** The demo uses `md5(str(rand)).hexdigest()[:16]`.
  Any 16-hex string unique-within-the-trace is fine. Real OTel uses
  64-bit random IDs; we keep it string-ish for readability.
- **Timing.** `time.time_ns()` gives you a nanosecond timestamp that
  matches the OTel data model. You don't need wall-clock — monotonic
  deltas from a fake `NOW` also work, but real clock time is simplest.
- **The stack trick.** The context manager already handles push/pop;
  you just have to push in `start_span` and pop in `end_span`. A common
  bug is popping before appending to `self.spans` with the wrong
  parent — check that retrieval's parent_span_id is the root's, not
  the plan call's.
- **Attribute mutation.** After `fake_plan` returns, do
  `s["attributes"]["gen_ai.usage.input_tokens"] = plan_in`. The dict
  is the same object you `yield`ed, so changes persist.
- **Deep-link to a failing trace.** Once everything works, artificially
  break one (`if i == 0: raise RuntimeError` inside a stage) and
  reload the viewer — the exception propagates, but the span you
  wrapped should still end with `status="ERROR"`. Comment the line
  back out before submitting.

## Common pitfalls

- **Forgetting to pop the stack on exception.** If `end_span` only
  pops on the happy path, one error fouls up every subsequent trace.
  Put the pop before the append and outside any `if status == 'OK'`
  check.
- **Using `time.time()` instead of `time.time_ns()`.** Float seconds
  lose sub-millisecond precision; the viewer's waterfall becomes
  useless for short spans. Convert at the boundary if you must:
  `int(time.time() * 1e9)`.
- **Treating `attributes=None` as mutable.** Python gotcha — default
  `attributes={}` is the *same dict across calls*. Use
  `attributes or {}` inside the function, then copy.
- **Running the script but not refreshing the viewer.** The viewer
  caches `spans.js`. Hard-refresh (Cmd-Shift-R / Ctrl-F5) if your
  waterfall still looks wrong after editing the tracer.

## What this drills

- **The span as a data contract.** Eight keys, always the same names.
  You're free to build your own tracer, but the consumer doesn't care
  as long as the shape matches. Same reason we shipped Demo 5's
  viewer: a tracer and a UI meeting at a stable schema.
- **Context propagation as a stack.** The "parent_span_id = top of
  stack" trick is how real libraries (OTel, Sentry, Datadog)
  implement implicit parent selection. Explicit parents work too but
  clutter every call site.
- **GenAI semantic conventions as a public interface.** The
  `gen_ai.*` attribute names are standardised exactly so that
  vendor-neutral tools (and your future self) can query across
  providers. Custom names work, but silo your data. Stage-B
  discipline pays off by the 6-month mark, not the first day.

## What's out of scope

- **Real HTTP propagation.** Real OTel injects a `traceparent`
  header into every outgoing request so the downstream service
  attaches its spans to the right trace. Single-process here.
- **Sampling.** Export-every-span works at 20 traces and fails at
  20M. Head-based sampling (decide at trace start) is how production
  systems keep cost bounded. Mentioned on Slide 25.
- **Backpressure and batching.** The OTel SDK batches spans before
  sending to the collector; we write them out synchronously. Not a
  correctness issue for a lab, always a correctness issue at scale.
