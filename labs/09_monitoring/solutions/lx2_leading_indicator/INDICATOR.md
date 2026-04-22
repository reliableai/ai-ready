# INDICATOR.md · Leading signal for the 14:00 `/checkout` incident

**Signal:** `/checkout` p99 latency (ms), sampled in a 1-minute rolling
window.

## Why it leads the error rate

Between 13:50 and 13:55, `/checkout` p50 and p95 are close to baseline
but the p99 tail doubles — the slowest 1% of checkouts are already
hitting the upstream timeout ceiling. This is the classical
backed-up-pool failure curve: a downstream dependency slows down, the
service's connection pool fills up, the slowest requests start
timing out at the client's read limit *before* the pool is actually
exhausted. Once the pool saturates (14:00), every request is slow —
and the TCP-level failure rate catches up to what the tail already
knew. The lead time is the gap between "1% of users feel it" and
"50% of users feel it". On this data, that's ~5 minutes.

Mechanically: the p99 moves because the pool's tail behaviour is
dominated by whichever request happens to grab the last available
slot. The error rate moves only when *the whole pool* is saturated.
p99 is downstream-aware; error rate is exhaustion-aware.

## Alert rule

> Alert when `/checkout` p99 latency exceeds 1200 ms for 2 consecutive
> minutes, evaluated every 1 minute.

The 1200 ms threshold sits above the afternoon daytime baseline
(~650–900 ms p99 for `/checkout`) and comfortably below the 13:55
trigger value (~2400 ms p99). The 2-minute hold prevents a single
noisy minute from paging.

## Lead time

| marker                                  | time  |
|-----------------------------------------|-------|
| `/checkout` p99 first crosses 1200 ms   | 13:55 |
| `/checkout` error rate first crosses 5% | 14:00 |
| **Lead time**                           | **5 min** |

A reasonable global error-rate alert (`error_rate > 5% for 2 min` on
the combined endpoint stream) would have fired at 14:01. Our p99
panel would have paged at 13:56.
