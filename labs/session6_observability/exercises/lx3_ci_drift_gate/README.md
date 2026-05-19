# LX-3 · The CI gate that would have caught it

Pairs with [Demo 3](../../demos/3_classical_ml_dashboard/README.md). ~35 minutes.

## Background

Look at Demo 3's dashboard. On day 12, two training jobs fail with
`SchemaMismatch` — the upstream feature job stopped emitting `pixel_63`.
That's the easy case: the training code raises `KeyError`, a human
notices. Red tiles, drawer open, done.

Now look at the accuracy panel. From day 12 onward, production accuracy
collapses from ~0.98 to ~0.70 and stays there. That is the **same
upstream event**, hitting the **serving** pipeline through a different
code path. Serving didn't crash — the column shape was fine — it just
started producing nonsense features. The model kept happily predicting
on them; latency stayed green; the SLO dashboard showed nothing. 48
hours of bad predictions went out the door before the quality panel had
enough labels to flag the drop.

A *statistical* assertion would have caught this. Not `assert
column_exists`, but `assert this-batch-looks-like-training`. That's the
Slide-15 idea shifted one layer upstream: same `assert value >=
threshold` shape, but the value is a distance between two
*distributions*, not a single number.

## Task

Write a CI-style script `check_drift.py` that:

1. Loads a *reference* distribution `X_train.npy` (what the model was
   fit on — shipped with the model as part of the training artifact).
2. Loads a *current* production feature batch (`X_prod_*.npy`).
3. Runs a two-sample Kolmogorov-Smirnov test per feature column.
4. Aggregates across the 64 features and decides: **pass or fail**.
5. Exits 0 on pass, 1 on fail. Prints a one-line summary to stderr.

The gate must:

- PASS on `X_prod_healthy.npy` (a random production slice from day 5,
  before the break).
- FAIL on `X_prod_broken.npy` (a random production slice from day 13,
  after the intensity-doubling bug shipped).

## Rules

1. **numpy only (scipy optional).** The starter ships with a 5-line
   `ks_2samp` written in numpy — same return value as
   `scipy.stats.ks_2samp(a, b).statistic`. Use it as-is, replace it with
   the scipy version if you have it, or write your own. No plotting.
2. **Justify your threshold.** A raw KS statistic lives in [0, 1]. For
   n = 200 vs n = 1800 under the null, 95% of runs stay under ~0.13. Pick
   a threshold that comfortably clears the baseline and comfortably
   catches the break. Write the reasoning into `DRIFT_GATE.md`.
3. **Handle the multiple-comparisons problem.** 64 independent tests at
   α = 0.05 gives you ~3 false positives per clean run. Either correct
   (Bonferroni, Benjamini-Hochberg) or use the KS statistic directly
   and set a threshold that's robust to running 64 of them. State which
   you did and why.
4. **One line of stderr on both paths.** Parseable by shell. Something
   like:

   ```
   PASS  max_ks=0.072  n_features_over=0
   FAIL  max_ks=0.712  n_features_over=64  worst=col_17  ks=0.712  p=3e-42
   ```

## How to run

```bash
# Generate the three arrays (once):
python gen_data.py

# Pass case:
python check_drift.py X_train.npy X_prod_healthy.npy
echo $?       # → 0

# Fail case:
python check_drift.py X_train.npy X_prod_broken.npy
echo $?       # → 1
```

## What to submit

- Your completed `check_drift.py`.
- A file `DRIFT_GATE.md` with:
  - Your chosen per-feature threshold, your aggregation rule, and a
    paragraph (≤ 200 words) defending both choices.
  - The exact stderr lines your script produced on the healthy and
    broken batches.
  - One sentence on how you'd integrate this into CI. Where does it
    run? What happens when it fires?

## Success criteria

1. `python check_drift.py X_train.npy X_prod_healthy.npy` exits 0.
2. `python check_drift.py X_train.npy X_prod_broken.npy` exits 1.
3. The stderr summary on both paths is machine-parseable and includes
   the aggregate statistic, not just PASS/FAIL.
4. The threshold is *justified*, not guessed — a reader should be able
   to reproduce your reasoning from `DRIFT_GATE.md` without needing the
   data.
5. The gate still passes if you re-run `gen_data.py` with a different
   seed (your threshold should be robust to sample-size noise, not
   overfit to the exact arrays shipped with the repo).

## Hints

- Start by printing the per-column KS statistic for both the healthy
  batch and the broken batch side by side. You'll see: healthy columns
  cluster under 0.12, broken columns cluster above 0.60. The threshold
  design space is that gap.
- The aggregation question is "what counts as drifted enough?" A single
  column above threshold? The worst column above a lower threshold?
  The fraction of columns over a threshold? Any of those works — pick
  one that reads well in the one-line summary.
- The Bonferroni trick is cheap: divide your per-test α by n_features.
  If α = 0.05 and n_features = 64, the per-test threshold is 0.05 / 64
  ≈ 0.00078. That's the correct way to keep the false-alarm rate under
  5% across the whole suite.

## Common pitfalls

- Testing only one column ("the mean of column 0 looks fine"). The
  whole point of drift detection is catching something you didn't
  pre-specify.
- Asserting on the p-value without any correction. With 64 tests, p <
  0.05 fires on clean data almost every time — noise, not drift.
- Choosing a threshold that passes the broken batch. Go look at the
  numbers; the gap is generous. If your threshold is too loose, you've
  built a placebo gate.
- Skipping the stderr summary. "Exit 1" is not a debugging aid — an
  on-call at 03:00 needs to see *which column moved* without rerunning
  anything.

## What this drills

LX-3 is the *statistical assertion* from Slide 15, promoted from a
one-liner to a production CI gate. The code is maybe 15 lines. The work
is:

- Picking a test that makes sense for the data (why KS and not χ²).
- Setting a threshold that's defensible under multiple comparisons.
- Reporting at a resolution that's useful when it fires.

If your `DRIFT_GATE.md` reads like a short postmortem rather than a lab
report, you've done it right — the Demo 3 SchemaMismatch incident is
the counterfactual your gate is meant to have prevented.

## What's out of scope

- Retraining. The point of the gate is to *stop the deploy*, not to fix
  the model.
- Feature-by-feature remediation. When the gate fires, a human looks at
  the worst column. That's the debugging workflow; it isn't the gate's
  job.
- Continuous drift monitoring in production. This gate runs on a batch,
  in CI, before a deploy ships. The production-side version of the
  same check — sliding-window KS against training — is a different
  exercise (and a different panel on the dashboard).
