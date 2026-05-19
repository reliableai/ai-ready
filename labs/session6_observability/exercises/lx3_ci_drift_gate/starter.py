"""
LX-3 — CI gate against feature drift.

Your job is to fill in `check_drift()` below so that:

    python check_drift.py X_train.npy X_prod_healthy.npy   → exit 0, 'PASS'
    python check_drift.py X_train.npy X_prod_broken.npy    → exit 1, 'FAIL'

The gate should be *statistical*, not exact. Use a two-sample
Kolmogorov-Smirnov test — one per feature column — and reject when any
column's distribution has moved too far from the training reference.

Requirements:
  1. Pick a per-feature threshold. Justify it (comment + DRIFT_GATE.md).
  2. Aggregate over the 64 features somehow — max, count-over-threshold,
     Bonferroni-corrected p-value, etc. Your choice; justify it.
  3. Print a one-line summary to stderr on both paths:
       PASS  max_ks=0.07  n_features_over=0
       FAIL  max_ks=0.71  n_features_over=64  worst=col_17  ks=0.71
  4. Exit code 0 on pass, 1 on fail.

`ks_2samp` below is a numpy-only implementation of the two-sample KS
statistic. You can use it as-is, or replace it with
`scipy.stats.ks_2samp` if you have scipy installed — both return the
same number.

Run:  python check_drift.py X_train.npy X_prod_healthy.npy
      python check_drift.py X_train.npy X_prod_broken.npy
"""

import sys

import numpy as np


def ks_2samp(a: np.ndarray, b: np.ndarray) -> float:
    """Two-sample KS statistic — max vertical gap between empirical CDFs.
    Equivalent to scipy.stats.ks_2samp(a, b).statistic. Returns a value in
    [0, 1]; 0 means identical distributions, 1 means total separation."""
    a = np.sort(a)
    b = np.sort(b)
    all_x = np.concatenate([a, b])
    cdf_a = np.searchsorted(a, all_x, side="right") / len(a)
    cdf_b = np.searchsorted(b, all_x, side="right") / len(b)
    return float(np.abs(cdf_a - cdf_b).max())


def check_drift(X_ref: np.ndarray, X_new: np.ndarray) -> tuple[bool, str]:
    """Return (passes, one_line_summary). Edit this function.

    Hints:
      * ks_2samp(a, b) is in [0, 1]. Under the null (same distribution),
        for n=200 vs n=1800 it usually stays under ~0.13.
      * Under the broken regime, intensities are doubled, which shifts the
        entire column and pushes KS toward 1.0.
      * Pick a threshold that clears the baseline and catches the break.
      * You're doing 64 tests at once. Either use the KS statistic
        directly (robust to multiple comparisons if your threshold is
        chosen above the baseline max), or compute p-values and correct.
    """
    # TODO: fill in.
    raise NotImplementedError("implement check_drift()")


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: check_drift.py <ref.npy> <new.npy>", file=sys.stderr)
        return 2
    X_ref = np.load(sys.argv[1])
    X_new = np.load(sys.argv[2])
    if X_ref.shape[1] != X_new.shape[1]:
        # Schema mismatch — not drift, a hard error. In Demo 3 this is the
        # KeyError on pixel_63. A real CI gate would distinguish the two,
        # but for this exercise you can treat it as FAIL.
        print(f"FAIL  schema mismatch: ref has {X_ref.shape[1]} features, "
              f"new has {X_new.shape[1]}", file=sys.stderr)
        return 1

    passes, summary = check_drift(X_ref, X_new)
    print(summary, file=sys.stderr)
    return 0 if passes else 1


if __name__ == "__main__":
    sys.exit(main())
