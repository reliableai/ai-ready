"""
LX-7 · A/B analysis with a decision memo.

You're the DRI for the triage agent. Product wants to know: should
we switch from gpt-4o-mini (arm A, current) to gpt-4o (arm B,
candidate)? You have 800 calls across 7 days, 50/50 split, in
`ab_calls.ndjson`. Your job:

  1. Implement `compare_arms(calls)` below. It should return a dict
     of per-metric comparisons — each metric with both arms' point
     estimate, 95% CI, and a boolean `separated` flag (CIs disjoint).
  2. Run `python starter.py`. It prints a table. Eyeball it.
  3. Write `DECISION_MEMO.md` — ≤ 300 words — with your
     recommendation.

The helpers for Wilson-interval proportions and bootstrap means /
medians are already written for you. What you have to write is the
*comparison* — deciding which metric uses which method, gathering
them into a consistent shape, and interpreting what "95% CI
disjoint" buys you.

Four metrics to compare, in order of product priority:

  (1) schema_fail rate         (proportion, lower = better)
  (2) pii-block rate           (proportion, lower = better)
  (3) latency p50              (continuous, lower = better)
  (4) mean cost per call       (continuous, lower = better)

Decision-memo rubric (see README):
  * One paragraph per metric — point estimate, CI, delta, CI overlap.
  * One paragraph on trade-offs across metrics.
  * A recommendation that names: ship / don't ship / ship on a
    segment. Back it with the numbers, not with vibes.

Run:  python starter.py
"""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict


# ---------------------------------------------------------------------------
# Helpers — provided. You don't need to edit these.
# ---------------------------------------------------------------------------

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% CI for a proportion. Returns (lo, hi)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_ci(values: list[float], stat, n: int = 1000,
                 seed: int = 2026) -> tuple[float, float, float]:
    """Bootstrap 95% CI for `stat(values)`. Returns (point, lo, hi)."""
    if not values:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    resamples = []
    N = len(values)
    for _ in range(n):
        sample = [values[rng.randrange(N)] for _ in range(N)]
        resamples.append(stat(sample))
    resamples.sort()
    lo = resamples[int(n * 0.025)]
    hi = resamples[int(n * 0.975)]
    return (stat(values), lo, hi)


def median(vals: list[float]) -> float:
    if not vals: return 0.0
    s = sorted(vals)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


# ---------------------------------------------------------------------------
# The function you implement.
# ---------------------------------------------------------------------------

def compare_arms(calls: list[dict]) -> dict:
    """Build a comparison dict of the form:

        {
          "schema_fail": {
            "kind": "proportion",
            "A": {"point": 0.06, "lo": 0.037, "hi": 0.085, "n": 374, "k": 21},
            "B": {"point": 0.035, "lo": 0.021, "hi": 0.057, "n": 426, "k": 15},
            "separated": False,
          },
          "pii_block": {...},
          "latency_p50": {"kind": "continuous", "A": {...}, "B": {...}, "separated": ...},
          "cost_mean":   {...},
        }

    Use `wilson` for proportion metrics (schema_fail, pii_block).
    Use `bootstrap_ci` with `median` for latency and `mean` for cost.
    Use the helpers above — don't re-implement.

    `separated` is True if the 95% CIs don't overlap.
    """
    # TODO: implement.
    raise NotImplementedError("implement compare_arms()")


# ---------------------------------------------------------------------------
# Reporting — provided.
# ---------------------------------------------------------------------------

def load_calls(path: str = "ab_calls.ndjson") -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f]


def print_table(cmp: dict) -> None:
    headers = ["metric", "arm", "point", "95% CI", "n", "separated?"]
    rows = []
    for metric, info in cmp.items():
        for arm in ("A", "B"):
            d = info[arm]
            point = d["point"]
            if info["kind"] == "proportion":
                val = f"{point * 100:.2f}%"
                ci  = f"[{d['lo'] * 100:.2f}%, {d['hi'] * 100:.2f}%]"
                n_s = f"{d['n']} (k={d['k']})"
            elif metric == "cost_mean":
                val = f"${point:.6f}"
                ci  = f"[${d['lo']:.6f}, ${d['hi']:.6f}]"
                n_s = str(d["n"])
            else:
                val = f"{point:.1f} ms"
                ci  = f"[{d['lo']:.1f}, {d['hi']:.1f}]"
                n_s = str(d["n"])
            sep = "yes" if info["separated"] else "no"
            rows.append([metric if arm == "A" else "", arm, val, ci, n_s,
                         sep if arm == "A" else ""])

    col_widths = [max(len(str(r[c])) for r in [headers] + rows)
                  for c in range(len(headers))]
    def fmt(row):
        return "  ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(row))
    print(fmt(headers))
    print(fmt(["-" * w for w in col_widths]))
    for r in rows:
        print(fmt(r))


def main() -> None:
    calls = load_calls()
    try:
        cmp = compare_arms(calls)
    except NotImplementedError:
        print("compare_arms() isn't implemented yet — get to it.")
        return
    print_table(cmp)
    print("\nNow write DECISION_MEMO.md (≤ 300 words).")
    print("Rubric is in README.md; table above has the numbers you need.")


if __name__ == "__main__":
    main()
