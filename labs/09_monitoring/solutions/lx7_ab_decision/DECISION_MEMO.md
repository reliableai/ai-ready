# DECISION MEMO · arm B (gpt-4o) vs arm A (gpt-4o-mini)

**DRI:** reference
**Window:** 7 days, n = 800 (A=374, B=426), 50/50 split

## Findings

**Schema-fail rate.** A was 5.61% (95% CI [3.70%, 8.43%]); B was
3.52% (95% CI [2.15%, 5.73%]). The point estimate favours B by
~2 percentage points, but the CIs overlap in [3.70%, 5.73%] — at
this sample size we cannot distinguish the arms. This is the
primary metric we hoped B would win; the data says "maybe, not sure".

**PII-block rate.** A was 1.07% (CI [0.42%, 2.72%]); B was 2.58%
(CI [1.45%, 4.56%]). Point estimates tilt toward B having *more*
blocks, but the CIs overlap in [1.45%, 2.72%]. Call it a tie,
possibly a small regression. The 11 B-arm blocks vs 4 A-arm blocks
is small-N volatility, not a finding.

**Latency p50.** A was 368 ms (CI [357, 384]); B was 455 ms (CI
[438, 471]). CIs fully disjoint. B is ~87 ms slower at the median,
and this is a real effect we will see in production. For our p95
SLO of 800 ms it's not fatal, but it cuts our headroom.

**Cost per call.** A averaged $0.000015 (CI tight); B averaged
$0.000260 (CI tight). ~17× more expensive. CIs disjoint by a
huge margin.

## Trade-off

We have no proven win on quality (schema fails: CIs overlap; PII:
CIs overlap), a clear regression on latency (+87 ms median), and a
17× cost regression. The metric we were trying to move (schema
fails) is precisely the one the current sample can't settle. Until
we have evidence of a real quality lift, cost and latency
regressions aren't justified.

## Recommendation

**Extend the experiment** to n ≈ 4,000 per arm to tighten the
schema-fail CI from ±2 pp to ±1 pp. **Flip-condition:** if the
larger sample confirms a ≥ 2 pp reduction in schema fails *with
separated CIs*, revisit and consider shipping B on urgency ≥ 8
tickets only (where 17× cost is acceptable in exchange for fewer
retries). If the gap closes at 4k, don't ship — the current
evidence is consistent with "no quality difference" and no model
we charge 17× more for earns its keep that way.
