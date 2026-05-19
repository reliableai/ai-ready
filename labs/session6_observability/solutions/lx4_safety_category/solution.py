"""
LX-4 reference solution — Instructor only.

Reference implementation of the exercise in
`../../exercises/lx4_safety_category/starter.py`. Anchor for grading,
not "the only right answer." Common variants students ship:

  * A regex with word boundaries instead of `in`. Better precision on
    small corpora but breaks on the "mg" substring inside "timing" —
    fine trade-off, worth discussing.
  * An LLM-judge stub (`judge(completion) -> bool`). Same chain slot,
    different oracle. All the rest of the code stays identical; this
    is the whole point of the factored pipeline.
  * A two-tier check: "suspicious" (flag, don't block) vs
    "advice-like" (block). Better product decision. Slightly more
    dashboard work.

See `SAFETY_DECISION.md` in this folder for the reference writeup.

Run:  python solution.py
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections import Counter
from datetime import datetime, timedelta


NOW = datetime(2026, 4, 27, 18, 0, 0)
WINDOW_DAYS = 14
WINDOW_START = NOW - timedelta(days=WINDOW_DAYS)
TOTAL_CALLS = 1500

PRICING = {
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4o":      {"in": 2.50, "out": 10.00},
}


TICKETS = [
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
    ("My phone +1-415-555-0123 is wrong in your system, please update.",
     "frustrated", 5, "Update phone +1-415-555-0123 on file.", "pii"),
    ("Send the invoice to billing@acme-inc.com — card ending 4242 double-charged.",
     "angry", 7, "Invoice to billing@acme-inc.com; card 4242 double-charged.", "pii"),
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


SCHEMA_KEYS = {"sentiment", "urgency", "summary"}


def check_schema(call: dict) -> None:
    try:
        parsed = json.loads(call["completion"])
        ok = SCHEMA_KEYS.issubset(parsed.keys())
    except Exception:
        ok = False
    call["guardrail"]["schema_ok"] = ok
    if not ok:
        call["outcome"] = "schema_fail"


def check_toxicity(call: dict) -> None:
    if call["outcome"] != "ok":
        return
    toxic = any(w in call["completion"].lower() for w in ["slur_placeholder"])
    call["guardrail"]["toxicity_ok"] = not toxic
    if toxic:
        call["outcome"] = "blocked_toxic"


def check_pii(call: dict) -> None:
    if call["outcome"] != "ok":
        return
    text = call["completion"]
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
# The new check.
# ---------------------------------------------------------------------------

# A very coarse medical-advice classifier. In production, swap this for an
# actual classifier (or LLM judge) — the integration shape wouldn't change.
# The words span three rough categories:
#   * drug names           — acetaminophen, ibuprofen, tylenol, …
#   * care directives      — "see a doctor", "go to the ER", "prescriber"
#   * clinical terminology — "antifungal", "antidepressant", "taper"
# We require *one* hit from *any* category. Using case-insensitive
# whole-word-ish matching to avoid firing on substrings like "ring" in
# "wringing" or "mg" in "timing".

_MEDICAL_PATTERNS = re.compile(
    r"\b("
    r"ibuprofen|tylenol|acetaminophen|antidepressant|antifungal|"
    r"dosage|mg|ml|prescriber|prescription|"
    r"doctor|ER|emergency room|ringworm|rash|"
    r"taper|discontinuation|"
    r"blood pressure|chest pain|fever"
    r")\b",
    re.IGNORECASE,
)


def check_medical_advice(call: dict) -> None:
    """Block completions that sound like medical guidance.

    Fail-closed: we block on first match. Rationale — if our model is
    accidentally prescribing ibuprofen to a child, the cheapest wrong
    answer is an extra support-ticket round-trip with the user; the
    expensive wrong answer is a real prescription-adjacent mistake. So
    we bias toward over-blocking, and report visibly on the dashboard
    so the team can tune the list.
    """
    # Always set the key so downstream code can rely on it, regardless
    # of earlier outcomes.
    hit = bool(_MEDICAL_PATTERNS.search(call["completion"]))
    call["guardrail"]["medical_advice_blocked"] = hit and call["outcome"] == "ok"

    if call["outcome"] != "ok":
        return
    if hit:
        call["outcome"] = "blocked_medical_advice"


GUARDRAILS: list = [
    check_schema,
    check_toxicity,
    # Medical-advice *before* PII: a completion can contain both ("call
    # your doctor at 555-0123"), and we'd rather it be flagged as the
    # stronger category. The taxonomy is clearer for the on-call too —
    # if it's in the medical bucket, a medical-operations team owns
    # triage; the PII bucket is a compliance rotation.
    check_medical_advice,
    check_pii,
]


# ---------------------------------------------------------------------------
# Simulator — unchanged from the starter.
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
            },
            "_rng":           rng,
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
        f.write("// Auto-generated by solution.py.\n")
        f.write("window.__CALLS__ = ")
        json.dump(calls, f)
        f.write(";\n")

    out = Counter(c["outcome"] for c in calls)
    print(f"wrote {len(calls)} rows to llm_calls.ndjson + calls.js")
    print(f"\n  outcomes: {dict(out)}")
    print("  guardrail keys on first row:", sorted(calls[0]["guardrail"]))

    # Self-grading block — matches the hint in README. Truth is decided
    # from the *prompt* (the user's question), not the completion — that
    # way the check (which inspects the completion) and the oracle are
    # decoupled.
    truth_kw = ["fever", "chest pain", "ibuprofen", "antidepressant",
                "Tylenol", "rash", "ringworm"]
    medical_truth = [c for c in calls if any(k in c["prompt"] for k in truth_kw)]
    fired = [c for c in calls if c["outcome"] == "blocked_medical_advice"]
    missed = [c for c in medical_truth if c["outcome"] != "blocked_medical_advice"]
    fp = [c for c in fired if c not in medical_truth]
    print(f"\n  medical truth rows : {len(medical_truth)}")
    print(f"  check fired on     : {len(fired)}")
    print(f"  missed             : {len(missed)}")
    print(f"  false positives    : {len(fp)}")


if __name__ == "__main__":
    main()
