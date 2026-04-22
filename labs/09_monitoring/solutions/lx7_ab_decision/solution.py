"""
LX-7 reference solution — Instructor only.

Reference implementation of `compare_arms` for the exercise in
`../../exercises/lx7_ab_decision/starter.py`. Copy `ab_calls.ndjson`
from the exercise folder first.

Run:  python solution.py
"""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict


def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_ci(values, stat, n=1000, seed=2026):
    if not values: return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    resamples = []
    N = len(values)
    for _ in range(n):
        sample = [values[rng.randrange(N)] for _ in range(N)]
        resamples.append(stat(sample))
    resamples.sort()
    return (stat(values), resamples[int(n * 0.025)], resamples[int(n * 0.975)])


def median(vals):
    if not vals: return 0.0
    s = sorted(vals); mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def mean(vals):
    return sum(vals) / len(vals) if vals else 0.0


def _sep(a, b) -> bool:
    """Two CIs are 'separated' when they don't overlap."""
    return a["hi"] < b["lo"] or b["hi"] < a["lo"]


def compare_arms(calls: list[dict]) -> dict:
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for c in calls:
        by_arm[c["arm"]].append(c)

    out = {}

    # --- proportion metrics -------------------------------------------
    for metric, matcher in [("schema_fail", lambda r: r["outcome"] == "schema_fail"),
                            ("pii_block",   lambda r: r["outcome"] == "blocked_pii")]:
        per = {}
        for arm in ("A", "B"):
            rows = by_arm[arm]
            k = sum(1 for r in rows if matcher(r))
            n = len(rows)
            lo, hi = wilson(k, n)
            per[arm] = {"point": k / n if n else 0.0, "lo": lo, "hi": hi,
                        "n": n, "k": k}
        out[metric] = {
            "kind": "proportion",
            **per,
            "separated": _sep(per["A"], per["B"]),
        }

    # --- continuous metrics -------------------------------------------
    for metric, field, stat in [("latency_p50", "latency_ms", median),
                                ("cost_mean",   "cost_usd",   mean)]:
        per = {}
        for arm in ("A", "B"):
            vals = [r[field] for r in by_arm[arm]]
            point, lo, hi = bootstrap_ci(vals, stat)
            per[arm] = {"point": point, "lo": lo, "hi": hi, "n": len(vals)}
        out[metric] = {
            "kind": "continuous",
            **per,
            "separated": _sep(per["A"], per["B"]),
        }

    return out


def load_calls(path="ab_calls.ndjson"):
    with open(path) as f:
        return [json.loads(line) for line in f]


def print_table(cmp: dict) -> None:
    headers = ["metric", "arm", "point", "95% CI", "n", "separated?"]
    rows = []
    for metric, info in cmp.items():
        for arm in ("A", "B"):
            d = info[arm]
            if info["kind"] == "proportion":
                val = f"{d['point'] * 100:.2f}%"
                ci = f"[{d['lo'] * 100:.2f}%, {d['hi'] * 100:.2f}%]"
                n_s = f"{d['n']} (k={d['k']})"
            elif metric == "cost_mean":
                val = f"${d['point']:.6f}"
                ci = f"[${d['lo']:.6f}, ${d['hi']:.6f}]"
                n_s = str(d["n"])
            else:
                val = f"{d['point']:.1f} ms"
                ci = f"[{d['lo']:.1f}, {d['hi']:.1f}]"
                n_s = str(d["n"])
            rows.append([metric if arm == "A" else "", arm, val, ci, n_s,
                         ("yes" if info["separated"] else "no") if arm == "A" else ""])

    col_widths = [max(len(str(r[c])) for r in [headers] + rows)
                  for c in range(len(headers))]
    def fmt(row):
        return "  ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(row))
    print(fmt(headers))
    print(fmt(["-" * w for w in col_widths]))
    for r in rows:
        print(fmt(r))


def main():
    calls = load_calls()
    cmp = compare_arms(calls)
    print_table(cmp)


if __name__ == "__main__":
    main()
