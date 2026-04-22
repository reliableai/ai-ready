# LX-4 · A new safety category

Pairs with [Demo 4](../../demos/4_llm_calls/README.md). ~35 minutes.

## Background

Demo 4 ships with three guardrail checks: **schema** (structural),
**toxicity** (content), **PII in the answer** (content). Each one is a
small function; together they form a *chain* that runs after the model
returns. The last 10 days of Slide 20 / 21 are about exactly this
pattern — the structural validation problem and the content-safety
problem are different problems, run by different code, with different
fail-closed/fail-open answers.

You're the on-call. A new failure mode just came in: users asking
medical questions, the triage model giving them medical-sounding
answers (dosages, "go to the ER", drug interactions), and the
`summary` field shipping that advice into the support ticket. The
existing PII check doesn't catch it — there's no email, no phone
number — and the toxicity check doesn't catch it either, because the
model is being *helpful*, not *toxic*.

You have one hour to add a fourth check, wire it through the
pipeline, and make it visible on the dashboard.

## Task

1. Implement `check_medical_advice(call)` in `starter.py`. The function
   should set `call["guardrail"]["medical_advice_blocked"] = True/False`
   on every call (always set the key) and, on a hit, set
   `call["outcome"] = "blocked_medical_advice"`. Use whatever signal
   you want — keyword list, regex, small classifier, LLM judge. The
   exercise doesn't grade the technique, it grades the integration.
2. Register your check in the `GUARDRAILS` list. Think about *order*
   — should medical-advice run before or after the PII check? Write
   one line in `SAFETY_DECISION.md` defending your choice.
3. Re-run `python starter.py`. Confirm the printed outcome counts
   include `blocked_medical_advice`, and the printed guardrail keys on
   the first row include `medical_advice_blocked`.
4. Patch `dashboard.html`. The minimum patch is one entry in the
   `TRIP_OUTCOMES` array (search the file for `TODO`). Optional:
   give your category a distinct colour in `TRIP_COLOR` and a KPI tile.
5. Open `dashboard.html` in a browser. The "guardrail trips per day"
   panel should show your new colour. There should be a clear lift on
   day 12 when the parenting-forum link drops.
6. Write `SAFETY_DECISION.md` (≤ 200 words) with:
   - **Order:** where you placed your check in the chain and why.
   - **Fail-closed vs fail-open:** which one you picked, and the
     scenario you would pick the other one for.
   - **What the check catches and what it misses:** one example of
     each.

## Rules

1. **Don't touch the Pydantic schema or the `check_schema` function.**
   This exercise is about content safety, which is a *separate concern*
   from structural validity. Mixing them up is exactly the failure
   mode Slide 20 calls out.
2. **The check must mutate `call` in place** to match the existing
   shape — it's a function with `(call: dict) -> None`. No return
   value. The pipeline runner doesn't read return values.
3. **No external API calls.** Keep it offline so the lab runs without
   credentials. A keyword list is fine; an LLM judge would also be
   fine if you stub the LLM.
4. **The starter script must still run cleanly** when your check is
   wired up. If you crash the simulator on a row that *isn't* a
   medical ticket, you've got the order or the predicate wrong.

## How to run

```bash
python starter.py            # writes llm_calls.ndjson + calls.js
open dashboard.html          # or double-click it
```

The starter is deterministic (seed=42 + frozen
`NOW = 2026-04-27T18:00`). Re-running it produces the same 1500
rows every time, so you can inspect specific rows by index.

There are 36 medical-completion rows in the data, distributed roughly
as: ~10 across days 8–11 (ambient growth) and ~25 across days 12–13
(the forum-link surge). A correct check should catch most of them.
False positives on the 8 normal-business tickets should be zero.

## What to submit

- Your patched `starter.py` (or a separate `solution.py` — your
  choice; whichever runs `python <file>.py` to produce the data).
- Your patched `dashboard.html`.
- `SAFETY_DECISION.md` — the three short sections above.

## Success criteria

1. `python starter.py` runs without raising `NotImplementedError`,
   prints an outcome count for `blocked_medical_advice`, and produces
   a `medical_advice_blocked` key on every row's `guardrail` dict.
2. The "guardrail trips per day" panel on `dashboard.html` shows your
   new category. Day 12 should be visibly the tallest bar for that
   colour.
3. Your check fires on at least 30 of the 36 medical-completion rows
   and on zero of the non-medical rows. (Run the snippet in the Hints
   section to grade yourself.)
4. `SAFETY_DECISION.md` defends three choices: chain order,
   fail-closed/fail-open, and the limits of your check. A reader who
   hasn't seen the code should be able to predict the chain's
   behaviour from your writeup.

## Hints

- **Where to put the check.** Most teams put content-safety checks
  *after* PII, on the theory that PII-laden text is already going to
  be blocked and there's no point running every other check on it. A
  reasonable counter-argument: if you ever turn off the PII block but
  keep auditing, you still want medical-advice classification.
- **Keyword list.** Look at the 6 medical completions in the
  `TICKETS` table. They share words like "ibuprofen", "ER", "mg",
  "Tylenol", "antifungal", "antidepressant", "doctor". A list of 10–15
  words covers the lot. This is a *terrible* production check; it's a
  fine teaching check.
- **Self-grading snippet.** Drop this into a REPL after running your
  starter. Truth is decided from the **prompt** (the user's question),
  not the completion — that way your check (which reads completions)
  and the grading oracle don't circle each other.

  ```python
  import json
  rows = [json.loads(l) for l in open("llm_calls.ndjson")]
  truth_kw = ["fever", "chest pain", "ibuprofen", "antidepressant",
              "Tylenol", "rash", "ringworm"]
  medical_truth = [r for r in rows if any(k in r["prompt"] for k in truth_kw)]
  fired         = [r for r in rows if r["outcome"] == "blocked_medical_advice"]
  print("medical rows in data:", len(medical_truth))
  print("rows your check blocked:", len(fired))
  print("misses:", sum(1 for r in medical_truth
                       if r["outcome"] != "blocked_medical_advice"))
  print("false positives:", sum(1 for r in fired if r not in medical_truth))
  ```

  Aim for ≤ 6 misses and ≤ 2 false positives.

## Common pitfalls

- **Editing the schema instead of adding a check.** "I'll just add
  `is_medical_advice: bool` to the JSON the model returns and call it
  done." That conflates structure with safety — every prompt change
  now has to negotiate with the safety team. The point of a separate
  check is the separation.
- **Putting the check before `check_schema`.** Then on a schema-failed
  row the medical check tries to inspect `completion`, which may not
  even contain JSON. Order the chain so structural validation goes
  first; semantic checks operate on validated content.
- **Wiring the check but forgetting `call["guardrail"]["medical_advice_blocked"] = False`
  on the miss path.** Your dashboard might still work, but downstream
  code that expects every guardrail key on every row will start
  raising `KeyError` in production. Pick a default and apply it on
  every row.
- **Patching the dashboard but not regenerating the data.** You'll
  see the bucket appear on the chart but with zero rows. The order is
  always: edit `starter.py` → `python starter.py` → refresh
  `dashboard.html`.
- **Skipping `SAFETY_DECISION.md`.** Writing one paragraph about
  fail-closed vs fail-open is the actual learning outcome of the
  exercise. The code is the carrier; the rationale is the cargo.

## What this drills

LX-4 is the *content-safety* loop from Slide 21, made tangible:

- A check that lives *outside* the structured-output schema (the
  schema enforces shape; the safety chain enforces content).
- A pluggable pipeline (you added one entry to a list, not a switch
  statement to five files).
- A monitoring panel that *separates* the new category from existing
  ones (the dashboard shows medical, PII, and toxicity as different
  colours, not "blocked").
- A documented fail-closed/fail-open choice with a scenario.

The choice of *medical advice* is incidental — the same exercise
would work for "financial advice", "legal advice", "emergency
language", "child-safety language", etc. What's not incidental is
that a real product has to add categories like this on a quarterly
basis, and the codebase has to make that addition cheap. If your
patch took more than ~30 lines across `starter.py` and
`dashboard.html`, the codebase is fighting you — and that's the
deeper lesson.

## What's out of scope

- **A real classifier or LLM judge.** A keyword list is enough for
  the exercise. In production the same `check_medical_advice` slot
  could call out to a model — same shape, different implementation.
- **Action policy beyond "block".** Demo 4 collapses everything into
  outcomes. A real product might *redact* the medical sentences,
  *escalate* to a human, or *let it through with a disclaimer*.
  Discussed on Slide 21; not implemented here.
- **A separate `safety.ndjson` log file.** The exercises.md spec
  mentions one; we keep everything in `llm_calls.ndjson` for
  simplicity. If you want to extract a separate file, it's a
  one-liner over the rows.
