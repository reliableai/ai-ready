"""
LX-4 — Add a new safety category to the triage pipeline.

Pairs with Demo 4. Read `README.md` for the task description and success
criteria. You'll implement `check_medical_advice` below, register it in
the `GUARDRAILS` chain, regenerate the data, and patch `dashboard.html`
to show the new category.

The pipeline here is the *factored* cousin of Demo 4's inline simulator.
Each check is a function that reads the mutable `call` dict and updates
it in place. The chain is just a list — add, remove, or reorder checks
by editing `GUARDRAILS`. That's the extension point this exercise
targets.

Run:  python starter.py
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from datetime import datetime, timedelta


NOW = datetime(2026, 4, 27, 18, 0, 0)
WINDOW_DAYS = 14
WINDOW_START = NOW - timedelta(days=WINDOW_DAYS)
TOTAL_CALLS = 1500        # smaller than Demo 4 — exercise runs faster

PRICING = {
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4o":      {"in": 2.50, "out": 10.00},
}


# ---------------------------------------------------------------------------
# Ticket pool.
#
# A subset of Demo 4's tickets plus a MEDICAL slice. The medical tickets are
# the ones your new check is supposed to catch — they invite the model to
# act as a doctor, and a compliant completion from the model is what the
# guardrail should reject.
# ---------------------------------------------------------------------------

# (text, sentiment, urgency, summary, kind)
# kind ∈ {"normal", "pii", "medical"}.
TICKETS = [
    # --- normal business ---
    ("The checkout page has been broken for 3 hours, I'm losing sales every minute!",
     "angry", 9, "Checkout page broken 3h; revenue loss ongoing.", "normal"),
    ("Can't upload images on Safari, third time I'm contacting support.",
     "frustrated", 5, "Safari image upload fails; repeat issue.", "normal"),
    ("How do I export my data to CSV?",
     "neutral", 2, "Data export to CSV question.", "normal"),
    ("Is there a keyboard shortcut for archiving?",
     "neutral", 1, "Keyboard shortcut question.", "normal"),
    ("Love the new update! The timeline view is great.",
     "happy", 0, "Positive feedback on timeline view.", "normal"),
    ("Payment failed for 4th time. This is ridiculous.",
     "angry", 7, "Repeated payment failures; customer frustrated.", "normal"),
    ("Can you help me reset my password?",
     "neutral", 3, "Password reset assistance.", "normal"),
    ("Thanks for the quick response, issue resolved.",
     "happy", 0, "Issue resolved; user thanks support.", "normal"),

    # --- PII-bearing (already handled by check_pii) ---
    ("My phone +1-415-555-0123 is wrong in your system, please update.",
     "frustrated", 5, "Update phone +1-415-555-0123 on file.", "pii"),
    ("Send the invoice to billing@acme-inc.com — card ending 4242 double-charged.",
     "angry", 7, "Invoice to billing@acme-inc.com; card 4242 double-charged.", "pii"),

    # --- MEDICAL (this is what your new check is for) ---
    # The model, trying to be helpful, writes a summary that looks like advice.
    ("My 5-year-old has a fever of 102. What should I give her?",
     "frustrated", 6, "Give children's ibuprofen 7.5 mL every 6 hours; see doctor if fever persists.", "medical"),
    ("I've had chest pain for two days. Should I go to the ER?",
     "frustrated", 8, "Chest pain 2 days — recommend going to the ER immediately.", "medical"),
    ("Is it safe to take ibuprofen with my blood pressure meds?",
     "neutral", 4, "Ibuprofen is generally safe with most BP meds but consult your prescriber.", "medical"),
    ("I stopped my antidepressant yesterday, feeling weird. Normal?",
     "frustrated", 7, "Abruptly stopping antidepressants can cause discontinuation symptoms; taper advised.", "medical"),
    ("How many Tylenol is too many in a day?",
     "neutral", 3, "Do not exceed 3000 mg acetaminophen daily to avoid liver damage.", "medical"),
    ("My rash looks like this photo. Is it ringworm?",
     "frustrated", 4, "Based on description it could be ringworm; try OTC antifungal for 2 weeks.", "medical"),
]


# ---------------------------------------------------------------------------
# Guardrail checks.  Each one mutates the `call` dict in place.
# A check may set `call["outcome"]` to anything other than "ok" to
# short-circuit later checks (this is what "fail-closed" looks like in
# code).
# ---------------------------------------------------------------------------

SCHEMA_KEYS = {"sentiment", "urgency", "summary"}


def check_schema(call: dict) -> None:
    """Try to parse the completion as JSON with the three required keys."""
    try:
        parsed = json.loads(call["completion"])
        ok = SCHEMA_KEYS.issubset(parsed.keys())
    except Exception:
        ok = False
    call["guardrail"]["schema_ok"] = ok
    if not ok:
        call["outcome"] = "schema_fail"


def check_toxicity(call: dict) -> None:
    """Very coarse keyword filter — a real system would use a classifier."""
    if call["outcome"] != "ok":
        return
    # We don't inject any toxic completions in this simulator, but the
    # hook is here so the pipeline has all three checks wired up.
    toxic = any(w in call["completion"].lower() for w in ["slur_placeholder"])
    call["guardrail"]["toxicity_ok"] = not toxic
    if toxic:
        call["outcome"] = "blocked_toxic"


def check_pii(call: dict) -> None:
    """Regex-ish check for emails + long digit runs in the completion.
    If PII is found, we block 70% of the time and audit-flag the rest."""
    if call["outcome"] != "ok":
        return
    text = call["completion"]
    # Cheap signals: an @ sign with a . after it, OR a run of >= 7 digits.
    has_email = ("@" in text) and ("." in text.split("@", 1)[-1][:30])
    digit_run = any(
        text[i : i + 7].replace("-", "").replace(" ", "").isdigit()
        for i in range(max(0, len(text) - 7) + 1)
    )
    has_pii = has_email or digit_run
    call["guardrail"]["pii_found"] = has_pii
    if has_pii and call["_rng"].random() < 0.70:
        call["guardrail"]["pii_blocked"] = True
        call["outcome"] = "blocked_pii"


# ---------------------------------------------------------------------------
# YOUR TASK starts here.
#
# Implement `check_medical_advice` below. The spec:
#
#   1. Only runs if earlier checks haven't already failed
#      (i.e. `call["outcome"] == "ok"` at entry).
#   2. Inspects `call["completion"]` for signals that the model is
#      giving medical advice (dosages, "see a doctor", prescription
#      language, anatomy, etc.). Use whatever you want — keyword list,
#      small classifier, LLM judge. The lab doesn't care about the
#      technique; it cares about the pipeline integration.
#   3. On a hit:
#        - set `call["guardrail"]["medical_advice_blocked"] = True`
#        - set `call["outcome"] = "blocked_medical_advice"`
#      On a miss:
#        - set `call["guardrail"]["medical_advice_blocked"] = False`
#      (always set the key so downstream code can rely on it).
#   4. Write a short SAFETY_DECISION.md that explains your fail-closed /
#      fail-open choice and the rationale.
#
# Then: add your check to `GUARDRAILS` at the right spot and re-run.
# ---------------------------------------------------------------------------


def check_medical_advice(call: dict) -> None:
    """TODO: implement.

    Hints:
      * The 6 "medical" tickets above all produce completions that contain
        words like "ibuprofen", "ER", "mg", "doctor", "Tylenol",
        "antidepressant". Pick a handful that cover the space.
      * Watch out for false positives: the ticket `"How do I export my
        data to CSV?"` should not fire your check, even though the string
        "data" is close to "medical data" in some sense.
      * Test your check on the 6 medical completions AND on the 10
        non-medical ones. You want it to fire on the 6 and stay silent on
        the 10.
    """
    raise NotImplementedError("implement check_medical_advice()")


GUARDRAILS: list = [
    check_schema,
    # Order matters. Toxicity runs before PII because a toxic completion
    # should be blocked for toxicity, not leak through the PII path.
    check_toxicity,
    check_pii,
    # TODO: add `check_medical_advice` here once you've implemented it.
    # Think about the order — where should it sit relative to pii and
    # toxicity? What happens if a medical-advice completion also contains
    # a phone number?
]


# ---------------------------------------------------------------------------
# Simulator — you do not need to edit anything below.
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = (
    "You are a triage agent for CustomerCarePro. Given a support ticket, "
    "return JSON with keys sentiment, urgency, summary.\n\nTicket:\n{ticket}\n"
)


def happy_completion(ticket) -> str:
    return json.dumps({"sentiment": ticket[1], "urgency": ticket[2], "summary": ticket[3]})


def diurnal_weight(hour: float) -> float:
    return 0.1 + 0.9 * (1 + math.cos(2 * math.pi * (hour - 14) / 24)) / 2


def _rid(i: int) -> str:
    return "req_" + hashlib.md5(f"{i}-lx4".encode()).hexdigest()[:12]


def generate_calls() -> list[dict]:
    rng = random.Random(42)

    minutes = list(range(WINDOW_DAYS * 24 * 60))
    weights = [diurnal_weight((m % 1440) / 60.0) for m in minutes]
    tot = sum(weights)
    weights = [w / tot for w in weights]
    picks = sorted(rng.choices(minutes, weights=weights, k=TOTAL_CALLS))

    calls: list[dict] = []
    for i, m in enumerate(picks):
        ts = WINDOW_START + timedelta(minutes=m, seconds=rng.random() * 60)
        day_frac = (ts - WINDOW_START).total_seconds() / 86400.0

        # Medical tickets start appearing on day 8 and become common on
        # day 12 (a link to our service was posted on a parenting forum).
        p_medical = 0.00 if day_frac < 8 else (0.03 if day_frac < 12 else 0.18)
        p_pii     = 0.01 if day_frac < 10 else 0.12
        r = rng.random()
        if r < p_medical:
            ticket = rng.choice([t for t in TICKETS if t[4] == "medical"])
        elif r < p_medical + p_pii:
            ticket = rng.choice([t for t in TICKETS if t[4] == "pii"])
        else:
            ticket = rng.choice([t for t in TICKETS if t[4] == "normal"])

        model = "gpt-4o" if rng.random() < 0.15 else "gpt-4o-mini"
        prompt = PROMPT_TEMPLATE.format(ticket=ticket[0])
        completion = happy_completion(ticket)
        in_tokens = len(prompt) // 4
        out_tokens = len(completion) // 4
        latency_ms = int(rng.lognormvariate(math.log(350), 0.3))
        cost = (in_tokens / 1e6 * PRICING[model]["in"] +
                out_tokens / 1e6 * PRICING[model]["out"])

        call = {
            "ts":             ts.isoformat(timespec="milliseconds"),
            "request_id":     _rid(i),
            "model":          model,
            "prompt_version": "v2",
            "temperature":    0.2,
            "prompt":         prompt,
            "completion":     completion,
            "input_tokens":   in_tokens,
            "output_tokens":  out_tokens,
            "latency_ms":     latency_ms,
            "cost_usd":       round(cost, 6),
            "outcome":        "ok",
            "guardrail": {
                "schema_ok":   True,
                "toxicity_ok": True,
                "pii_found":   False,
                "pii_blocked": False,
                # medical_advice_blocked intentionally NOT pre-set — the
                # check itself is responsible for adding the key. That way
                # you can see in the output whether your check ran.
            },
            "_rng":           rng,   # scratch — stripped before writing
        }

        for check in GUARDRAILS:
            check(call)

        call.pop("_rng")
        calls.append(call)

    return calls


def main() -> None:
    calls = generate_calls()

    with open("llm_calls.ndjson", "w") as f:
        for c in calls:
            f.write(json.dumps(c) + "\n")
    with open("calls.js", "w") as f:
        f.write("// Auto-generated by starter.py — same rows as llm_calls.ndjson.\n")
        f.write("window.__CALLS__ = ")
        json.dump(calls, f)
        f.write(";\n")

    out = Counter(c["outcome"] for c in calls)
    print(f"wrote {len(calls)} rows to llm_calls.ndjson + calls.js")
    print(f"\n  outcomes: {dict(out)}")
    print("\n  guardrail keys on first row:", sorted(calls[0]["guardrail"]))
    print("\n  If 'medical_advice_blocked' is missing above, your check isn't")
    print("  wired into GUARDRAILS yet. If it's present but always False,")
    print("  your check isn't triggering — try it on one of the medical")
    print("  completions by hand.")


if __name__ == "__main__":
    main()
