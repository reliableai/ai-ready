# Demo 5 · OTel traces for an agent

Pairs with Slides 24–26 of L10 — the jump from **Stage A** (flat
per-request log rows) to **Stage B** (distributed traces with
parent/child spans). This is the first demo where a single user
request produces *multiple* spans and where the interesting questions
are about *relationships* — "which step blew the budget?", "did the
retrieval call time out before or after the plan step ran?"

## What's here

```
demos/5_otel_traces/
  gen_spans.py          ← generates ~165 spans across 40 traces
  spans.ndjson          ← one span per line (for grep / jq)
  spans.js              ← window.__SPANS__ = [...]   (for the viewer)
  trace_viewer.html     ← 3-pane viewer: trace list · waterfall · attrs
  README.md
```

## The agent being traced

A small RAG-style research assistant:

```
research.task                      ← root span
  ├── llm.call (step=plan)         ← decide which tools to call
  ├── retrieval.search             ← vector-db lookup
  │    └── tool.http (optional)    ← added on day-4 as a web fallback
  └── llm.call (step=answer)       ← compose the final answer
```

Each span carries the OTel data model — `trace_id`, `span_id`,
`parent_span_id`, `name`, `start_ns`, `end_ns`, `attributes`,
`status`. On `llm.call` spans we set the GenAI semantic-convention
attributes (`gen_ai.system`, `gen_ai.request.model`,
`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
`gen_ai.operation.name`, plus a local `gen_ai.step` marker so plan
vs. answer is visible in the waterfall). Retrieval spans carry the
query, hit count, and index name. HTTP spans carry method/url/status.

## Two intentional incidents

The generator is deterministic (`seed=7`, frozen
`NOW = 2026-04-27T18:00`). In the 40-trace window you get:

- **~2 retrieval timeouts.** `retrieval.search` runs for 5 s, status
  `ERROR`, `error.type = "timeout"`, hit count 0. The `llm.call
  (step=answer)` span still runs — but with `input_tokens=120` (no
  context) and a completion excerpt that reads *"I don't have enough
  information to answer that."* This is the fail-open-on-retrieval
  pattern from Slide 24.
- **Root status propagation.** The research.task root span inherits
  `status=ERROR` and `error.type=retrieval_timeout`. The trace-list
  UI shows a red badge; the waterfall shows the offending span in red.

## How to run

```bash
python gen_spans.py
open trace_viewer.html     # or double-click it
```

On first load you see the trace list. Click a row → waterfall on the
right of the list. Click a span → full attributes panel on the far
right. The URL updates to `?trace_id=...` so you can share a link
straight to an investigation.

## Teaching beats (Slide 26)

1. **Why three spans instead of one row.** Open a healthy trace.
   Point out how the waterfall tells you *where the latency lives*
   (usually the answer llm.call, sometimes the retrieval). One flat
   log row with `total_latency_ms=3200` can't tell you that.
2. **Parent-child is a graph, not a string.** The `tool.http` span
   (when present) is a child of `retrieval.search`, not of the root.
   Click it; note how its span_id's `parent_span_id` matches
   `retrieval.search.span_id`. This is the entire point of the span
   data model.
3. **An error trace.** Pick one with a red badge (trace 0 is the
   first). Retrieval is 5 s, red; the answer llm.call still ran and
   the completion excerpt is a hedge. This is a *correct* behaviour
   for the agent and a *wrong* answer for the user — exactly the kind
   of thing Stage A can't see.
4. **GenAI semantic conventions.** On the plan span, open the attrs
   panel. `gen_ai.system=openai`,
   `gen_ai.operation.name=chat.completions`, input/output tokens.
   This is the OTel-standardised shape — same keys whether you're on
   Datadog, Honeycomb, or Langfuse. Vendor-neutral contract.
5. **Local extensions.** Note `gen_ai.step` ("plan" / "answer") and
   `trace.total_latency_ms` — not in the OTel spec, but legal as
   attributes. The rule is: stable names from the spec when one
   exists, `your_org.*` prefix for extensions. We cheat slightly for
   pedagogy.

## Reading the ndjson directly

Span rows are flat, one per line. `jq` works:

```bash
# All spans for the one error trace with the longest retrieval.
jq 'select(.name=="retrieval.search" and .status=="ERROR")' spans.ndjson

# Total tokens (plan + answer) per trace.
jq -s '
  group_by(.trace_id) |
  map({trace: .[0].trace_id,
       total: ([.[] | select(.name=="llm.call")
                    | .attributes["gen_ai.usage.input_tokens"]
                      + .attributes["gen_ai.usage.output_tokens"]] | add)})
' spans.ndjson | head -20
```

This is the same file shape every OTel collector emits — so anything
you build here transfers to production data.

## What's deliberately simple

- **No sampler.** We export every span. Real agents run a head-based
  sampler to keep cost bounded; mentioned on Slide 25, not coded here.
- **No span links.** A real multi-turn assistant would link a new
  `research.task` to the previous turn's trace. One of the follow-on
  exercises (LX-5) covers this.
- **Fabricated durations.** `rng.lognormvariate` is fine for a demo
  and wrong for production. Never ship a model that prescribes drug
  dosages based on a log-normal.
- **One service.** Real distributed traces cross services; spans get
  propagated via the `traceparent` HTTP header. That's the whole
  point of distributed tracing — out of scope for this demo.
