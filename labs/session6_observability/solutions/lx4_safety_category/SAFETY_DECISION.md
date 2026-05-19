# LX-4 · SAFETY_DECISION (reference)

## Order in the chain

`check_medical_advice` runs **after** `check_schema` and
`check_toxicity`, and **before** `check_pii`.

- **After schema / toxicity**: those checks are cheaper (schema parse
  is already needed; toxicity is a word-list). A row that would be
  rejected for either of those reasons should carry *that* label, not
  be re-categorised. In particular, a schema-failed row doesn't have a
  valid completion string to search, so running the medical check on
  it would be meaningless.
- **Before PII**: medical-advice text often also contains phone
  numbers ("call your doctor at 555-0123") or clinic names. If we ran
  PII first, the row would be tagged `blocked_pii` and the
  medical-operations on-call would never hear about it. The medical
  taxonomy is more actionable for the team that owns this problem, so
  it wins the tie.

## Fail-closed vs fail-open

**Fail-closed.** The product cost of blocking a non-medical reply
that happened to contain the word "ibuprofen" is a support round-trip.
The product cost of letting a real medical-advice reply through is a
prescription-adjacent mistake that shows up on the CEO's desk. The
asymmetry is three to four orders of magnitude. When the asymmetry is
that skewed, fail-closed is the default and the tuning loop happens
against the monitoring dashboard, not against user reports.

When I would fail-open: a debug or internal-testing mode where the
completion is being inspected by a human anyway. We don't have that
mode in this codebase yet — when we do, the switch is one argument on
`run_pipeline()`.

## What the check catches and what it misses

- **Catches:** any completion that contains at least one word from the
  list (drug names, care directives, clinical terminology). On this
  corpus that fires on 30 of 30 medical-completion rows and 0 of the
  1,470 non-medical rows. Zero false positives is luck of the corpus
  — a real deploy would expect a small non-zero rate and would want
  the dashboard visible to tune it.
- **Misses, by construction:** advice that sidesteps the exact
  vocabulary. A completion that says "take two of the little white
  pills every four hours" has zero keywords and would sail through.
  A real deploy would move to either a classifier (trained on a
  medical-vs-not corpus) or an LLM judge ("is this medical advice,
  yes/no, one word"). Either one slots into the same chain position
  with no code changes outside `check_medical_advice`.

That's the payoff of the pluggable chain: the *integration work*
(order, fail-closed, dashboard bucket) is shared across every future
check, and the *technique work* is local to one function.
