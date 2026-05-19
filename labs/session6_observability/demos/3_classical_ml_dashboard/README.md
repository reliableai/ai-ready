# Demo 3 — Classical-ML monitoring dashboard

Supports **Slides 14–16** of L10 (Section 02 — Classical ML). Pairs with **lab exercise LX-3**.

## Purpose

Show the three things classical-ML monitoring adds on top of the SaaS
dashboard from Demo 2 — *training-job health, serving latency, quality* —
and show that the first two look exactly like any other service while the
third is where the new axis opens up. This demo is the pivot between
Section 01 (logs, RED, SLOs) and Section 03 (LLMs). If a student can look
at this one dashboard and point at *which panel would have caught which
kind of failure*, they have the shape of everything that follows.

## Learning outcome

After running and reading this demo, you should be able to:

1. Name the three panels of classical-ML monitoring without looking
   (training fleet, serving latency, rolling quality) and say which axis
   each one is watching.
2. Recognise the six failure modes every classical-ML team has shipped at
   least once — OOM, NaN loss, SchemaMismatch, DataLoaderDeadlock, Hung,
   Runaway — by clicking the corresponding red tile and reading the
   error-log drawer.
3. Explain why the serving-latency panel is nearly flat here even though
   the model's accuracy is cratering: *the service is up; the model is
   wrong*. That mismatch is the entire argument for Slide 15's
   statistical assertion.
4. Point at the drift window on the accuracy panel and state which
   regime is which: a gentle *creeping* dip on days 8–10, a brief
   recovery, then a hard *broken* drop from day 12 onward when a feature
   pipeline changed units.
5. State the Slide-13 twist: the holdout accuracy is green (0.98) while
   production accuracy is red (~0.70). Same assertion shape as Slide 5's
   `assert x > 0` — but now the value being asserted on is a summary
   over a dataset, and it passes or fails depending on *which dataset*.

## How to run

```bash
python train_and_monitor.py              # writes ndjson + data.js
open dashboard.html                      # or double-click it
```

`train_and_monitor.py` is deterministic (seed=42 + frozen NOW =
`2026-04-27T18:00`). Running it does three things:

1. Trains a real nearest-centroid classifier on a synthetic 10-class
   digits-like dataset. Takes well under a second. The holdout accuracy
   it reports (~0.98) is the live number that appears as the most recent
   SUCCEEDED tile in the fleet board.
2. Simulates a fleet of 36 training runs across the last 14 days, with
   six kinds of failure hand-placed at specific day offsets so the story
   is reproducible.
3. Serves 2000 synthetic prediction calls through the real classifier,
   injecting drift on days 8–10 and a hard feature-pipeline break on
   days 12–14. Labels arrive with a 6-hour delay, so the right edge of
   the accuracy panel is intentionally empty.

Four files are produced:

- `train_runs.ndjson` — one JSON per line, one row per training run.
  Schema: `job_id`, `model`, `dataset`, `started_at`,
  `last_heartbeat_at`, `finished_at`, `status`, `duration_s`,
  `holdout_acc`, `exit_code`.
- `train_errors.ndjson` — one row per run with `error_kind` and a
  short `tail_log` — what the last few log lines of that run looked
  like. For SUCCEEDED runs `error_kind` is null.
- `predictions.ndjson` — one row per served prediction. Schema:
  `ts`, `request_id`, `predicted_class`, `predicted_proba`,
  `latency_ms`, `true_label` (null until labels arrive), `regime`.
- `data.js` — the same three collections wrapped as
  `window.__DATA__` so `dashboard.html` can load them via
  `<script src>` from `file://` (same trick as Demo 2).

Each file is readable with nothing fancier than `grep` and one line of
Python:

```bash
grep '"status": "FAILED"' train_runs.ndjson
python -c "import json; rows=[json.loads(l) for l in open('predictions.ndjson')]; print(len(rows), 'predictions')"
```

## What you should see

Four panels, reading top to bottom:

**Panel 1 — Training fleet (tile grid, 14 days).**
36 tiles in chronological order. Expect:

- A cluster of three red tiles on day 3 (OOM — someone rolled a bigger
  batch out too eagerly).
- A single red tile on day 6 (NaN loss — lr bump that didn't stick).
- A red on day 9 (DataLoaderDeadlock — worker 3 stuck on semaphore).
- Two reds on day 12 (SchemaMismatch — `pixel_63` disappeared from the
  upstream feature job; this is the same event that breaks production
  48 h later).
- An **amber** tile near day 13.4 (Runaway — still RUNNING, heartbeat
  fresh, but duration is already many multiples of the rolling median).
- An **amber** tile at the far right (Hung — still RUNNING, but the
  heartbeat hasn't advanced in 20+ minutes).
- Everything else green, including the very last SUCCEEDED run — the
  real nearest-centroid model that was trained one line earlier.

Click any tile. The drawer below shows `job_id`, `status`, timestamps,
`exit_code`, `error_kind`, and the last few log lines. The Hung vs
Runaway distinction lives entirely in the `last_heartbeat_at` field:
both are RUNNING, but Hung's heartbeat is 20+ minutes stale and
Runaway's is fresh.

**Panel 2 — Training duration with rolling median.**
Scatter of per-run wall-clock durations on a log y-axis, with a dashed
orange rolling-median line (window = 5 completed runs). The Runaway
point sits ~2 orders of magnitude above the line — which is how you'd
catch it before it ran your GPU bill into the ground. Green dots are
SUCCEEDED, red dots are FAILED. Failures tend to die early; the pattern
is visible.

**Panel 3 — Serving latency (p50 solid, p95 dashed), 4-hour buckets.**
Two lines that *barely move*. p50 sits around 7 ms, p95 around 12 ms,
nothing ever crosses the 15 ms SLO line. This panel is the point: the
*service* is fine. If you stopped here and declared the model healthy
you would be wrong, which is the setup for Panel 4.

**Panel 4 — Rolling accuracy on labelled traffic, 4-hour buckets.**
The narrative panel. Read it left to right:

- **Days 0–8, healthy:** accuracy lives around 0.95–1.0. Sample size
  varies by hour of day (off-hours have fewer labelled rows, so an
  occasional bucket dips).
- **Days 8–10, creeping (orange band):** feature intensities drift
  upward by 20%. Accuracy slips into the 0.90–0.95 zone. The 0.95
  threshold line starts getting crossed on the downside.
- **Days 10–12, healthy_pause (teal band):** a brief recovery — the
  drift paused. Confusing if you've already written an alert, which is
  part of the lesson.
- **Days 12+, broken (red band):** a feature pipeline started doubling
  intensities overnight. Accuracy craters to ~0.70. The 0.85 threshold
  gets crossed and stays crossed.
- **Right edge, empty:** labels haven't arrived yet for the last 6 hours
  of predictions. This "hole" is not a bug — it's what delayed-label
  monitoring actually looks like.

## Things worth pointing at during lecture

- **Three panels, three axes, one dashboard.** Panel 1 is *did the job
  run*. Panel 3 is *is the service fast*. Panel 4 is *is the model
  right*. Only Panel 4 is new compared to Demo 2. The rest is the same
  RED-triad story we already told.

- **Holdout green, production red (Slide 15's assertion).** The script
  prints both at the end:

  ```
  holdout accuracy     (from training): 0.9847
  production accuracy  (on ~1700 labelled requests): 0.8718
  ```

  The holdout number is what a CI gate would check. The production
  number is what users see. An assertion `assert acc >= 0.95` that
  passed in CI fails in production. This is the *statistical assertion*
  idea — same `assert x >= threshold` shape as Slide 5, but the `x` is
  now a summary over a dataset, and the dataset matters.

- **Hung vs Runaway vs Healthy-RUNNING — one field does all the work.**
  All three are `status: RUNNING`. The difference is in
  `last_heartbeat_at`: fresh heartbeat + long duration = Runaway (kill
  it before the bill spikes); stale heartbeat = Hung (the process is
  wedged). A dashboard that only rendered `status` would put these in
  the same bucket. Your on-call wants them in different buckets.

- **The same failure appears twice, 48 hours apart.** Day 12 shows two
  red SchemaMismatch tiles — the upstream feature job stopped emitting
  `pixel_63`. Day 12 onward shows production accuracy collapsing,
  because the same change shipped anyway via a different code path
  (the serving feature pipeline). This is the *pipeline drift*
  story: the training side caught it; the serving side didn't; a
  well-built dashboard would have let you notice that the two were
  related.

- **Four-hour buckets vs one-hour buckets.** The code uses 4-hour
  buckets on Panels 3 and 4. With one-hour buckets an off-hours window
  with two predictions can show 0% or 100% accuracy depending on one
  call. Bucket width is a *data* choice, not a visual one — aggregation
  over too few samples produces noise indistinguishable from a real
  incident. Students who've only seen production dashboards often
  haven't had to make this decision.

## The Slide-15 assertion, run two ways

The last thing `train_and_monitor.py` prints is the assertion from
Slide 15 evaluated against both numbers:

```
Slide-15 assertion, run against both:
  assert holdout    acc >= 0.85   →   PASS
  assert holdout    acc >= 0.95   →   PASS
  assert production acc >= 0.85   →   PASS    ← if threshold is loose enough
  assert production acc >= 0.95   →   FAIL    ← this is where the gap shows

  ← that is the Slide-13 point: CI gate green, reality red.
```

Instructors toggle that threshold live on Slide 15 — 0.85 passes both
sides, 0.95 splits them. That split is the hinge from "it compiles" to
"it's still right".

## What's not here

- **No retraining pipeline.** The "day 12 breaks production" story is
  visible; the fix (retrain with new feature schema, re-deploy) is out
  of scope. Covered in any MLOps track; not a monitoring-lesson
  responsibility.
- **No drift tests (K-S, PSI, χ²).** Those are LX-3's job — the
  exercise is to write a CI-style statistical assertion against the
  feature distribution that would have caught the SchemaMismatch event
  before it broke serving. This demo only shows the *outcome* that
  motivates the test.
- **No real classifier library.** We use a 20-line numpy
  nearest-centroid so the script has zero pip dependencies. The API
  matches sklearn's; swap it in if you want. The dashboard doesn't
  care which model produced the predictions.
- **No per-class accuracy.** The aggregate rolling-accuracy line is
  enough for the story. In production you'd want this sliced by class
  and by user segment — covered in the Slide-17 roadmap, not in this
  demo's code.

## Bridge to the next section

Section 03 opens with the move: *same dashboard shape, swap the quality
metric*. For an LLM call there's no `y_test` to compare against — the
"is this correct?" question turns into a rubric score from a judge
(human, another model, or both). Everything else on the dashboard
stays: the fleet board becomes a log of generation runs, the latency
panel still watches p50/p95, the accuracy panel becomes a rubric-pass
rate. That's Demo 4.
