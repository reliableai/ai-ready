"""
LX-3 reference solution — CI gate against feature drift.

Gate rule:

    FAIL if >= MIN_FEATURES_OVER feature columns have a two-sample KS
    statistic above PER_FEATURE_THRESHOLD against the training reference.
    PASS otherwise.

    PER_FEATURE_THRESHOLD = 0.25     # per-column KS distance
    MIN_FEATURES_OVER     = 5        # how many columns must trip

Why this rule (vs. other candidates we considered — see DRIFT_GATE.md for
the write-up):

  * `max(ks) > 0.35` (single-column max rule) passes the shipped data
    but has only ~0.03 margin across seeds (max KS across 20 fresh
    healthy-batch seeds ranged 0.21–0.32). One noisy reseed breaks it.
  * Bonferroni-corrected per-column threshold at alpha=0.05/64 is
    ~0.148. With n=200 that flags ~15 columns on clean data — it's
    detecting the finite-sample noise of a small batch vs a large
    reference, not drift.
  * The count-above-threshold rule splits the three regimes cleanly:
      healthy batches:  0–2 columns over 0.25
      broken batch:     64 columns over 0.25
    A threshold of 5 sits comfortably between the two. A fresh seed
    would have to be *three standard deviations* off before it tripped.

How to read the stderr line:

    PASS  max_ks=0.284  n_features_over(0.25)=1
    FAIL  max_ks=0.751  n_features_over(0.25)=64  worst=col_17  ks=0.751

`max_ks` tells an on-call how severe the worst column is. The count is
the actual gating signal. `worst` names the column that moved most —
usually the first thing the on-call wants to look at.
"""

import sys

import numpy as np


PER_FEATURE_THRESHOLD = 0.25
MIN_FEATURES_OVER = 5


def ks_2samp(a: np.ndarray, b: np.ndarray) -> float:
    """Two-sample KS statistic — max vertical gap between empirical CDFs.
    Equivalent to scipy.stats.ks_2samp(a, b).statistic."""
    a = np.sort(a)
    b = np.sort(b)
    all_x = np.concatenate([a, b])
    cdf_a = np.searchsorted(a, all_x, side="right") / len(a)
    cdf_b = np.searchsorted(b, all_x, side="right") / len(b)
    return float(np.abs(cdf_a - cdf_b).max())


def check_drift(X_ref: np.ndarray, X_new: np.ndarray) -> tuple[bool, str]:
    ks = np.array([ks_2samp(X_ref[:, j], X_new[:, j]) for j in range(X_ref.shape[1])])
    n_over = int((ks > PER_FEATURE_THRESHOLD).sum())
    worst_j = int(np.argmax(ks))
    max_ks = float(ks.max())

    passes = n_over < MIN_FEATURES_OVER
    verdict = "PASS" if passes else "FAIL"

    if passes:
        summary = (
            f"{verdict}  max_ks={max_ks:.3f}  "
            f"n_features_over({PER_FEATURE_THRESHOLD})={n_over}"
        )
    else:
        summary = (
            f"{verdict}  max_ks={max_ks:.3f}  "
            f"n_features_over({PER_FEATURE_THRESHOLD})={n_over}  "
            f"worst=col_{worst_j}  ks={ks[worst_j]:.3f}"
        )
    return passes, summary


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: solution.py <ref.npy> <new.npy>", file=sys.stderr)
        return 2
    X_ref = np.load(sys.argv[1])
    X_new = np.load(sys.argv[2])
    if X_ref.shape[1] != X_new.shape[1]:
        print(f"FAIL  schema mismatch: ref has {X_ref.shape[1]} features, "
              f"new has {X_new.shape[1]}", file=sys.stderr)
        return 1

    passes, summary = check_drift(X_ref, X_new)
    print(summary, file=sys.stderr)
    return 0 if passes else 1


if __name__ == "__main__":
    sys.exit(main())
