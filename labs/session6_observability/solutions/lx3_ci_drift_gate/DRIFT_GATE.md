# DRIFT_GATE.md · Why count-above-threshold, not max

## Rule

```
FAIL if >= 5 feature columns have a two-sample KS statistic
         above 0.25 against the training reference.
PASS otherwise.
```

With `n=200` in the production batch and a 64-column feature matrix,
this rule discriminates the three regimes cleanly:

| batch           | columns over KS=0.25 | verdict |
|-----------------|---------------------:|:--------|
| healthy batch   |                  0–2 | PASS    |
| shipped slice   |                    1 | PASS    |
| broken batch    |                   64 | FAIL    |

## Candidates we considered and rejected

- **`max(ks) > 0.35` (single-column max).** Passes the shipped data
  but with only ~0.03 margin. Across 20 fresh healthy-batch seeds
  the column-wise max KS ranged 0.21–0.32. One noisy reseed would
  trip it. Count-above-threshold is more robust because the noise
  has to conspire across *many* columns at once.

- **Bonferroni-corrected per-column threshold at α = 0.05 / 64 ≈
  0.148.** With n=200 this flags ~15 columns on clean data — we
  measured the finite-sample CDF jitter of a small batch against
  a large reference, not drift. Bonferroni is for multiple
  hypothesis testing, not for distribution-shift gating.

- **Mean KS across all columns exceeds X.** One extremely-drifted
  column is diluted by 63 stable ones. Fails the "one feature went
  off a cliff" case.

## Aggregation rule

Count, not max. Rationale: real drift tends to affect many features
simultaneously (a pipeline bug, a schema change, an upstream
distribution shift). Healthy noise tends to affect one feature at a
time. Counting exploits that asymmetry.

## Per-feature threshold (0.25)

This is roughly the 99th-percentile KS we see between two size-200
samples drawn from the same distribution, measured empirically on
64-column gaussian data. Below 0.25 is noise; above 0.25 deserves
attention.

## Stderr output

```
PASS  max_ks=0.284  n_features_over(0.25)=1
FAIL  max_ks=0.751  n_features_over(0.25)=64  worst=col_17  ks=0.751
```

`max_ks` gives the on-call severity of the worst column. The count
is the actual gating signal. `worst` names the column that moved
most — usually the first thing the on-call wants to look at.

## CI integration

Wire this into the deploy pipeline between train and ship:

```
train → compute reference stats → hold out X_val for CI check →
drift-gate X_val against training stats → if PASS, package & ship;
if FAIL, block the deploy and page model-on-call
```

The gate is fast (no scipy, no bootstrap) and deterministic — same
`X_ref` and `X_new` always give the same verdict. The cost of a
false negative is a silently-drifted model in production; the cost
of a false positive is a blocked deploy that takes five minutes of
on-call time to clear. With our margins, the false-positive rate
against fresh healthy batches is zero and the false-negative rate
against the broken batch is zero. That's the bar worth shipping at.
