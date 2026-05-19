# %% [markdown]
# # Demo 4 — generate a stream of LLM calls for a SaaS triage agent
#
# Writes ~3000 JSON-per-line rows to `llm_calls.ndjson`, simulating 14 days of
# traffic against a "support-ticket triage" LLM endpoint. Each call takes a
# raw support ticket and returns structured JSON:
#
#     { "sentiment": "angry" | "frustrated" | "neutral" | "happy",
#       "urgency":   0..10,
#       "summary":   "one-line summary, <= 20 words" }
#
# The stream contains four deliberate incidents — each one corresponds to a
# panel on the dashboard:
#
#     day 3.0 – 3.2  : prompt_version "v3" rolled out; it ends with
#                      "Respond in prose" instead of "Respond with JSON".
#                      Schema-validation fails spike to ~60%. A retry
#                      against a repaired prompt recovers ~half of them.
#                      Rolled back at day 3.2.
#     day 7.5 – 8.5  : upstream API latency on `gpt-4o` spikes 3x (vendor
#                      incident). `gpt-4o-mini` is unaffected. Some calls
#                      time out. Total failure rate visibly rises.
#     day 11.0 onward: a config change ("log the full context in the prompt
#                      for debugging") doubles input-token counts for
#                      everyone. Cost panel spikes; latency barely moves.
#     day 13.0 – 14.0: a batch of tickets pastes in user PII (email + phone).
#                      The guardrail correctly blocks some of those answers
#                      from being stored (outcome 'blocked_pii'), but the
#                      trip rate jumps enough that the dashboard's guardrail
#                      panel shows a new spike.
#
# Every other hour looks normal. The point of the demo is that the *monitoring*
# tells you something is wrong before any user writes in — each incident shows
# up on a different panel, and each panel drills back into the same flat-row
# log file.
#
# Run as a script (`python gen_calls.py`) or step through cell-by-cell.

# %% Imports
import hashlib
import json
import math
import random
from datetime import datetime, timedelta


# %% Window & totals
NOW = datetime(2026, 4, 27, 18, 0, 0)
WINDOW_DAYS = 14
WINDOW_START = NOW - timedelta(days=WINDOW_DAYS)
TOTAL_CALLS = 3000


# %% Pricing (per million tokens, USD)
PRICING = {
    "gpt-4o-mini": {"in": 0.15,  "out": 0.60},
    "gpt-4o":      {"in": 2.50,  "out": 10.00},
}


# %% Prompt versions
PROMPT_TEMPLATE_V1 = """You are a triage agent for CustomerCarePro. Given a support ticket, return JSON with keys:
  - sentiment: one of "angry" | "frustrated" | "neutral" | "happy"
  - urgency: integer 0-10
  - summary: one-line summary, max 20 words

Ticket:
{ticket}

Respond with only the JSON object."""

PROMPT_TEMPLATE_V2 = PROMPT_TEMPLATE_V1.replace(
    'Respond with only the JSON object.',
    'Respond with only the JSON object. Be strict with urgency — reserve 8+ for revenue-critical.'
)

# v3 is the broken one — somebody edited the last line in a refactor.
PROMPT_TEMPLATE_V3 = PROMPT_TEMPLATE_V2.replace(
    'Respond with only the JSON object.',
    'Explain your reasoning in prose, then give the answer.'
)


def prompt_version_at(t: datetime) -> str:
    """Return the prompt version active at time t."""
    d = (t - WINDOW_START).total_seconds() / 86400.0
    if d < 1.0:                 return "v1"
    if d < 3.0:                 return "v2"
    if 3.0 <= d < 3.8:          return "v3"      # broken window (20h)
    return "v2"                                  # rolled back


# %% Ticket pool
# A mix of business cases. Each is (text, likely_sentiment, urgency_hint,
# summary_hint, contains_pii). The model reliably gets the happy-path
# predictions right; the only PII we leak is when the user put PII in the
# ticket and we don't redact the echoed summary.

TICKETS = [
    # revenue-critical / angry
    ("The checkout page has been broken for 3 hours, I'm losing sales every minute!",
     "angry", 9, "Checkout page broken 3h; revenue loss ongoing.", False),
    ("Your product is terrible and your support is worse. Canceling my subscription.",
     "angry", 6, "User canceling subscription due to product and support complaints.", False),
    ("Invoice #INV-2026-001234 shows $490 but we only owe $49. Fix ASAP, auditor is here.",
     "frustrated", 8, "Invoice INV-2026-001234 overcharged 10x; auditor waiting.", False),
    ("Payment failed for 4th time. This is ridiculous.",
     "angry", 7, "Repeated payment failures; customer frustrated.", False),
    # frustrated / neutral
    ("Can't upload images on Safari, third time I'm contacting support.",
     "frustrated", 5, "Safari image upload fails; repeat issue.", False),
    ("SSO login takes 20 seconds. Used to be instant. Any idea?",
     "frustrated", 4, "SSO login latency regression.", False),
    ("The timeline view doesn't show items older than 30 days anymore.",
     "frustrated", 4, "Timeline view capped to 30 days.", False),
    ("How do I export my data to CSV?",
     "neutral", 2, "Data export to CSV question.", False),
    ("Is there a keyboard shortcut for archiving?",
     "neutral", 1, "Keyboard shortcut question.", False),
    ("Do you have an API endpoint for listing integrations?",
     "neutral", 2, "API endpoint question re integrations.", False),
    ("Can you help me reset my password?",
     "neutral", 3, "Password reset assistance.", False),
    # happy / positive
    ("Love the new update! The timeline view is great.",
     "happy", 0, "Positive feedback on timeline view.", False),
    ("Thanks for the quick response, issue resolved.",
     "happy", 0, "Issue resolved; user thanks support.", False),
    ("Just wanted to say your docs are the best I've seen.",
     "happy", 0, "Positive docs feedback.", False),
    # PII-containing tickets (only appear in the day-13+ window)
    ("My phone +1-415-555-0123 is wrong in your system, please update. Email me at jane.doe@example.com.",
     "frustrated", 5, "Update phone +1-415-555-0123 and email jane.doe@example.com on file.", True),
    ("Please ship my replacement to 742 Evergreen Terrace, Springfield. My number is 555-867-5309.",
     "neutral", 3, "Ship replacement to 742 Evergreen Terrace, Springfield; phone 555-867-5309.", True),
    ("Send the invoice to billing@acme-inc.com — my card ending 4242 was charged twice.",
     "angry", 7, "Invoice to billing@acme-inc.com; card ending 4242 double-charged.", True),
    ("Account jane.doe@example.com locked out; SSN on file is 123-45-6789 if verification needed.",
     "frustrated", 6, "Account jane.doe@example.com locked; SSN 123-45-6789 shared for verification.", True),
]


# %% Synthetic completions
def happy_completion(t, ticket) -> str:
    """A well-formed JSON the prompt asked for."""
    obj = {
        "sentiment": ticket[1],
        "urgency":   ticket[2],
        "summary":   ticket[3],
    }
    return json.dumps(obj)


def v3_broken_completion(t, ticket) -> str:
    """v3 (the broken prompt) asked for prose, so the model replies in prose —
    no JSON to parse. Sometimes, later in the window, the model self-corrects
    and wraps JSON at the end."""
    reasoning = (
        f"The ticket reads as {ticket[1]} with urgency around {ticket[2]}/10. "
        f"The core issue: {ticket[3].lower()}."
    )
    # 20% of the time the model appends a JSON blob after the prose — the
    # retry-with-repair path will still recover those.
    if random.random() < 0.20:
        tail = ' {"sentiment":"' + ticket[1] + f'","urgency":{ticket[2]},"summary":"{ticket[3]}"}}'
        return reasoning + tail
    return reasoning


# %% Diurnal weighting
def diurnal_weight(hour_of_day: float) -> float:
    return 0.1 + 0.9 * (1 + math.cos(2 * math.pi * (hour_of_day - 14) / 24)) / 2


# %% Call generator
def _request_id(i: int) -> str:
    return "req_" + hashlib.md5(f"{i}-demo4".encode()).hexdigest()[:12]


def choose_model(rng, day_fraction) -> str:
    """A tier-routing rule: ~15% of calls go to gpt-4o, the rest to mini.
    We introduce slight drift over time so the dashboard isn't flat.
    """
    return "gpt-4o" if rng.random() < 0.15 else "gpt-4o-mini"


def api_latency(rng, model: str, day_fraction: float) -> int:
    """Return latency_ms. The gpt-4o path sees a 3x spike in
    day 7.5–8.5 (vendor incident)."""
    if model == "gpt-4o":
        base = rng.lognormvariate(math.log(1200), 0.35)
        if 7.5 <= day_fraction < 8.5:
            base *= rng.uniform(2.5, 3.5)
            if rng.random() < 0.18:
                base = max(base, 15_000)   # timeouts
    else:
        base = rng.lognormvariate(math.log(350), 0.30)
    return int(max(50, base))


def generate_calls() -> list[dict]:
    rng = random.Random(42)

    # Sample timestamps with diurnal weight.
    minutes = list(range(WINDOW_DAYS * 24 * 60))
    weights = [diurnal_weight((m % 1440) / 60.0) for m in minutes]
    total_w = sum(weights)
    weights = [w / total_w for w in weights]
    picks = rng.choices(minutes, weights=weights, k=TOTAL_CALLS)
    picks.sort()

    calls: list[dict] = []
    for i, m in enumerate(picks):
        ts = WINDOW_START + timedelta(minutes=m, seconds=rng.random() * 60)
        day_fraction = (ts - WINDOW_START).total_seconds() / 86400.0

        # Ticket selection. PII tickets only appear in the day-13 incident.
        if 13.0 <= day_fraction:
            ticket = rng.choice(TICKETS) if rng.random() < 0.70 else rng.choice(
                [t for t in TICKETS if t[4]]      # PII-bearing slice
            )
        else:
            ticket = rng.choice([t for t in TICKETS if not t[4]])

        prompt_version = prompt_version_at(ts)
        template = {
            "v1": PROMPT_TEMPLATE_V1,
            "v2": PROMPT_TEMPLATE_V2,
            "v3": PROMPT_TEMPLATE_V3,
        }[prompt_version]
        prompt = template.format(ticket=ticket[0])

        model = choose_model(rng, day_fraction)

        # Input-token count. From day 11 onward, a config change ("log full
        # context in the prompt for debugging") triples input tokens.
        verbose = day_fraction >= 11.0
        in_tokens = len(prompt) // 4
        if verbose:
            in_tokens *= 3                         # verbose context dump
        # Completion tokens depend on broken-prompt path.
        if prompt_version == "v3":
            completion = v3_broken_completion(ts, ticket)
        else:
            completion = happy_completion(ts, ticket)
        out_tokens = len(completion) // 4

        latency_ms = api_latency(rng, model, day_fraction)

        # --- Structural validation ----------------------------------------
        try:
            parsed = json.loads(completion)
            ok_keys = {"sentiment", "urgency", "summary"}
            schema_ok = ok_keys.issubset(parsed.keys())
        except Exception:
            # v3's "reasoning prose" case — fails JSON parse.
            schema_ok = False
            # If v3's completion happens to end with a JSON blob, try to
            # pick it out. This simulates "retry-with-repair".
            if prompt_version == "v3" and "{" in completion:
                try:
                    tail = completion[completion.index("{"):]
                    parsed = json.loads(tail)
                    schema_ok = {"sentiment", "urgency", "summary"}.issubset(parsed.keys())
                    if schema_ok:
                        # Count the retry as a second call — same row, flagged.
                        out_tokens += len(tail) // 4
                        latency_ms += int(latency_ms * 0.8)
                except Exception:
                    schema_ok = False

        # --- Outcome classification ---------------------------------------
        outcome = "ok"
        guardrail = {
            "schema_ok":   schema_ok,
            "toxicity_ok": True,
            "pii_found":   False,
            "pii_blocked": False,
        }

        if not schema_ok:
            outcome = "schema_fail"
        elif latency_ms >= 15_000:
            outcome = "timeout"
        elif model == "gpt-4o" and 7.5 <= day_fraction < 8.5 and rng.random() < 0.10:
            outcome = "api_error"

        # PII detection — ticket text contained it, and the summary echoed
        # back a chunk of it. Our guardrail catches ~70% of those; the rest
        # slip through (outcome "ok" but with pii_found=True, flagged for
        # audit). The 70% we catch get blocked.
        if outcome == "ok" and ticket[4]:
            guardrail["pii_found"] = True
            if rng.random() < 0.70:
                guardrail["pii_blocked"] = True
                outcome = "blocked_pii"

        # Rare toxicity trip — very low base rate, slightly higher on angry
        # tickets where the model might echo something inflammatory back.
        if outcome == "ok" and ticket[1] == "angry" and rng.random() < 0.003:
            guardrail["toxicity_ok"] = False
            outcome = "blocked_toxic"

        # --- Cost -------------------------------------------------------
        cost = (
            in_tokens  / 1_000_000 * PRICING[model]["in"]
          + out_tokens / 1_000_000 * PRICING[model]["out"]
        )

        calls.append({
            "ts":             ts.isoformat(timespec="milliseconds"),
            "request_id":     _request_id(i),
            "model":          model,
            "prompt_version": prompt_version,
            "temperature":    0.2,
            "prompt":         prompt,
            "completion":     completion,
            "input_tokens":   in_tokens,
            "output_tokens":  out_tokens,
            "latency_ms":     latency_ms,
            "cost_usd":       round(cost, 6),
            "outcome":        outcome,
            "guardrail":      guardrail,
        })

    return calls


# %% Driver
def main() -> None:
    calls = generate_calls()

    with open("llm_calls.ndjson", "w") as f:
        for c in calls:
            f.write(json.dumps(c) + "\n")

    with open("calls.js", "w") as f:
        f.write("// Auto-generated by gen_calls.py — same rows as llm_calls.ndjson.\n")
        f.write("window.__CALLS__ = ")
        json.dump(calls, f)
        f.write(";\n")

    # ---- Sanity summary ----------------------------------------------------
    from collections import Counter
    out = Counter(c["outcome"] for c in calls)
    mods = Counter(c["model"] for c in calls)
    pvs = Counter(c["prompt_version"] for c in calls)

    print(f"wrote {len(calls)} rows to llm_calls.ndjson + calls.js")
    print(f"\n  models: {dict(mods)}")
    print(f"  prompt_versions: {dict(pvs)}")
    print(f"  outcomes: {dict(out)}")

    # Cost per day per model
    print("\n  cost by day (USD):")
    by_day: dict[int, float] = {}
    for c in calls:
        d = int((datetime.fromisoformat(c["ts"]) - WINDOW_START).total_seconds() / 86400)
        by_day[d] = by_day.get(d, 0) + c["cost_usd"]
    for d in sorted(by_day):
        flag = "  ← verbose mode" if d >= 11 else ""
        print(f"    day {d:>2}:  ${by_day[d]:.4f}{flag}")


# %% Run
if __name__ == "__main__":
    main()
