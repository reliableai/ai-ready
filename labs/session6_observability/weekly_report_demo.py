"""
weekly_report_demo.py — "anatomy of a weekly AI-system report" demo.

Generates a fake 4-week dataset of daily metrics (quality, cost, guardrail
reject rate) with a deliberately-seeded regression in Week 3 and a partial
recovery in Week 4. Renders the three charts a useful weekly report
should have, plus a tiny prose summary.

Run:
    python weekly_report_demo.py --out weekly_report.png
"""
from __future__ import annotations
import argparse, datetime as dt, random, statistics as stats

import matplotlib.pyplot as plt       # pip install matplotlib


def synth(seed: int = 7) -> list[dict]:
    """Fake but plausible daily metrics over 28 days."""
    rnd = random.Random(seed)
    rows = []
    start = dt.date(2026, 3, 30)           # Monday, for a clean week boundary
    for i in range(28):
        day = start + dt.timedelta(days=i)
        week = i // 7
        # Quality: baseline 0.82 ± noise, dip in week 2 (index 2), partial recovery week 3
        if week == 0:
            q = rnd.gauss(0.82, 0.02)
        elif week == 1:
            q = rnd.gauss(0.81, 0.02)
        elif week == 2:
            q = rnd.gauss(0.73, 0.03)   # regression shipped
        else:
            q = rnd.gauss(0.78, 0.02)   # partial rollback
        q = max(0.0, min(1.0, q))

        # Cost per successful request: mostly flat, ticks up under retries.
        cost = rnd.gauss(0.0041, 0.0003)
        if week == 2:
            cost += 0.0008              # retries inflated cost

        # Guardrail reject rate: the leading indicator that fires first.
        grr = rnd.gauss(0.02, 0.005)
        if week == 2:
            grr = rnd.gauss(0.055, 0.008)
        elif week == 3:
            grr = rnd.gauss(0.028, 0.006)
        grr = max(0.0, grr)

        rows.append({"date": day, "quality": q, "cost_usd": cost,
                     "guardrail_reject_rate": grr})
    return rows


def weekly(rows: list[dict], key: str) -> list[float]:
    """Weekly means of a given metric, 4 values."""
    return [stats.mean(r[key] for r in rows[i*7:(i+1)*7]) for i in range(4)]


def ci95(rows: list[dict], key: str) -> list[tuple[float, float]]:
    """Rough 95% CI (±1.96σ/√n) per week."""
    out = []
    for i in range(4):
        xs = [r[key] for r in rows[i*7:(i+1)*7]]
        m = stats.mean(xs)
        s = stats.pstdev(xs) / (len(xs) ** 0.5)
        out.append((m - 1.96*s, m + 1.96*s))
    return out


def render(rows: list[dict], out_path: str) -> None:
    dates = [r["date"] for r in rows]
    q = [r["quality"] for r in rows]
    c = [r["cost_usd"] for r in rows]
    g = [r["guardrail_reject_rate"] for r in rows]

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    fig.suptitle("Weekly AI-system report — 4 weeks, one product line",
                 fontsize=14)

    # 1. Quality with weekly CI bars.
    ax = axes[0]
    ax.plot(dates, q, marker="o", linewidth=1, color="#1f77b4",
            label="daily rubric score")
    wk_mid = [dates[i*7 + 3] for i in range(4)]
    wk_ci = ci95(rows, "quality")
    wk_mean = weekly(rows, "quality")
    ax.errorbar(wk_mid, wk_mean,
                yerr=[[m - lo for m, (lo, _) in zip(wk_mean, wk_ci)],
                      [hi - m for m, (_, hi) in zip(wk_mean, wk_ci)]],
                fmt="s", color="black", capsize=6, label="weekly mean ± 95% CI")
    ax.set_ylabel("quality (rubric score)")
    ax.set_ylim(0.6, 1.0)
    ax.legend(loc="lower left", fontsize=9)
    ax.axhline(0.80, linestyle="--", color="gray", linewidth=0.8)
    ax.text(dates[0], 0.805, "target: 0.80", fontsize=8, color="gray")

    # 2. Cost per successful request.
    ax = axes[1]
    ax.plot(dates, c, marker="o", linewidth=1, color="#2ca02c")
    ax.set_ylabel("$ / successful request")

    # 3. Guardrail reject rate — the leading indicator.
    ax = axes[2]
    ax.plot(dates, g, marker="o", linewidth=1, color="#d62728")
    ax.set_ylabel("guardrail reject rate")
    ax.set_xlabel("day")
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(30); lbl.set_ha("right")

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_path, dpi=140)
    print(f"Wrote {out_path}")


def prose(rows: list[dict]) -> str:
    """What a human would write on top of the charts."""
    w = weekly(rows, "quality")
    grr = weekly(rows, "guardrail_reject_rate")
    return (
        f"Week 3 shipped a regression: rubric score dropped from "
        f"{w[1]:.2f} to {w[2]:.2f} with a disjoint 95% CI, and guardrail "
        f"rejects rose from {grr[1]:.1%} to {grr[2]:.1%} — the guardrail "
        f"rate caught it first, ~36 hours ahead of the rubric signal. "
        f"A partial rollback on day 17 recovered quality to "
        f"{w[3]:.2f}; the residual gap is a tool-argument schema mismatch "
        f"we did not cover in the PR's offline evals. "
        f"ACTION ITEM: add a tool-argument-schema guardrail to the CI gate "
        f"for Week 5."
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="weekly_report.png")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rows = synth(seed=args.seed)
    render(rows, args.out)
    print("\n--- PROSE SUMMARY ---")
    print(prose(rows))


if __name__ == "__main__":
    main()
