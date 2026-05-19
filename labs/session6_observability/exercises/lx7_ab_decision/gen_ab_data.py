"""
Generator for the LX-7 dataset.

Deliberately smaller and noisier than Demo 7: 800 calls, 50/50
split, 7-day window. The scenario: we're testing **arm B** =
gpt-4o against **arm A** = gpt-4o-mini on a fixed prompt. Leadership
wants to know whether to switch.

Seeded effects:

  * arm B schema_fail rate    : 4.0% (vs 6.0% for A)    - small win, noisy
  * arm B pii-block rate       : 2.0% (vs 2.0% for A)   - tie
  * arm B latency p50 (ms)     : 460  (vs 380 for A)    - clear regression
  * arm B cost per call        : ~16x A                 - clear regression

At 800 calls the schema-fail comparison is on the edge of
detectability — the CIs often overlap. The latency and cost effects
are big enough that CIs are always separate. The student's job is to
write the right memo: "B wins on schema maybe, loses on latency
definitely, costs 16x more. Ship on a segment, not wholesale."

Run:  python gen_ab_data.py
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import datetime, timedelta


NOW = datetime(2026, 4, 27, 18, 0, 0)
WINDOW_DAYS = 7
WINDOW_START = NOW - timedelta(days=WINDOW_DAYS)
TOTAL_CALLS = 800

PRICING = {
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4o":      {"in": 2.50, "out": 10.00},
}

ARMS = {
    "A": {"model": "gpt-4o-mini", "p_schema_fail": 0.06, "p_pii": 0.02, "lat_median_ms": 380},
    "B": {"model": "gpt-4o",      "p_schema_fail": 0.04, "p_pii": 0.02, "lat_median_ms": 460},
}

TICKETS = [
    ("Checkout broken, losing sales!",         "angry",      9),
    ("Can't upload on Safari.",                "frustrated", 5),
    ("How do I export data to CSV?",           "neutral",    2),
    ("Keyboard shortcut for archiving?",       "neutral",    1),
    ("Love the new update.",                   "happy",      0),
    ("Payment failed 4th time.",               "angry",      7),
    ("Reset my password please.",              "neutral",    3),
    ("Thanks, resolved.",                      "happy",      0),
    ("My phone +1-415-555-0123 is wrong.",     "frustrated", 5),
    ("Send invoice to billing@acme-inc.com.",  "neutral",    4),
]


def _rid(i: int) -> str:
    return "req_" + hashlib.md5(f"{i}-lx7".encode()).hexdigest()[:12]


def diurnal(hour):
    return 0.1 + 0.9 * (1 + math.cos(2 * math.pi * (hour - 14) / 24)) / 2


def main():
    rng = random.Random(202)
    minutes = list(range(WINDOW_DAYS * 24 * 60))
    weights = [diurnal((m % 1440) / 60.0) for m in minutes]
    tot = sum(weights)
    weights = [w / tot for w in weights]
    picks = sorted(rng.choices(minutes, weights=weights, k=TOTAL_CALLS))

    calls = []
    for i, m in enumerate(picks):
        ts = WINDOW_START + timedelta(minutes=m, seconds=rng.random() * 60)
        arm = "A" if rng.random() < 0.5 else "B"
        cfg = ARMS[arm]

        ticket = rng.choice(TICKETS)
        schema_fail = rng.random() < cfg["p_schema_fail"]
        pii = rng.random() < cfg["p_pii"]

        prompt = ("You are a triage agent. Return JSON with keys "
                  f"sentiment, urgency, summary.\n\nTicket:\n{ticket[0]}\n")
        if schema_fail:
            completion = '{"sentiment":"' + ticket[1] + '","urgen'
            outcome = "schema_fail"
        elif pii:
            completion = json.dumps({"sentiment": ticket[1],
                                     "urgency": ticket[2],
                                     "summary": "user contact 415-555-0123"})
            outcome = "blocked_pii"
        else:
            completion = json.dumps({"sentiment": ticket[1],
                                     "urgency": ticket[2],
                                     "summary": ticket[0][:60]})
            outcome = "ok"

        in_toks  = len(prompt) // 4
        out_toks = len(completion) // 4
        lat_ms = int(rng.lognormvariate(math.log(cfg["lat_median_ms"]), 0.3))
        cost = (in_toks / 1e6 * PRICING[cfg["model"]]["in"] +
                out_toks / 1e6 * PRICING[cfg["model"]]["out"])

        calls.append({
            "ts":            ts.isoformat(timespec="milliseconds"),
            "request_id":    _rid(i),
            "arm":           arm,
            "model":         cfg["model"],
            "prompt":        prompt,
            "completion":    completion,
            "input_tokens":  in_toks,
            "output_tokens": out_toks,
            "latency_ms":    lat_ms,
            "cost_usd":      round(cost, 6),
            "outcome":       outcome,
            "ticket.urgency": ticket[2],
        })

    with open("ab_calls.ndjson", "w") as f:
        for c in calls:
            f.write(json.dumps(c) + "\n")

    from collections import Counter
    arm_counts = Counter(c["arm"] for c in calls)
    out_counts = Counter((c["arm"], c["outcome"]) for c in calls)
    print(f"wrote {len(calls)} rows")
    print(f"  arm split: {dict(arm_counts)}")
    for k, v in sorted(out_counts.items()):
        print(f"  {k[0]} / {k[1]}: {v}")


if __name__ == "__main__":
    main()
