# DECISION MEMO · arm B (gpt-4o) vs arm A (gpt-4o-mini)

**DRI:** <your name>
**Window:** 7 days, n ≈ 800 calls, 50/50 split

## Findings

<One paragraph each on the four metrics. Each paragraph should
contain: the point estimates for both arms, the 95% CIs, the
direction of the delta, and whether the CIs are separated. Keep
each paragraph to ~3 sentences.>

### Schema-fail rate

<...>

### PII-block rate

<...>

### Latency p50

<...>

### Cost per call

<...>

## Trade-off

<One paragraph. Which metric's result did you weight most heavily
and why? What's the cost (in dollars, ms, or user-visible
regressions) of the winning arm losing on another metric? If there
were additional data you'd want before shipping, name it and why.>

## Recommendation

<One short paragraph. Pick ONE of:
  * **Ship B fully.** (Rare — you need wins on most metrics and no
    severe regressions.)
  * **Ship B on a segment.** (E.g. only urgency ≥ 7 tickets, or
    only when the prompt output includes a JSON schema validator
    failure on the first try.)
  * **Don't ship B.** (Clear regression, OR ambiguous wins that
    don't justify the cost.)
  * **Extend the experiment.** (CIs wide enough that the decision
    hinges on not-yet-collected data.)

Whichever option you pick, name the *specific metric and threshold*
that would flip your recommendation.>
