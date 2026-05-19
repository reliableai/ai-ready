# %% [markdown]
# # Demo 7 — generate an A/B dataset for a prompt-version change
#
# Pairs with Slide 29 (analysis over monitoring data) and Slide 30 (A/B
# testing with confidence intervals). Extends the Demo 2/4 flat call-row
# shape with an `arm` column ("A" or "B") so the dashboard can split metrics
# two ways.
#
# Background story: we have a triage agent on prompt_version=v2 (arm A, the
# "champion"). A proposed v3 (arm B, the "challenger") adds a few safety-rail
# lines to the system prompt. The team thinks v3 is better on schema
# adherence but isn't sure whether it slows things down or whether the longer
# system prompt is worth the token cost.
#
# The generator seeds four small latent effects so the dashboard has real
# things to report:
#
#   * arm B schema_fail rate     : 3% (vs 8% for A)       ← B is better
#   * arm B latency p50 (ms)     : +20 ms (vs A)          ← B is slightly slower
#   * arm B cost per call        : +$0.0003 (vs A)        ← B is slightly pricier
#   * arm B pii_blocked rate     : 2.5% (vs 2.2% for A)   ← wash / regression
#
# The whole point is that decisions are multi-dimensional: B wins on the
# primary metric (schema fails) but regresses or ties on three secondaries.
# The dashboard shows all four side-by-side with 95% confidence intervals so
# the user can actually *decide*.
#
# Traffic split is 50/50, random assignment per call, stable over the 14-day
# window. Total ~3000 calls.
#
# Run as a script (`python gen_ab_runs.py`) or step through cell-by-cell.

# %% Imports
from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import datetime, timedelta


# %% Window, pricing, effects
NOW = datetime(2026, 4, 27, 18, 0, 0)
WINDOW_DAYS = 14
WINDOW_START = NOW - timedelta(days=WINDOW_DAYS)
TOTAL_CALLS = 3000

PRICING = {
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4o":      {"in": 2.50, "out": 10.00},
}

# Latent effect sizes (true population values).
EFFECTS = {
    "A": {"p_schema_fail": 0.08, "p_pii": 0.022, "lat_median_ms": 340, "extra_in_toks": 0},
    "B": {"p_schema_fail": 0.03, "p_pii": 0.025, "lat_median_ms": 360, "extra_in_toks": 25},
}


# %% Ticket pool
TICKETS = [
    ("The checkout page has been broken for 3 hours!",          "angry",      9),
    ("Can't upload images on Safari.",                          "frustrated", 5),
    ("How do I export my data to CSV?",                         "neutral",    2),
    ("Is there a keyboard shortcut for archiving?",             "neutral",    1),
    ("Love the new timeline view.",                             "happy",      0),
    ("Payment failed for the 4th time, this is ridiculous.",    "angry",      7),
    ("Can you help me reset my password?",                      "neutral",    3),
    ("Thanks for the quick response.",                          "happy",      0),
    ("My phone +1-415-555-0123 is wrong in your system.",       "frustrated", 5),
    ("Send the invoice to billing@acme-inc.com.",               "neutral",    4),
]


# %% Helpers
def _rid(i: int) -> str:
    return "req_" + hashlib.md5(f"{i}-demo7".encode()).hexdigest()[:12]


def diurnal_weight(hour: float) -> float:
    return 0.1 + 0.9 * (1 + math.cos(2 * math.pi * (hour - 14) / 24)) / 2


# %% Call generator
def generate_calls() -> list[dict]:
    rng = random.Random(77)
    minutes = list(range(WINDOW_DAYS * 24 * 60))
    weights = [diurnal_weight((m % 1440) / 60.0) for m in minutes]
    tot = sum(weights)
    weights = [w / tot for w in weights]
    picks = sorted(rng.choices(minutes, weights=weights, k=TOTAL_CALLS))

    calls: list[dict] = []
    for i, m in enumerate(picks):
        ts = WINDOW_START + timedelta(minutes=m, seconds=rng.random() * 60)
        arm = "A" if rng.random() < 0.5 else "B"
        eff = EFFECTS[arm]

        ticket = rng.choice(TICKETS)
        model = "gpt-4o" if rng.random() < 0.15 else "gpt-4o-mini"

        # Schema fail rate is arm-dependent.
        schema_fail = rng.random() < eff["p_schema_fail"]
        pii = rng.random() < eff["p_pii"]

        prompt_body = (
            "You are a triage agent for CustomerCarePro. Given a support "
            "ticket, return JSON with keys sentiment, urgency, summary.\n"
        )
        if arm == "B":
            # v3 adds a few safety-rail lines — extra tokens in the prompt.
            prompt_body += ("Do not infer PII. Do not give medical advice. "
                            "If the ticket references a specific person's "
                            "identity, redact names.\n")
        prompt = f"{prompt_body}\nTicket:\n{ticket[0]}\n"

        if schema_fail:
            completion = '{"sentiment":' + ticket[1] + ',"urgen'  # broken
            outcome = "schema_fail"
        elif pii:
            completion = json.dumps({
                "sentiment": ticket[1],
                "urgency":   ticket[2],
                "summary":   "user provided contact +1-415-555-0123",
            })
            outcome = "blocked_pii"
        else:
            completion = json.dumps({
                "sentiment": ticket[1],
                "urgency":   ticket[2],
                "summary":   ticket[0][:60],
            })
            outcome = "ok"

        in_tokens  = len(prompt) // 4
        out_tokens = len(completion) // 4
        # Latency: arm-specific median, lognormal sigma=0.3.
        lat_ms = int(rng.lognormvariate(math.log(eff["lat_median_ms"]), 0.3))
        cost = (in_tokens / 1e6 * PRICING[model]["in"] +
                out_tokens / 1e6 * PRICING[model]["out"])

        calls.append({
            "ts":             ts.isoformat(timespec="milliseconds"),
            "request_id":     _rid(i),
            "arm":            arm,
            "prompt_version": "v2" if arm == "A" else "v3",
            "model":          model,
            "prompt":         prompt,
            "completion":     completion,
            "input_tokens":   in_tokens,
            "output_tokens":  out_tokens,
            "latency_ms":     lat_ms,
            "cost_usd":       round(cost, 6),
            "outcome":        outcome,
        })

    return calls


# %% Driver
def main() -> None:
    calls = generate_calls()

    with open("ab_calls.ndjson", "w") as f:
        for c in calls:
            f.write(json.dumps(c) + "\n")
    with open("ab_calls.js", "w") as f:
        f.write("// Auto-generated by gen_ab_runs.py.\n")
        f.write("window.__AB_CALLS__ = ")
        json.dump(calls, f)
        f.write(";\n")

    from collections import Counter
    arm_counts = Counter(c["arm"] for c in calls)
    out_by_arm = Counter((c["arm"], c["outcome"]) for c in calls)
    print(f"wrote {len(calls)} rows")
    print(f"  arm split: {dict(arm_counts)}")
    print(f"  outcomes by arm:")
    for (arm, out), n in sorted(out_by_arm.items()):
        print(f"    {arm} / {out}: {n}")


# %% Run
if __name__ == "__main__":
    main()
