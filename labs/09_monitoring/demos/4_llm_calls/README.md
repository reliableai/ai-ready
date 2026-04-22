# Demo 4 — LLM-call log viewer + dashboard (Stage A)

Supports **Slides 18–22** of L10 (Section 03 — Stage A: a single LLM call).
Pairs with **lab exercise LX-4**.

## Purpose

Move the monitoring story from "is the service up?" (Demo 2) and
"is the model right?" (Demo 3) to **"is the generation usable?"** —
the axis that appears the moment the thing being monitored is a call to
an LLM. This is the first demo where the row being logged contains the
actual prompt and the actual completion, where the quality gate is a
**schema check** instead of a status code, and where two wholly new
signals — **guardrail trips** and **cost per call** — show up as
first-class panels.

The demo ships *two* HTML files backed by the same NDJSON, and the
pairing matters:

- `log_viewer.html` is the raw-row side. Filter by prompt version,
  outcome, day, free-text; expand any row to see the full prompt +
  completion + guardrail JSON.
- `dashboard.html` is the aggregate side. Five panels over the same
  file, each panel deep-linking back to the log viewer via URL query
  params — `?outcome=schema_fail&prompt_version=v3` drops you into the
  195 rows that produced the spike.

That round-trip — summary panel → drill-down → single row → full
prompt — is the Slide-22 move, and it's the one students most often
haven't seen on a real system.

## Learning outcomes

After running and reading this demo, you should be able to:

1. Name the fields that should be on every LLM-call log row without
   looking: `request_id`, `model`, `prompt_version`, `temperature`,
   `prompt`, `completion`, `input_tokens`, `output_tokens`,
   `latency_ms`, `cost_usd`, `outcome`, `guardrail`. Each one answers a
   question a dashboard panel wants to ask. (Slide 18.)
2. State the three outcome categories that matter for monitoring and
   which panel each one lives on: **structural** failures
   (`schema_fail`, parse errors) → failure panel; **transport**
   failures (`timeout`, `api_error`) → failure panel; **content**
   failures (`blocked_pii`, `blocked_toxic`) → guardrail panel.
   Same event shape; three different dashboard homes. (Slides 18, 20.)
3. Point at the **schema-fail panel** on `dashboard.html` and trace
   the day-3 spike all the way down to individual v3-prompt rows via
   the "view rows →" link. Then say why the other panels barely flinched.
4. Read the **latency panel** and articulate the model-specific story:
   the vendor incident on days 7–8 is visible on `gpt-4o` (p95 pegged
   at the 15 s timeout cap) and almost invisible on `gpt-4o-mini` —
   *because they're different providers from the dashboard's point of
   view.* Per-model slicing is non-optional for LLM fleets.
5. Explain why the **cost panel** is a first-class signal rather than
   a finance-team concern: a verbose-context config change on day 11
   roughly doubles spend with no latency or quality penalty. The only
   panel that notices is cost.
6. State the Slide-20 distinction live: *PII in the log is Demo 1's
   problem. PII in the answer is Demo 4's problem.* The guardrail
   panel fires on the second.

## How to run

```bash
python gen_calls.py           # writes llm_calls.ndjson + calls.js (~2.6 MB)
open log_viewer.html          # or double-click it
open dashboard.html           # side-by-side with the log viewer
```

`gen_calls.py` is deterministic (seed=42 + frozen
`NOW = 2026-04-27T18:00`). It writes two files:

- `llm_calls.ndjson` — 3000 calls over the last 14 days, one JSON
  object per line. This is the canonical log file — the thing a
  service would ship to Splunk / Loki / a warehouse. Grep it:
  ```bash
  grep '"outcome": "schema_fail"' llm_calls.ndjson | head
  grep '"prompt_version": "v3"'   llm_calls.ndjson | wc -l
  python -c "import json; print(sum(json.loads(l)['cost_usd'] for l in open('llm_calls.ndjson')))"
  ```
- `calls.js` — the same rows wrapped as `window.__CALLS__` so the two
  HTML files can load them via `<script src>` from `file://`. Same
  trick as Demos 2 and 3.

Schema of one row:

```json
{
  "ts": "2026-04-17T03:14:22",
  "request_id": "req_000412",
  "model": "gpt-4o-mini",
  "prompt_version": "v3",
  "temperature": 0.2,
  "prompt": "Classify the following support ticket ...",
  "completion": "{\"sentiment\": \"angry\", \"urgency\": \"high\", ...",
  "input_tokens": 312,
  "output_tokens": 48,
  "latency_ms": 734,
  "cost_usd": 0.000076,
  "outcome": "schema_fail",
  "guardrail": {"schema_ok": false, "toxicity_ok": true,
                "pii_found": false, "pii_blocked": false}
}
```

## The scenario

A support-ticket triage service. Each call takes a user-submitted
ticket and asks the model to produce a JSON object with three fields:
`sentiment` (`angry|neutral|happy`), `urgency` (`low|med|high`), and a
short `summary`. Two models are in use — `gpt-4o-mini` for 70% of
traffic (cheap default) and `gpt-4o` for the 30% the router marks as
hard. That's the steady state.

Over the 14-day window four incidents are injected — each one designed
to be visible on exactly one of the five dashboard panels and almost
invisible on the others:

```
day  3.0 – 3.8    prompt v3 shipped — missing curly brace in the template
                  → ~78% of v3 calls produce unparseable JSON
                  → schema-fail panel spikes; latency/cost unchanged
                  → rolled back at 3.8 (20h window)

day  7.5 – 8.5    vendor incident on gpt-4o — 3x latency, 18% forced timeouts
                  → latency panel: p95 rails to 15 s on gpt-4o only
                  → failure panel: timeout bars appear on d7 and d8
                  → mini and cost are clean

day 11 onward     "verbose context" rollout — 3x input_tokens
                  → cost panel: mini line roughly doubles
                  → latency ~flat, quality ~flat; only cost moves

day 13 onward     real-user PII appears in tickets (phone numbers, addresses)
                  → model echoes it into summary
                  → output-side PII guardrail blocks ~70%
                  → guardrail panel: blocked_pii rises from 0 to ~68/day
```

Every incident has a cheap, mechanical signature on exactly one axis.
That's the argument for multi-panel dashboards: no single metric would
have caught more than one of these.

## What you should see

### `log_viewer.html`

Opens with the 50 most recent rows, paginated 50 at a time. Five
filters across the top:

- **prompt_version** — `v1`, `v2`, `v3` (the broken one).
- **model** — `gpt-4o-mini`, `gpt-4o`.
- **outcome** — `ok`, `schema_fail`, `timeout`, `api_error`,
  `blocked_pii`, `blocked_toxic`.
- **day** — `d0` … `d13`, indexed from the start of the window.
- **search** — free-text match across prompt + completion.

Click any row to expand it — a grid of metadata, the full prompt, the
full completion, and the guardrail JSON. Try:

- Filter `outcome=schema_fail` → 153 rows. Open a few and notice the
  `completion` field holds a truncated JSON fragment — the parser
  would have rejected it.
- Filter `prompt_version=v3` → 195 rows. 153 of them are schema_fail;
  the rest made it through by luck.
- Filter `outcome=blocked_pii` + search `phone` → rows where the
  ticket contained a phone number, the model echoed it, and the
  output guardrail blocked the response.
- URL deep-link: open `log_viewer.html?outcome=timeout` directly.
  Every dashboard panel uses this mechanism to drill into rows.

### `dashboard.html`

Four top-line KPIs and five panels. The KPIs are a sanity bar across
the window: `calls (14d) = 3,000`, `failure rate ≈ 5.6%`,
`p95 latency ≈ 1.5 s`, `total spend ≈ $0.35`. Everything below reads
over the same 3000 rows.

**Panel 1 — Latency p50 / p95 by model (8-h buckets, log y-axis).**
Four lines: mini-p50, mini-p95, 4o-p50, 4o-p95. The dashed 4o-p95
line rails to the 15 s timeout cap for three consecutive buckets on
days 7–8. The mini lines barely move. Teaching beat: *this is the
entire argument for per-model slicing* — a single "overall latency"
line would have smeared the incident over six hours of traffic and
buried it.

**Panel 2 — Failure rate per day (stacked bars).**
schema_fail + timeout + api_error. One tall red bar on day 3 (153
schema_fails from v3). A shorter amber stack on days 7–8 (11 timeouts
across the vendor incident). Baseline is zero — the service is
healthy when it's healthy. Click "view failing rows" → log viewer
with `outcome=schema_fail` preselected.

**Panel 3 — Cost per day by model (stacked bars).**
Mini in teal, 4o in amber. Baseline ~$0.02/day. Days 11–13 roughly
double (to $0.035, $0.026, $0.053) — the mini line does most of the
lifting because it's where most traffic is. Latency and quality are
fine in the same window. Without the cost panel the verbose-mode
rollout would have been invisible until the end-of-month bill.

**Panel 4 — Guardrail trips per day (stacked bars).**
`blocked_pii` + `blocked_toxic`. Flat at zero for the first 13 days,
then 68 `blocked_pii` on day 13. This is the Slide-20 event — the
output-side PII guardrail firing when real user PII started flowing
through tickets.

**Panel 5 — Schema-validation fail rate per 4-h bucket (wide).**
The most precise panel. Zero almost everywhere; five adjacent
4-h buckets on day 3 shoot to 52%–92% fail rate; back to zero from
day 4. A dashed amber line marks a 2% alert threshold. Click
"view schema fails (v3)" → 153 rows of v3-prompt failures.

## Things worth pointing at during lecture

- **Same file, five reductions.** Every panel on the dashboard is a
  one-screen JavaScript reduction over `llm_calls.ndjson`. The same
  lesson as Demo 2 — the value of centralization is that aggregates
  become cheap. What you're paying a vendor for is retention, scale,
  and access control, not the view.

- **Log the prompt. Log the completion.** `log_viewer.html` makes
  the argument physical: without the full prompt text and full
  completion text on the row, you would have no way to answer the
  question *why did v3 break?* Tokens and latency are not enough.
  This is where the privacy thread from Slide 11 gets its teeth —
  you are *choosing* to keep the raw text because debugging requires
  it, and then you owe the reader of that log something about access
  control and redaction. Slide 20 picks up exactly this thread.

- **Three outcome families, three dashboard homes.** Tease the
  distinction before students see the panels. A good dashboard for
  an LLM service needs to separate:
  - *structural* failures (the JSON didn't parse — probably a prompt
    regression),
  - *transport* failures (timeout / 5xx — probably a vendor incident),
  - *content* failures (guardrail block — probably a data shift at
    the input or a hole in the prompt).
  All three produce a log row with `outcome != "ok"`; all three
  aggregate to different-shaped curves; conflating them hides which
  incident is which.

- **The cost panel is a monitoring panel.** Undergrads tend to file
  cost under "ops" or "finance." In LLM systems cost is a
  first-class *signal* about what the system is doing. A prompt that
  got more verbose, a router that started escalating to the big
  model too eagerly, a retry loop that doesn't terminate — all three
  show up on cost first and on quality never.

- **Drill-down is the feature.** Every panel's title has a small
  "view rows →" tag that deep-links to the log viewer with the right
  filter pre-filled. Demonstrate one round trip live: *spike on the
  schema panel → click → 155 rows → expand one → read the prompt and
  the broken completion.* That's the motion the dashboard exists to
  enable.

- **The URL as query.** The deep-link trick is worth naming —
  `log_viewer.html` reads its filters from `window.location.search`
  on load. This is the cheapest way to turn a dashboard panel into a
  drill-down target, and it's the same pattern every real
  observability tool uses (Datadog, Grafana, Splunk). No server, no
  state, no auth handoff.

## What's not here

- **No tracing.** Every row is flat — one call, one JSON object. As
  soon as a call adds context (RAG), tool calls, or sub-agent
  hand-offs the flat shape starts lying to you about causality.
  That's Stage B, starting at Slide 23 and shown in Demo 5.
- **No retry bookkeeping.** The `schema_fail` rows here die at the
  first parse failure. A real system would attempt one bounded retry
  with the validation error appended to the prompt ("retry-with-repair",
  Slide 21) and only log `schema_fail` on the final give-up. Out of
  scope for the teaching beat.
- **No LLM-as-judge panel.** Rubric-based correctness sampling is
  called out on Slide 19 and shown in the weekly-report demo later
  in the lesson; this demo deliberately stops at the cheap
  structural/content checks.
- **No real model calls.** `gen_calls.py` is a pure simulator — no
  network, no API key, no tokens counted at the vendor. The
  completion strings are templated; the failure modes are mechanical.
  That's intentional — the dashboard is what we're teaching, not
  prompt-engineering.

## Bridge to the next section

Section 04 opens on the first thing this demo can't show: *which
steps led to which*. The moment the call becomes a loop — the model
retrieves a chunk, calls a tool, reasons again — a flat NDJSON row
stops being enough. Demo 5 picks up from there, with OpenTelemetry
spans and a trace viewer. Same rows-in-a-file mental model, with
parent-child pointers added.
