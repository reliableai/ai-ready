# L10 · Monitoring, Observability and Reporting — Slide Notes

A slide-by-slide draft (one concept per slide). Iterate here before rebuilding `monitoring_slides.pptx`.

Target: ~43 slides across 5 sections + opener + closer (including 7 demo interludes). Palette: Ocean Gradient (carry over from v1 deck).

Each slide entry has: **title**, **content bullets**, optional **visual / code**, optional **speaker-note one-liner**.

Interlude slides mark where the lecture pauses and the class moves to a demo (5–15 min each). Short in-class drills (IC-1 … IC-7) stay inline as "→ pause for IC-N" notes on their parent slide — they run 2–3 min and don't need their own slide.

---

## Opener (3 slides)

### Slide 1 — Title

- **L10 · Monitoring, Observability and Reporting**
- Week 5 · AI Design 2026
- Subtitle: *Power is Nothing Without Control*

### Slide 2 — Why we monitor (and why it matters more than ever)

- Today's question: *How do we know an AI system is still working, once it's live?*
- **Three reasons we monitor** — all three amplified for AI systems:
  - **Find and fix bugs**. 
  - **Understand** — we don't fully understand the system's behavior (true for any big system; doubly true for models).
  - **Control** — we want to set guardrails against specific failure modes.
  - **Improve** — observe → learn → improve. Monitoring is the data source for next week's fix.
- Both **humans and AI** participate in monitoring AI: operators read dashboards *and* agents check other agents' outputs. We'll see both in the lab.

### Slide 3 — Roadmap: the summary matrix (empty shell)

- **Visual:** 5×3 table with headers only. System rows blank.
- Columns: *What we monitor · How · Why*
- Rows: Traditional SW/SaaS · Classical ML · Single LLM call · LLM + context/tool/memory · Systems of agents

Notes: "We will fill this in row by row, and this is what you take with you."

---

## Section 01 · Logging and  monitoring

### Assertions: Avoid Silent Failures Like the Plague

`**assert`** — an *invariant*. The violation means the program has an internal bug. Fires now, halts execution. Don't use it for user-input validation — that's what exceptions are for.

But, better crashing than proceeding with a "wrong", unexpected state

Use assertions as often as you want: they act as great documentation, too. 

>>> add text here. stress importance of assertiont to fight the biggest problem in dev: silent failures
>>> also add an example of asserion in python. show it

### Exceptions
`**raise` / `try` / `except`** — *expected-but-exceptional* flow: bad input, network error, missing file. Use when there's a recovery path or a well-defined way to signal failure up the stack.

>>> Exception handling tends to supporess failures: use them with caution


### Slide 4 — Logging

- *"this happened, here, with these values, at this time."*
- Two complementary reasons, both predating dashboards:
  - **To find and diagnose unexpected behaviors.** you log the state to try to identify when and why a bug hits.
  - **To have a trail of what happened.** Sometimes we log just to have a record, regardless of whether anything went wrong. Logs give us peace of mind, and let us reconstruct behaviours and facts later (who did what, when, with what data).
- Uses that grow from those two: audit trails, session replay, billing, compliance, product analytics.



### Slide 5 — Logging primitives

Three complementary controls in the standard library — different answers to "something unexpected was detected, now what?"


  - `**logging`** — a *side channel* that records "something happened." Doesn't change control flow. Verbosity controlled by level.
- **Log levels** — a verbosity knob *and* an alerting hook:
  - `DEBUG` — developer detail, usually silenced in prod
  - `INFO` — normal events ("request served")
  - `WARNING` — unusual but handled
  - `ERROR` — a failure we recovered from or escalated
  - `CRITICAL` — demands immediate attention
- **Code:**
  ```python
  import logging
  log = logging.getLogger(__name__)

  def divide(a, b):
      assert isinstance(a, (int, float)), "a must be numeric"
      if b == 0:
          log.warning("division by zero", extra={"a": a})
          raise ZeroDivisionError(f"a={a}, b={b}")
      result = a / b
      log.info("divide ok", extra={"a": a, "b": b, "result": result})
      return result
  ```
- Footnote: stdlib `logging` is what you'll use 95% of the time. `structlog` / `loguru` exist for niche ergonomics — reach for them only when context-binding or a terser API genuinely hurts.
- Thesis: *These three primitives show up again, adapted, at every level we'll cover today.*
- → **pause for IC-1** (3 min): *Pick the primitive* — four one-liners.




### Slide 6 — INTERLUDE · Demo 1 · Basic logging primitives

- Open `labs/09_monitoring/demos/1_basic_logging/` and run `python demo.py`.
- Budget: ~5 minutes.
- What students see: JSON rows in `app.log`, level filtering (INFO vs DEBUG), and a deliberate crash at the end. Teaching beat: "in dev, crashes are fine; silent failures are not."
- Returns to the deck by motivating the next step: *"one log file is already useful — now what changes when we watch it automatically?"*

### Slide 7 — From logging to monitoring

- **Monitoring = automated, continuous inspection** of logged data against expectations. Moves us from reading logs by hand to dashboards and alerts.
- **RED:** Rate, Errors, Duration — the three numbers every request-driven service wants on a dashboard.
- **USE:** Utilization, Saturation, Errors — the resource-side view.
- **SLOs, error budgets, MTTR, alerting culture** — the operational vocabulary built on top.
- Thesis: *Every dashboard is ultimately an aggregation of log events plus an expectation about their values.*
- → **pause for IC-2** (3 min): *Read the RED dashboard* — what fields must each event carry?

### Slide 8 — Traces: causal structure over events (and process mining)

- Some events belong together: a **session**, a **request**, a **business workflow**. If we give them a shared identifier, the events form a **trace**.
- In enterprise SaaS, that's exactly the input format for **process mining** — given a log with `case_id · activity · timestamp · actor`, discover the real business process that produced it.
- Key point: "trace" is first a *business* concept (a workflow you can replay) and only later an *engineering* concept (a request you can debug). LLM-era traces (OTel, Section 03) inherit both meanings.
- **Visual:** a small process-mining swimlane — case_id rows, activities as coloured blocks along a timeline.
- → **pause for IC-3** (3 min): *The untraceable request* — why per-service RED isn't enough.

### Slide 9 — Centralized logging + metrics at scale

- One log file per box doesn't scale. SaaS-scale services ship logs to a central system that **collects · aggregates · indexes · queries**.
- Common systems:
  - **Splunk** — enterprise workhorse, SPL query language, dashboards + alerts.
  - **Datadog / New Relic** — SaaS-hosted; logs + metrics + traces in one pane.
  - **ELK** (Elasticsearch / Logstash / Kibana) — open-source stack.
  - **Grafana Loki** — lightweight, log-only; fits an existing Grafana stack.
- **Metrics emerge naturally from centralization.** Once events are in one place you can aggregate them — counts, rates, histograms — cheaply. Metrics aren't a separate "pillar," they're *a cheaper, coarser view of the same events*.
- Dashboards = metrics + expectations. Alerts = automated checks on those expectations.

### Slide 10 — INTERLUDE · Demo 2 · Central log dashboard (Splunk-like)

- Open `labs/09_monitoring/demos/2_central_log_dashboard/` and open `dashboard.html`.
- Budget: ~8 minutes.
- What students see: three RED panels computed from a 10k-row synthetic `logs.ndjson`, a 15-minute `/checkout` incident visible on the error-rate panel, and a search box that drills from summary back to the raw rows.
- **Closing beat (plants the Section-02 seed).** All of these panels measure *is it up, fast, not erroring* — none measure *is the output correct*. For a SaaS endpoint there's no notion of a correct response to compare against; that axis only appears once the system is making predictions you could be right or wrong about. No new panel — the point is that the quality axis isn't even askable yet.
- Returns to the deck by motivating the next slide: *"now that everyone on the team can query everything, what you put into the log matters."*

### Slide 11 — Privacy: why it shows up here

- The moment logs are centralized and queryable, **what you put into them matters as much as the log itself**:
  - Centralized access — everyone on the team can query everything.
  - Regulation — GDPR, CCPA, right-to-erasure, data-residency rules.
  - Auditability cuts both ways: a detailed log is a liability as well as an asset.
- Classic failure modes:
  - Raw emails or tokens in `log.info` payloads.
  - "We'll redact later" pipelines that never get built.
  - Over-verbose production loggers inherited from dev.
- Preview: this concern expands in Section 03, where the log may contain the user's entire prompt.

### Slide 12 — Privacy: patterns that work

- **Hash or tokenise identifiers** — log `user_hash` not `user_email`; keep the mapping in one controlled store.
- **Environment-gated verbosity** — verbose in dev; redacted in prod; gated by a single config flag.
- **Redact at the event boundary**, not downstream. A scrubber runs inside the log formatter so raw data never hits disk.
- **Typed secret wrappers** — `class Secret(str)` whose `__repr`__ returns `"***"` — makes it impossible to accidentally serialize.
- **Retention + deletion** — decide upfront how long logs live and how you handle deletion requests.
- Every one of these patterns is itself an *assertion* about the log pipeline: "no raw PII ever crosses this boundary."

### Slide 13 — Roadmap: row 1 filled in

- **Row revealed: Traditional SW / SaaS**
  - What: control flow, exceptions, latency, error rate, resource use.
  - How: `assert` + exceptions + structured logs + centralized aggregation + dashboards on RED/USE + SLOs.
  - Why: know when broken, restore fast, debug post-hoc, keep a record, hit SLAs.

---

## Section 02 · Classical ML (4 slides)

### Slide 14 — What we monitor in classical ML

- Three things, in this order:
  - **Training-job health** — did the scheduled job run? did it produce a model artifact? how long did it take? any resource issues?
  - **Serving latency & throughput** — p50/p95 per endpoint; QPS; error rates. Same story as any other service.
  - **Quality** — accuracy / F1 / recall-at-k / whatever metric the model was trained for, measured on held-out data and (when labels arrive) on production traffic.
- Drift tests (K-S, PSI, χ²) are a subset of *quality monitoring* — useful when labels are delayed or absent.
- Thesis: *Classical ML monitoring is mostly standard service monitoring plus a quality metric. The open-ended complications arrive with LLMs.*

### Slide 15 — Example: a quality assertion

- **Code:**
  ```python
  from sklearn.metrics import accuracy_score

  preds = model.predict(X_holdout)
  acc = accuracy_score(y_holdout, preds)
  log.info("holdout eval", extra={"accuracy": acc, "n": len(preds)})
  assert acc >= 0.85, f"quality regression: accuracy={acc:.3f}"
  ```
- Same *shape* as an ordinary code assertion — but the value being asserted on is a *summary over a dataset*, not a single request. This is the smallest step from Section 01 into statistical territory.
- → **pause for IC-4** (3 min): *Which assertion broke?* — single-request `assert` vs. nightly-eval `assert`.

### Slide 16 — INTERLUDE · Demo 3 · Classical-ML monitoring dashboard

- Open `labs/09_monitoring/demos/3_classical_ml_dashboard/` and open `dashboard.html`.
- Budget: ~15 minutes.
- What students see: the training-job board (HUNG / CRASHED / RUNAWAY / HEALTHY tiles), the error-log drawer for a hung and a crashed job, and the quality-over-time chart with an injected drift window. Instructor toggles the Slide-15 assertion between a loose and a tight threshold live.
- Returns to the deck by staging Section 03: *"same dashboard shape, now swap the quality metric for a rubric score over an LLM's answer."*

### Slide 17 — Roadmap: row 2 filled in

- **Row revealed: Classical ML**
  - What: training-job health, serving latency, quality metrics.
  - How: job-status checks, service-level metrics, held-out evaluation, drift tests when labels lag.
  - Why: same as any service — plus "is the model still good?" — answered with statistics, not per-request assertions.

---

## Section 03 · LLM systems, escalating (11 slides)

### Slide 18 — Stage A · A single LLM call — anatomy & what to log

- A single LLM call has: a prompt (often templated), optional output schema, a completion, usage stats, a latency.
- **What to log — generously:**
  - Metadata: request id, model, prompt version, temperature, input/output tokens, latency, cost, outcome.
  - **The actual prompt and completion.** Non-negotiable for debugging. Subject to the privacy caveats from Slides 11–12 (hashing, env-gated verbosity, redact-at-boundary).
- **Structured-output contract:** declare the shape you want with a **Pydantic** model (or JSON schema). Parse after the call; re-ask once on validation failure.
- **Code:**
  ```python
  class Decision(BaseModel):
      action: Literal["buy", "sell", "hold"]
      confidence: float

  out = llm.structured(prompt, schema=Decision)
  log.info("llm.call", extra={
      "request_id": rid, "prompt_version": "v3",
      "prompt": prompt, "completion": out.model_dump_json(),
      "in_tokens": it, "out_tokens": ot, "latency_ms": ms,
  })
  ```
- **Data structure:** one JSON row per call — rich, flat, queryable.

### Slide 19 — Stage A · Monitoring over time

- One call is data. The **stream** of calls is where monitoring lives. What to watch:
  - **Latency distributions** — p50 / p95 / p99 per model, per prompt version. Alert on drift.
  - **Failure rate** — schema-validation fails, API errors, **timeouts**. Alert when timeout rate crosses threshold.
  - **Correctness sampling** — sample a small % of production traffic and run LLM-as-judge (L7) offline. Track rubric score over time.
  - **Cost** is first-class — spend per day, per model, per prompt version.
- Pattern: every dashboard for Stage A is an aggregation over the structured log rows from Slide 18.
- Thesis: *Same RED picture from Slide 7, with a quality axis added.*

### Slide 20 — Stage A · Content safety (separate from structural validation)

- Pydantic-valid ≠ safe. A well-formed answer can still be toxic, leak PII, or violate policy. These checks sit **after** the structural validation from Slide 18.
- **Toxicity / policy** — rule-based filters, classifier models, or an LLM judge. Run pre-response.
- **PII in the answer** — the model may *emit* PII even when the prompt was clean. Detect at the output boundary, then decide:
  - Redact before responding.
  - Block the response entirely.
  - Let it through, flag for audit.
- **Important distinction:** detecting PII in an answer is *different* from logging it. You might allow the answer but refuse to persist it in the log — two separate knobs, usually controlled by two separate configs.
- → **pause for IC-5** (3 min): *PII sorting* — separate "in the answer" from "in the log" on a three-case table.

### Slide 21 — Stage A · Guardrail design patterns

- Once you have checks, you need a policy for *what to do when one trips*. Four patterns you'll see everywhere:
  - **Fail-closed vs. fail-open** — per check, not global. Schema → fail-closed. Toxicity → fail-closed. Latency budget → often fail-open (serve stale).
  - **Retry-with-repair** — one bounded retry: *"your last answer didn't parse — here's the error, try again."*
  - **Fallback chains** — cheap model → strong model → human.
  - **Circuit breakers** — trip when a check's reject-rate spikes above threshold; stop hitting the guarded path temporarily.
- Every trip should produce a structured log entry and a metric — otherwise the guardrail is invisible to monitoring.

### Slide 22 — INTERLUDE · Demo 4 · LLM-call log viewer and dashboard

- Open `labs/09_monitoring/demos/4_llm_calls/` — first `log_viewer.html`, then `dashboard.html`.
- Budget: ~15 minutes.
- What students see: **Step 1** the raw log viewer over `llm_calls.ndjson` — filter by prompt version, expand a row to see the full prompt + completion. Teaching beat: *building a viewer like this is essentially free today — what Splunk sells is scale, not viewing.* **Step 2** the aggregation dashboard over the same file — latency, failure rate, cost, safety trips, guardrail outcomes. "View rows" links deep-link back to the viewer.
- Returns to the deck by motivating Stage B: *"flat rows are fine for one call — about to stop being enough."*

### Slide 23 — Stage B · Add context and tool calls

- Real systems extend the single call with two things:
  - **Context / memory** — system prompts, retrieved chunks (RAG), conversation history.
  - **Tool calls** — the model requests information or actions (search, code execution, APIs).
- The call becomes a **loop**: the model reasons, optionally calls a tool, reads the result, reasons again, and continues until it returns an answer. Still one logical request/response from the user's point of view.
- What we now need to keep track of along that flow:
  - **Memory state** — what the model actually saw at each step.
  - **Reasoning** — the model's explanation for what it's doing, when exposed.
  - **Tool-calling decisions** — which tool it picked and with what arguments.
  - **Tool logs** — tool call inputs, outputs, latency, errors.
  - **Session-level state** — `session_id`, step count, cumulative cost and latency, whether the session ended resolved.

### Slide 24 — Tracing a multi-step flow

- Once a single request involves several LLM calls, tool calls, and optional hand-offs to other agents, flat log rows can't show *which step led to which*. We need a **trace**: events with a shared request id and parent/child relationships.
- **Worked example** (from the lab): a research agent delegates a sub-task to a retrieval agent, which calls a search tool:
  ```
  research.task       [rid=7a2, 4.2s]
  ├── llm.call plan   [142ms]
  ├── retrieval.agent [3.1s]
  │   ├── llm.call    [310ms]
  │   └── tool.search [2.7s]
  └── llm.call answer [720ms]
  ```
- **Callback to Slide 8:** same idea as process mining — events with a shared case id reveal the process that produced them. Here the case id is the request id; the activities are LLM and tool calls.
- **Data structure:** a trace is a set of spans linked by a trace id and a parent span id. Parent/child relationships recover the causal order.
- **Visual:** the ASCII trace above, side-by-side with the Slide-8 process-mining swimlane.
- → **pause for IC-6** (3 min): *Tree vs. rows* — name three questions answerable only with parent/child info.

### Slide 25 — OpenTelemetry + GenAI semantic conventions

- **OpenTelemetry (OTel)** = the vendor-neutral standard for trace data.
- **GenAI semantic conventions** pick attribute names that work across all backends: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.operation.name`.
- Standard names = portability. Write instrumentation once, swap backends without touching code.
- **Code:** the lab's `trace_llm_call` context manager setting GenAI attributes and emitting a span.

### Slide 26 — INTERLUDE · Demo 5 · OpenTelemetry traces + viewer

- Open `labs/09_monitoring/demos/5_otel_traces/` and open `trace_viewer.html`.
- Budget: ~10 minutes.
- What students see: a Stage-B flow's spans exported as NDJSON, reconstructed into a collapsible waterfall; clicking a span shows the GenAI-semconv attributes (model, tokens, tool args). Optional side-trip: `--with-otlp` streams the same spans into a local Phoenix so students see the "real" UI on the same data.
- Returns to the deck by setting up tooling: *"you've read your own tree — now let's survey what's out there."*

### Slide 27 — What's out there (and when to reach for it)

- **Phoenix** (Arize) — notebook-first, open source.
- **Langfuse** — full-stack LLM observability: tracing + eval + prompt management.
- **Jaeger** — generic OTel backend, engineer-friendly, no LLM-specific UI.
- **LangSmith** — LangChain-native; hosted; proprietary.
- **Grafana Tempo** — fits into an existing Grafana/Prometheus stack.
- **Build-vs-buy thesis:** OTLP is standard, so swap cost is low. Start with a home-grown viewer to own the primitives; adopt a backend when the team outgrows it.

### Slide 28 — Roadmap: rows 3 & 4 filled in

- Single LLM call + context/tool/memory rows revealed together.
- Thesis: *Each rung up the complexity ladder forces a new data structure: row → session-keyed rows → causal tree.*

---

## Section 04 · Agents and systems of agents (5 slides)

### Slide 29 — Topology: orchestrators and sub-agents

- Orchestrators, planners, reasoners, sub-agents, handoffs, re-entry.
- The span structure from Slide 24 generalises: one request can spawn several sub-agent spans, each with its own LLM and tool calls underneath.
- **Visual:** orchestrator span at top, 2–3 sub-agent spans beneath, each with child LLM and tool spans.

### Slide 30 — Task-level and coordination assertions

- **Task-level:** "did the final answer satisfy the original user intent?" — an LLM-as-judge rubric (L7) over the whole span tree.
- **Coordination:** plan is valid; step budget bounded across the tree; no role drift ("research agent started writing code"); no planner-ping-pong.
- **Statistical at task level:** task-success rate, repair rate, human-escalation rate, cost/task.

### Slide 31 — Failure modes unique to multi-agent

- Silent agent disagreement.
- Cascading repair (each layer retries, cost explodes).
- Planner loops.
- Role confusion.
- → **pause for IC-7** (3 min): *Spot the pathology* — label three ASCII trees.

### Slide 32 — INTERLUDE · Demo 6 · Multi-agent trace

- Open `labs/09_monitoring/demos/6_multi_agent/` and reuse Demo 5's `trace_viewer.html`.
- Budget: ~10 minutes.
- What students see: a healthy orchestrator tree (wide, bounded depth) next to a `--failure-mode=planner_loop` run (tall, repeating retries); `task_judgments.ndjson` alongside shows the Slide-30 task-level rubric verdict. Instructor points at the shape and reads back Slide-31 vocabulary.
- Returns to the deck by closing the section: *"failure mode is a shape — and the shape is in the same spans file you had before."*

### Slide 33 — Roadmap: row 5 filled in

- Systems-of-agents row revealed.
- Thesis: *In agent systems, correctness is defined at the task level; the production trace is the eval sample.*
- Footnote: the runnable multi-agent lab is in **L13**.

---

## Section 05 · CI · Telemetry · Analysis · Reporting (8 slides)

### Slide 34 — CI eval gate

- Golden set + rubric judges run on every PR.
- Budgets: tokens, wall-clock, dollars — fail the build if exceeded.
- Regression check using **confidence intervals** (L8–L9), not raw means.
- Pin dataset version, judge version, prompt version in the run artifact.
- **Code:** `test_rubric_regression` pytest skeleton.

### Slide 35 — Telemetry: what makes remote monitoring possible

- Definition: the operational act of *shipping* structured data (logs / metrics / spans) off the service to a remote backend.
- Without telemetry you can only monitor by SSH'ing into the box.
- **OTLP** = vendor-neutral wire format — same spans go to Tempo / Jaeger / Phoenix / Langfuse.
- **Code:** ~3-line diff swapping `ConsoleSpanExporter` → `OTLPSpanExporter`.
- Sampling: head-based (decide at trace start) vs. tail-based (keep all errors, 1% of successes).
- Cardinality discipline — no user-generated strings in metric tags.

### Slide 36 — Online evals

- **Canary** — small % of traffic on new prompt/model, side-by-side rubric/guardrail comparison.
- **Shadow** — new version sees real input, output judged but not shown.
- **Sampled LLM-as-judge** on production traffic (L7 caveats apply).
- **Drift signals:** rising reject-rate, embedding-distribution shift, output-length shift, tool-mix shift.

### Slide 37 — Analysis: turning telemetry into answers

- Monitoring tells you *what's happening now*. **Analysis** is the next step — *why is it happening, what's different, and what should we change?* — run on the same logged/traced data, usually offline.
- Typical operations on the data:
  - **Aggregation** — summary stats per prompt version, model, user cohort, time window.
  - **Segmentation** — slice by dimension and compare (prompt v2 vs v3; weekend vs weekday; cohort A vs B).
  - **A/B comparison** — canary slice vs control; difference with **confidence intervals** (callback to L8–L9). Not just "which number is bigger."
  - **Drill-down** — filter to a failing subset, pull the individual traces, read them.
  - **Trend detection** — rolling windows to spot drift *before* an SLO breaks.
- **Tooling:** notebook scripts against the exported JSON rows and spans · analysis UIs built into Phoenix / Langfuse · at scale, SQL against a logs warehouse — but for this lab we stay with scripts over files.
- **Code:** a compact analysis script from the lab — loads the span export, groups by `prompt_version`, reports quality with CIs. Same shape as the CI regression check from Slide 34, run post-hoc instead of pre-merge.
- Thesis: *The same structured data powers live dashboards, CI gates, and after-the-fact analysis. Build the pipeline once.*

### Slide 38 — INTERLUDE · Demo 7 · Analysis / A-B comparison

- Open `labs/09_monitoring/demos/7_ab_analysis/` and run `python analyze.py`; open the generated `analysis_report.html`.
- Budget: ~10 minutes.
- What students see: the five Slide-37 operations applied to the same `llm_calls.ndjson` from Demo 4 plus the `task_judgments.ndjson` from Demo 6 — an executive one-liner with a CI, side-by-side bars with whiskers, and a drill-down list that deep-links into Demo 5's trace viewer for the 20 worst cases.
- Returns to the deck by setting up reporting cadences: *"same file — different audience, different cadence."*

### Slide 39 — Reporting cadences

- **Real-time** → alerts on hard assertion breaks.
- **Daily** → team quality/cost summary.
- **Weekly** → PM/leadership: one quality number **with CI**, one cost number, one safety number, short prose "what changed and why."
- **Visual:** the lab's 4-week weekly-report chart (quality w/ CI bars · cost/request · reject-rate).

### Slide 40 — Incident reviews for AI systems

- LLM failures are usually **distribution shifts**, not bugs.
- Post-mortems look different from Software 1.0:
  - What new traffic pattern appeared?
  - What upstream model / prompt / tool changed?
  - What guardrail / rubric was silent when it shouldn't have been?

### Slide 41 — Thesis for Section 05

- *CI gate, production dashboard, and post-hoc analysis all run the same assertions on the same structured data — only the cadence differs. Telemetry is what lets them share a pipeline.*

---

## Closing (2 slides)

### Slide 42 — Summary matrix, fully populated

- The complete 5×3 table.
- Speaker: "This is the one artifact to keep from today."

### Slide 43 — Take-aways & what's next

- Logging is the primitive. Monitoring is continuous assertion-checking on top.
- Assertions evolve with system complexity: code → statistical → semantic → trace → task.
- Telemetry is what makes remote monitoring possible.
- Same assertions, different cadences: CI gate ↔ production dashboard.
- Humans *and* AI both monitor AI — operators read dashboards, agents check other agents.
- Next: **L13** — multi-agent systems in depth · **L15** — long-term maintenance.

---

## Design notes for when we build the deck

- Reuse Ocean Gradient palette from v1 deck (`C.bg=0E1726`, `C.teal=1C7293`, `C.accent=F4A261`).
- Keep `FONT_M = "Courier New"` for code blocks (Consolas substitution bug from v1).
- **Progressive-reveal pattern:** slides 3, 13, 17, 28, 33, 42 all show the same 5×3 matrix with more rows revealed each time — consistent template (same row order, same column widths, only the "filled" cells change).
- **Interlude slides** (6, 10, 16, 22, 26, 32, 38) share a common template — Ocean-accent background, large "→ demo X" title, file path in mono, 60-second speaker prompt. Visually distinct from normal content slides so presenter can't miss the cue to step off the deck.
- **In-class drills** (IC-1…IC-7) stay inline on their parent slide (5, 7, 8, 15, 20, 24, 31) as a final bullet — they're 2–3 min pauses, not full slide transitions.
- Code slides should be ≤ 12 lines and use the monospace font.
- Each section ends on a thesis-block slide in the accent colour.
- **Privacy thread:** Slides 11–12 (SaaS-scale privacy) → Slide 20 (LLM-specific: PII in the *answer*, distinct from PII in the *log*). Same iconography; Slide 20 flashes back to the problem framing from Slide 11 with one line.
- **Checks thread:** Slide 5 (code-level `assert` + exceptions) → Slide 15 (statistical assertion over a dataset) → Slide 19 (aggregate checks: latency SLO, failure-rate alert, sampled correctness) → Slide 30 (task-level rubric over a span tree). Same *check ≥ threshold* shape at every rung; what changes is the object being checked.
- **Traces thread:** Slide 8 (business / process mining) → Slide 24 (request-level, ASCII tree) → Slide 25 (OTel + GenAI semconv). Slide 24 shows the ASCII tree alongside the Slide-8 process-mining swimlane so the family resemblance is visible.

