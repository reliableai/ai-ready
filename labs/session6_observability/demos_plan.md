# L10 · Demos plan — Python scripts + HTML dashboards

Each demo is **two artefacts**:

1. A **self-contained Python script** students can run from the terminal (`python demo_XX.py`). No servers, no Docker. Produces a JSON/CSV file plus, when appropriate, a **standalone HTML dashboard** written to the same folder.
2. The **HTML dashboard** — one file, inlined JS/CSS (Chart.js via CDN), loads the JSON the script produced via `fetch('./data.json')` or has it embedded as a `<script>` variable. Opens with double-click, no web server.

This keeps the pattern "here is the code → here is what you see" obvious throughout the lecture. Each demo lives in `labs/09_monitoring/demos/<n>_<name>/`.

For the OpenTelemetry demo (05), we additionally include **optional** instructions for piping the same span data into a local Phoenix or Jaeger instance — so students see the "real" OTel UI if they want, but the lab still works fully without it.

---

## Demo map


| #   | Demo                                | Supports slide(s)         | Artefacts                                                                       |
| --- | ----------------------------------- | ------------------------- | ------------------------------------------------------------------------------- |
| 1   | Basic logging primitives            | Slide 5                   | `demo.py` → console + `app.log`                                                 |
| 2   | Central-log dashboard (Splunk-like) | Slides 6, 8, 11           | `gen_logs.py` + `dashboard.html`                                                |
| 3   | Classical-ML: catching stuck jobs + drift | Slides 12, 13, 14   | `train_and_monitor.py` + `dashboard.html`                                       |
| 4   | LLM-call logging **and** monitoring | Slides 15, 16, 17, 18, 23 | `llm_calls.py` + `log_viewer.html` + `dashboard.html`                           |
| 5   | OpenTelemetry traces + viewer       | Slides 19, 20, 21, 22, 29 | `traced_flow.py` + `trace_viewer.html` (+ optional Phoenix/Jaeger instructions) |
| 6   | Multi-agent trace                   | Slides 24, 25, 26, 27     | `multi_agent.py` + `trace_viewer.html` (reused)                                 |
| 7   | Analysis / A-B comparison           | Slides 28, 30, 31, 32     | `analyze.py` + `analysis_report.html`                                           |


---

## Demo 1 — Basic logging primitives

**Purpose.** Make the three Python primitives (`assert`, exceptions, `logging`) concrete before we introduce any infrastructure. Students see the *shape* of a well-formed log line and the difference between an invariant violation, an expected-but-exceptional event, and a side-channel record.

**Learning outcome.** By the end of this demo a student can: (1) point to the right primitive for a given situation; (2) read a JSON log row and name each field; (3) change the log level and predict what appears vs. disappears; (4) explain why a single log file is already useful even without any monitoring system on top of it.

**Script:** `demo.py`

- Defines the `divide(a, b)` function from Slide 5.
- Drives it with a handful of cases: valid, `b=0`, wrong type.
- Demonstrates level filtering: first run with `level=INFO`, then re-run with `level=DEBUG`.
- Uses `logging.basicConfig` with a JSON formatter — one JSON object per line → `app.log`.
- Ends by printing "Now open `app.log` and you see structured rows ready to ship anywhere."

**Dashboard:** *none yet* — intentional. This demo exists to make the point that a log line alone is already useful.

**Runs:** `python demo.py` · cost: $0 · offline.

---

## Demo 2 — Central log dashboard (Splunk-like)

**Purpose.** Show what changes the moment events are shipped to one place: dashboards, search, alerts — all of them are just aggregations and filters over the log stream. Gives students the Splunk / Datadog / ELK picture without needing any of those products.

**Learning outcome.** By the end of this demo a student can: (1) explain that RED panels are aggregations over the raw log — counts, rates, and percentiles computed by iterating the JSON rows — not a separate pillar; (2) spot an incident on the dashboard and drill from the summary view into the individual log rows that caused it; (3) articulate why centralisation makes privacy Slides 9–10 non-optional — everyone on the team can now see everything.

**Script:** `gen_logs.py`

- Simulates a small SaaS service over 24 hours: `POST /login`, `GET /feed`, `POST /checkout`, etc.
- ~10k synthetic requests with realistic latency distributions (bimodal, occasional spikes).
- Injects an incident: a 15-min window of elevated 500s on `/checkout`.
- Writes `logs.ndjson` (one JSON per line) and also emits a pre-aggregated `metrics.json` (RED per endpoint per minute).

**Dashboard:** `dashboard.html`

- Three panels:
  - **Rate** per endpoint (stacked area).
  - **Error rate** per endpoint (line, with the incident visible).
  - **Duration p50/p95** per endpoint (band chart).
- A "search" box that filters `logs.ndjson` by substring — stand-in for SPL. Students can search for `500` and see only the error rows.
- Chart.js via CDN, Ocean-gradient palette to match the deck.

**Teaching beats:**

- Open `dashboard.html` → point at the 500s spike → click "search: 500" → drill into the raw rows.
- Loop back to Slide 7: "Every panel here is an aggregation over the same log file."
- **Closing beat (plants the Section-02 seed).** "Look at what these panels measure: all of them answer *is the service up, fast, not erroring*. None of them answer *is the output correct* — for a SaaS endpoint there's no notion of a 'correct' response to compare against. That axis only appears when something in the system is making predictions you could be right or wrong about. That's Section 02." *Do not add a panel for this; the point is that the quality axis is not even askable yet.*

---

## Demo 3 — Classical ML monitoring dashboard

**Purpose.** Put the three classical-ML monitoring concerns from Slide 12 — training-job health, serving latency, quality — side by side on one screen, and use the dashboard to *catch specific failures*: training jobs that hang, training jobs that crash (and why, from error logs), and model quality drifting after deployment.

**Learning outcome.** By the end of this demo a student can: (1) spot a stuck training job from the dashboard (no heartbeat for N minutes) and drill down into its error log to see *why* — OOM, CUDA error, data loader exception; (2) spot a crashed job vs. a hung job from the same panel and decide which one needs a restart vs. a code fix; (3) read the quality-over-time chart, see a drift event starting, and decide whether the drop is noise or signal; (4) see that the Slide 13 `assert acc >= threshold` is *the same primitive* as Slide 5, applied to a statistic rather than a single value.

**What we want to catch** (explicit list — each has a corresponding panel signal + log drill-down):

- **Hung training job** — last heartbeat > 10 min ago, no stdout/stderr activity, job still marked RUNNING. Cause usually visible in the last log lines: data loader deadlock, stuck on a corrupt shard, waiting on a GPU allocation.
- **Crashed training job** — job marked FAILED, non-zero exit, traceback in the error log. Top causes we simulate: OOM on a bigger batch, `nan` loss, missing feature column after an upstream schema change.
- **Runaway training job** — still running but duration > 3× the rolling median for this model; a hint that something's off even before it officially fails.
- **Serving latency regression** — p95 creeps above SLO after a deploy; usually correlates with a model-size or batch-size change visible in the training-run metadata.
- **Model quality drift** — rolling accuracy on labelled traffic trends down. We simulate a gradual input-distribution shift (new user cohort, seasonality) and a sudden break (upstream feature pipeline changed units).
- **Silent quality regression after retrain** — holdout accuracy on the new model is fine, but production accuracy drops: the holdout set is stale. Catches the Slide-13 assertion passing while the real system gets worse.

**Script:** `train_and_monitor.py`

- Trains a tiny sklearn classifier (logistic regression on the digits dataset) — takes <2 seconds for the happy path.
- Also simulates a **fleet of training runs over the last 2 weeks** — ~40 runs covering all six failure scenarios above. Each run writes:
  - `train_runs.ndjson` — one row per run with `job_id`, `model`, `status` (RUNNING / SUCCEEDED / FAILED / HUNG), `started_at`, `last_heartbeat_at`, `duration_s`, `holdout_acc`, `exit_code`.
  - `train_errors.ndjson` — per-run error-log tail (last 40 lines) with a parsed `error_kind` field (`OOM` / `NaN` / `SchemaMismatch` / `DataLoaderDeadlock` / `None`).
- Then "serves" the latest model: 2000 synthetic prediction calls written to `predictions.ndjson`, with labels arriving after a 1-minute delay. Injects a drift window and a feature-pipeline-broken window so the quality panel has events to explain.
- Runs the Slide-13 assertion two ways: passing threshold → green, `acc >= 0.95` → red — both the happy case *and* the "holdout passes, production drifts" case are exercised.

**Dashboard:** `dashboard.html`

- Panel 1 — **Training-job board:** last 40 runs as coloured tiles (green/red/grey-running/amber-hung). Click a tile → side drawer with the error-log tail and `error_kind`.
- Panel 2 — **Job duration vs. rolling median:** catches runaway jobs before they fail.
- Panel 3 — **Serving latency:** p50/p95 over the prediction stream, SLO line overlaid.
- Panel 4 — **Quality over time:** rolling accuracy once labels arrive, with the threshold line and coloured bands for the two injected drift events. Clicking a band highlights the contemporaneous training runs on Panel 1.

**Teaching beats:**

- Demo 1: click a grey tile → "this job is hung." Read the last log line from the drawer → "it's stuck on a corrupt shard. Restart won't help; fix the data first."
- Demo 2: click a red tile → "OOM. Restart with a smaller batch or a bigger box."
- Demo 3: zoom the quality panel into the drift event; show that the training-run on Panel 1 immediately before looked healthy — the signal only appears in production.
- Demo 4: re-run the assertion with the tight threshold → it fails on the production stream *even though* the holdout eval passed. Set up the L11 topic on eval-set staleness.
- Close by pointing out this dashboard is *structurally identical* to Demo 2 — same RED idea plus one extra quality line — and setting up Section 03: "Now swap the model for an LLM. Holdout accuracy becomes a rubric score. Everything else is the same."

---

## Demo 4 — LLM-call logging and monitoring

**Purpose.** Turn Slides 15-18 into something students can see and interact with, in two steps. **First**, show what a single LLM call looks like on disk (Slide 15) and open a raw log viewer over the call stream — the point is that *today, building a serviceable viewer over any log format is a one-file job*; you don't need Splunk to read your own logs. **Then**, layer the aggregation dashboard on top so students see monitoring as a view of the same underlying data, not a separate system.

**Learning outcome.** By the end of this demo a student can: (1) name every field in the Slide-15 log schema and explain why each is there; (2) read a raw-log viewer to inspect individual calls, filter by prompt version or outcome, and pull up the full prompt + completion for any single call; (3) read the aggregation dashboard and decide which prompt version to ship based on latency, cost, quality, safety, and guardrail-trip rate together rather than any one in isolation; (4) distinguish a Pydantic-validation failure (structural) from a content-safety trip (semantic) — and explain why those are separate knobs; (5) see that the raw viewer and the dashboard read the *same file* — the dashboard just buckets the rows the viewer shows one by one.

**Script:** `llm_calls.py`

- No real API key needed: includes a `FakeLLM` that returns structured outputs (Pydantic `Decision` model from Slide 15) with realistic latency, cost, and occasional schema-validation failures / toxic outputs.
- A flag `--live` lets students plug in a real provider if they have a key.
- Generates 2000 calls across two prompt versions (`v2` and `v3`) — `v3` is deliberately slightly better on quality but slower.
- Writes `llm_calls.ndjson` (the Slide-15 schema exactly) — the single source of truth for both HTML artefacts below.
- Separately runs a toxicity classifier (stub keyword-based) and a PII detector (regex) over each output; appends `safety.ndjson`.

**Step 1 — Raw log viewer:** `log_viewer.html`

- Loads `llm_calls.ndjson` directly. One row per call, newest first.
- Columns: timestamp · `request_id` · model · prompt version · latency · tokens · cost · outcome (ok / schema-fail / timeout / safety-trip).
- Click a row → expands to show the full prompt, the full completion, and the raw JSON blob.
- Free-text filter box (search across all fields) and a pair of dropdowns (prompt version, outcome).
- ~150 lines of HTML + vanilla JS, no build step.
- **Teaching beat:** "This is how far you can get for one lecture's worth of typing — honestly, less, with an LLM writing the HTML for you. The point of Splunk et al. (Slide 8) isn't that log viewing is hard; it's the scale, retention, access control, and integration. For a single service, a file like this is often enough."

**Step 2 — Monitoring dashboard:** `dashboard.html`

- Same input file. Aggregations and trends over time.
- Panel 1 — **Latency distributions** — p50/p95/p99 per prompt version (Slide 16).
- Panel 2 — **Failure rate** — schema fails, API errors, timeouts (Slide 16).
- Panel 3 — **Cost per day per prompt version** (Slide 16).
- Panel 4 — **Content-safety trips** — stacked bar: toxicity / policy / PII-in-answer (Slide 17).
- Panel 5 — **Guardrail outcomes** — fail-closed / repaired / fell-back / served (Slide 18).
- Every panel has a "view rows" link that deep-links back into `log_viewer.html` with the same filter applied.

**Teaching beats:**

- Start in the raw viewer. Scroll, filter, expand a row — "this is just the file from Slide 15."
- Switch to the dashboard. "Every one of these panels is the same rows, bucketed and counted — same file, different reduction."
- Click "view rows" on a safety-trip bar → jump back to the viewer, now filtered to the five offending calls, and read their completions.
- Row 3 of the matrix (Slide 23) is readable off this pair of views.

---

## Demo 5 — OpenTelemetry traces + viewer

**Purpose.** Show why, as soon as a single user request fans out into several LLM and tool calls, flat log rows stop being enough and you need a causal tree. Make OpenTelemetry — the standard for representing that tree — a concrete file on disk rather than an abstract concept.

**Learning outcome.** By the end of this demo a student can: (1) describe a span (trace id, span id, parent span id, timing, attributes) well enough to reconstruct a trace tree from its raw rows; (2) point out where each GenAI semantic-convention attribute (`gen_ai.request.model`, token counts, etc.) appears and why using standard names matters for portability; (3) click a suspicious span and identify the slow step in a multi-step LLM flow — a thing you physically cannot do from flat logs alone; (4) explain the one-line swap from `ConsoleSpanExporter` to `OTLPSpanExporter` that turns local logging into Slide-29 telemetry.

**Script:** `traced_flow.py`

- Uses the real `opentelemetry-sdk` with a **file exporter** writing NDJSON spans to `spans.ndjson`. This is what's actually nice: the same code also works with `OTLPSpanExporter` (Slide 29) — swap one line.
- Runs a Stage-B flow from Slide 19: an `answer.task` root span wraps: LLM plan call → retrieval sub-operation (its own span) → search tool call (child span) → LLM answer call.
- Attributes follow the GenAI semantic conventions (`gen_ai.request.model`, etc. — Slide 21).
- Includes a `--with-otlp` flag that switches the exporter to OTLP → localhost:4317 for optional Phoenix/Jaeger.

**Dashboard:** `trace_viewer.html`

- Loads `spans.ndjson`, reconstructs the tree by `trace_id` + `parent_span_id`, renders it as a **collapsible waterfall** — left column: nested name list; right column: timeline bars.
- Click a span → inspector panel shows its attributes (prompt version, model, tokens, tool name/args, latency).
- Toggle to view the same data as a **process-mining swimlane** — callback to Slides 7 and 20.

**Optional "real OTel" path:** `README_PHOENIX.md` in the demo folder: `pip install arize-phoenix && phoenix serve`, then `python traced_flow.py --with-otlp`. Students see the same trace in Phoenix's UI.

**Teaching beats:**

- Demo the ASCII from Slide 20 lives on disk as span rows.
- Click one span to show "this is what we'd have lost if we only had flat logs."

---

## Demo 6 — Multi-agent trace

**Purpose.** Reuse Demo 5's viewer on a more complex shape so students can *see* what changes when the system is a set of agents rather than a single LLM loop — and see the Section-04 failure modes (planner loops, cascading repair) as tree pathologies rather than vocabulary.

**Learning outcome.** By the end of this demo a student can: (1) recognise a healthy orchestrator/sub-agent tree vs. a pathological one at a glance (wide-and-bounded vs. tall-and-retrying); (2) name where task-level and coordination assertions from Slide 25 attach in the span tree; (3) use the viewer + the task-judgment file together to answer "did this request actually succeed?" — which, in agent systems, is no longer equivalent to "did it return 200?".

**Script:** `multi_agent.py`

- Reuses the OTel plumbing from Demo 5.
- Models the Slide-24 topology: one `orchestrator.task` parent, two `sub_agent.research` and `sub_agent.writer` children, each spawning their own LLM and tool spans.
- Includes a `--failure-mode=planner_loop` flag that induces the Slide-26 failure (cascading repair → ballooning cost) so students can see it in the viewer.
- Evaluates the final output against a golden task and writes `task_judgments.ndjson` (rubric score, pass/fail).

**Dashboard:** `trace_viewer.html` (reused from Demo 5).

**Teaching beats:**

- Run once happy-path → wide tree, bounded depth.
- Run with `--failure-mode=planner_loop` → tall, skinny tree with repeated retries → point at it and match it to Slide 26.
- Open `task_judgments.ndjson` → task-level assertions from Slide 25.

---

## Demo 7 — Analysis / A-B comparison

**Purpose.** Close the loop the lecture has been building toward: take the exact same structured data that fed the live dashboards in Demos 4-6 and use it *offline* to answer questions monitoring can't — "why did this happen, how do v2 and v3 actually compare, which traces should we look at?" Make the Slide-34 thesis physical: one pipeline, three consumers.

**Learning outcome.** By the end of this demo a student can: (1) run each of the five analysis operations from Slide 31 (aggregation, segmentation, A/B with CIs, drill-down, trend detection) on real data; (2) read an A/B result presented with confidence intervals and avoid concluding from a point estimate alone — the explicit callback to L8-L9; (3) go from a summary statistic to a specific failing trace in two clicks, which is the move that turns dashboards into root-cause analysis; (4) explain why the CI gate (Slide 28), the live dashboard (Demo 4), and this analysis script are the same assertions run at different cadences.

**Script:** `analyze.py`

- Inputs: `llm_calls.ndjson` from Demo 4 (two prompt versions mixed) and `task_judgments.ndjson` from Demo 6.
- Operations on the data (mirroring Slide 31's list):
  - **Aggregation** — mean / median latency, pass-rate, cost by prompt version.
  - **Segmentation** — split by user cohort and by hour-of-day.
  - **A/B comparison** — prompt v2 vs v3 on rubric-pass rate; bootstrap 95% CI on the difference (callback to L8-L9).
  - **Drill-down** — pull the 20 worst traces by latency; write their span trees to a report.
  - **Trend detection** — rolling-window quality; flag windows where the lower CI bound dips below the SLO.
- Writes `analysis_report.html` directly — no separate dashboard file needed.

**Dashboard:** `analysis_report.html`

- Generated by the script (uses a Jinja-like f-string template).
- Three sections:
  - **Executive row:** one-line verdict ("v3 is +3.1pp on pass-rate, 95% CI [1.8, 4.4]; cost +7%").
  - **Comparison charts:** side-by-side bars with CI whiskers (Chart.js).
  - **Drill-down:** the 20 worst traces as an expandable list, each linking to the span view in Demo 5's viewer.

**Teaching beats:**

- Same input files as the live dashboards — different cadence, different question.
- Point at Slide 34 thesis: one pipeline → three consumers (CI gate, dashboard, analysis).

---

## Cross-cutting conventions

- **Palette & typography:** every dashboard uses the Ocean-Gradient palette from the deck for continuity.
- **No server required:** all HTML files open with `file://`. Script-generated data either lives in the same folder or is inlined.
- **One script per demo, ≤ 200 lines** — students can read the whole thing in one sitting.
- **Every script has a `--help`** that names the slides it supports.
- **Privacy in demos:** any synthetic user field is already hashed in the scripts; a big comment points at Slides 9-10.
- **Requirements file:** one top-level `demos/requirements.txt` — `pydantic`, `scikit-learn`, `opentelemetry-sdk`, `numpy`. No heavyweight deps.

## Lecture flow with demos

- **Slide 5** → switch to terminal, run Demo 1, point at `app.log`.
- **Slide 8** → open Demo 2 dashboard, search for 500s.
- **Slides 12-14** → Demo 3 dashboard; show the assertion fail on screen.
- **Slides 15-23** → Demo 4 dashboard; end by saying "flat rows, but we're about to need a tree."
- **Slide 20** → open Demo 5's trace viewer; expand the tree.
- **Slide 26** → rerun Demo 6 with `--failure-mode=planner_loop`; show the pathology in the viewer.
- **Slide 31** → open Demo 7's analysis report.
- **Slide 34 (thesis)** → gesture back at Demos 4, 5, 7: "Same file. Three uses."

---

## Build order (recommendation)

1. Demo 1 (trivial; warms up the pattern).
2. Demo 4 (core LLM story; defines the JSON schema the other demos reuse).
3. Demo 5 (OTel plumbing; trace viewer is reused by Demo 6).
4. Demo 7 (analysis — depends on Demos 4 and 6 output).
5. Demos 2, 3, 6 — round out the progression.

