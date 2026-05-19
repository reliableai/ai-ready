# LX-2 · Catch the incident earlier

Pairs with [Demo 2](../../demos/2_central_log_dashboard/README.md). ~30 minutes.

## Background

Open Demo 2's dashboard and study the `/checkout` incident at 14:00. The
error-rate panel flags it clearly — but by the time the error rate has
spiked, real users have already been seeing 500s for a full minute. The
latency panel, if you look carefully, shows `/checkout` p95 climbing
**five minutes earlier**, at 13:55, while the error rate is still at zero.

That five-minute head-start is what leading indicators buy you. An alert
on the latency signal would have paged the on-call before any user saw a
failed checkout.

## Task

Add one new panel to the dashboard that would have flagged the `/checkout`
incident **at 13:55 or earlier** — before the error-rate panel crossed a
reasonable threshold.

Rules:

1. **No new data source.** Read only from `logs.ndjson` / `logs.js`. The
   whole point is that a good leading indicator is already hiding in the
   same log file.
2. **One signal.** Pick something single-dimensional and justify in one
   paragraph why it *moves before* the error rate.
3. **A threshold.** Overlay a horizontal alert line on your panel. The
   threshold should sit above the baseline day-time value and below the
   level the signal hits at 13:55. Both conditions must hold on the
   provided data.
4. **A written alert rule.** State it the way you'd configure it in
   Splunk / Datadog:

   > *"Alert when `<signal>` exceeds `<threshold>` for `<window>`, evaluated every `<period>`."*

## How to run

Start from `starter.html` in this folder. It is a copy of Demo 2's
dashboard with a fourth panel slot wired up and a `leadingChart()` stub
ready for your code.

```bash
# From the demo folder next door, regenerate the data if you haven't:
cd ../../demos/2_central_log_dashboard && python gen_logs.py && cd -

# The starter expects ./logs.js alongside it. Easiest: symlink.
ln -sf ../../demos/2_central_log_dashboard/logs.js logs.js

open starter.html
```

## What to submit

- Your edited `starter.html` with the new panel working.
- A file `INDICATOR.md` with:
  - One paragraph (≤ 150 words) naming your signal and explaining *why*
    it leads the error rate. Cite something about how the system fails,
    not just "it looked earlier on the chart."
  - Your alert rule in the exact Splunk/Datadog shape above.
  - The timestamp at which your signal first crosses the threshold, and
    the timestamp at which the error-rate panel's `/checkout` line first
    crosses a *reasonable* threshold (you pick; justify). The difference
    is your lead time. Aim for ≥ 5 minutes.

## Success criteria

1. The new panel renders without errors and computes its signal from
   `logs.ndjson` alone.
2. The threshold line is visible on the chart.
3. On the provided data, the signal crosses threshold at least 5 minutes
   before any reasonable error-rate alert would fire.
4. The alert rule is stated precisely — threshold, window, evaluation
   period. A reader should be able to configure it in a real system
   without further questions.
5. `INDICATOR.md` gives a *mechanical* reason the signal leads — not just
   "the chart showed it earlier."

## Hints

- What happens to a service's latency when something slow but not yet
  broken starts happening upstream? (Thread pools, connection pools,
  queues — they fill up before they overflow.)
- p95 is not the only shape you can pull from the latency distribution.
  The tail often moves before the median.
- A *ratio* is sometimes more leading than a raw number. Current-window
  p95 divided by rolling-median p95 gives you a dimensionless "how
  unusual is this?" signal.
- If you're stuck, look at the `/checkout` numbers between 13:50 and
  14:00 in the dashboard's latency panel and ask: what changed, and when?

## Common pitfalls

- Choosing a signal that only distinguishes the incident *after* the
  error rate already spiked. That's lagging, not leading.
- Setting the threshold so low that it trips every afternoon peak, or so
  high that it only fires after errors are already visible. The margin
  between baseline and 13:55 value is your design space.
- Writing the alert rule without a window. `p95 > 800ms` sampled once is
  noisy; `p95 > 800ms for 2 consecutive minutes` is a rule.
- Forgetting to hide the indicator when `/checkout` isn't involved. A
  leading signal for one endpoint doesn't have to live on the same panel
  as the global RED view — it can be endpoint-specific.

## What this drills

LX-2 is a dashboard-designer exercise, not a coding exercise. The code is
ten lines; the work is **picking a signal, defending the choice, and
pinning down an alert rule that a real operator could live with.** If
your `INDICATOR.md` reads like a PM spec rather than a lab report, you've
done it right.

## What's out of scope

- **Multi-signal / composite alerts.** Real operators often combine
  two leading signals with an `AND` to cut false positives. One is
  enough here.
- **Dynamic thresholds.** Seasonality, day-of-week baselines, and
  per-endpoint auto-tuned bounds all exist in production alerting
  systems. Here the baseline is one weekday of synthetic data — pick
  a static threshold.
- **Alert fatigue modelling.** A real PM debate would weigh how often
  this alert fires *outside* 13:55. Stick to the one incident in the
  data.
