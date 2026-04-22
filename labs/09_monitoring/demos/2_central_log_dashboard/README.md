# Demo 2 — Central log dashboard (Splunk-like)

Supports **Slides 9–10** of L10 (Section 01 — centralized logging at scale). Pairs with **lab exercise LX-2**.

## Purpose

Show what changes the moment log events are shipped to one place and
aggregated. Every chart you've ever seen on a production dashboard — rate,
error rate, latency percentiles — is a reduction over the same JSON rows
Demo 1 produced. Splunk, Datadog, Grafana Loki, ELK: they sell scale,
retention, and access control, not "the dashboard part." The dashboard
part is this demo.

## Learning outcome

After running and reading this demo, you should be able to:

1. Point to the RED triad (Rate, Errors, Duration) on a real dashboard and
   name the aggregation each panel performs.
2. Use the search box to drill from a summary signal (a spike on the error
   panel) into the individual log rows that produced it.
3. Explain, without looking, why the structured JSON shape from Demo 1 is
   what makes this dashboard buildable in a single HTML file.
4. Recognise a *leading indicator* on the latency panel — a signal that
   moves before the error-rate panel does. (That's the target for LX-2.)
5. State what this dashboard still cannot tell you: *whether the output was
   correct*. That axis doesn't exist yet — it arrives in Section 02.

## How to run

```bash
python gen_logs.py                    # writes logs.ndjson and logs.js
open dashboard.html                   # or double-click it
```

`gen_logs.py` is deterministic (seeded). Two files are produced:

- `logs.ndjson` — the canonical log file. One JSON object per line. This is
  what a service would ship to Splunk / Loki / S3. Grep it, pipe it, load
  it in pandas in two lines:
  ```bash
  grep '"status_code": 5' logs.ndjson | head
  python -c "import json; rows=[json.loads(l) for l in open('logs.ndjson')]; print(len(rows))"
  ```
- `logs.js` — same rows wrapped as a JS array so `dashboard.html` can load
  them via `<script src>` from `file://` (browsers block `fetch()` there).

## What you should see

`gen_logs.py` simulates 24 hours of traffic against a toy SaaS service with
four endpoints:

```
GET  /feed      — 60% of traffic, p50 ~25ms,  0.2% base error rate
POST /login     — 10% of traffic, p50 ~80ms,  1.0% base error rate
POST /checkout  — 20% of traffic, p50 ~200ms, 0.5% base error rate
GET  /profile   — 10% of traffic, p50 ~30ms,  0.1% base error rate
```

A diurnal curve shapes the rate (quiet at night, peak near 14:00). Then a
25-minute incident is injected on `/checkout`:

```
13:50 – 14:00   latency creep    p95 climbs from ~400ms → ~1300ms   errors still 0%
14:00 – 14:15   full incident    error rate 20%                     p95 hits timeouts (5 s)
14:15 – 14:30   recovery         errors + latency taper back        toward baseline
```

Open `dashboard.html`, let it load (~2.5 MB of JSON in the browser), and
look for three things:

- **Rate panel:** smooth stacked curve with a peak in the afternoon. No
  visible incident — rate is the wrong axis.
- **Error panel:** a sharp vertical spike on `/checkout` at 14:00.
- **Latency panel (p95 dashed):** `/checkout` p95 is visibly elevated in
  the 13:55–14:00 bucket (p95 ≈ 1.3 s) — **five minutes before the error
  spike.** The error panel flags the incident at 14:00; the latency panel
  would have flagged it at 13:55. That five-minute gap is the
  leading-indicator story LX-2 is built around.

Then type in the search box:

```
500        → just the error rows
/checkout  → just the checkout rows
14:0       → everything in the 14:00 hour
```

The table shows the first 200 matching rows.

## Things worth pointing at during lecture

- **Same file, different reduction.** Every panel is computed in about a
  dozen lines of JavaScript. Rate = counts per bucket ÷ bucket size. Error
  rate = count-where-status≥500 ÷ count. Latency p50/p95 = sort-and-index.
  Nothing fancier than that.
- **Drill-down round-trip.** Click the spike on the error panel, search
  `500 /checkout`, inspect the individual rows — the raw `request_id`,
  `latency_ms`, `user_hash` that caused the aggregate. Summary ↔ raw is the
  move the dashboard exists to enable.
- **Centralization makes privacy non-optional.** Everyone on the team can
  now query every row. That's the bridge into Slides 11–12 — if those rows
  contain raw PII, the dashboard becomes a liability.
- **The quality axis isn't here.** All three panels measure *is the service
  up, fast, not erroring*. None of them measure *is the output correct* —
  for a SaaS endpoint there's no notion of a "correct" response to compare
  against. That axis only appears once the system is making predictions
  you could be right or wrong about. Next slide (Slide 11) picks up the
  privacy thread; Section 02 opens the quality one.

## Why no server is required

The dashboard reads the data via `<script src="logs.js">` rather than
`fetch("logs.ndjson")`. Browsers block `fetch()` from `file://` for
security reasons; a `<script>` tag still works. The cost is that we emit
the same rows twice — once in the canonical `.ndjson` (what a real service
ships) and once wrapped in `.js` (what the file-loaded dashboard can eat).
In production you'd fetch aggregates from a metrics backend; for this demo
two files on disk is simpler and honest about what the dashboard is doing.

## What's not here

- No alerting. Alerts are assertions on top of these panels — a threshold +
  a window + a notification target. Covered in Slide 7 vocabulary; no extra
  code needed to discuss.
- No cross-service traces. The request-id field is present and unique per
  row, but everything fits in one service. Section 03 is where traces
  become load-bearing.
- No authentication / retention / cost controls — the three things Splunk
  et al. actually charge for. Out of scope for a one-file demo.
