# L10 · Solutions and grading guide

**Instructor-only.** This file is the companion to `exercises.md`. For each exercise it gives:

- A **model answer** — not always the only right answer, but a defensible one to anchor grading.
- **What to look for** when reading student responses — the concepts we actually care about.
- **Common wrong answers** and how to respond in the moment (for in-class) or in feedback (for labs).
- For code exercises, a **reference implementation sketch** — focused on the bits that matter, not a full copy-paste repo.

Distribute only to graders; do not share with students before the week of the exercise.

---

## Part 1 · In-class exercise solutions

### IC-1 · Pick the primitive · solution

**Model answer.**

1. Empty list is a caller bug → **`assert len(xs) > 0`**. Internal invariant, should never trigger in correct code.
2. Empty list is a normal business case ("no orders yet") → **return an empty result, or raise a typed business exception** the caller handles. Never `assert`.
3. Record for later analysis → **`log.info("served", extra={...})`**. Side channel, no control-flow impact.
4. Wrong shape halfway through → **`log.error(...)` then `raise`**. Log so the operator has context, raise so the batch aborts.

**What to look for.** The load-bearing distinction is (a) `assert` = invariant (code bug), vs (b) raise = expected exceptional (world state), vs (c) log = record-without-changing-flow. Students who say "I'd log and assert" for (1) are close enough; "I'd assert" for (2) is the misconception to correct.

**Common wrong answers.**

- *"`assert` for user input validation."* → Classic mistake. Walk through: in production with `python -O`, asserts are stripped. If security depends on it, it's gone. Always raise.
- *"`log.error` + `assert`"* for (4) → Over-engineered; `log.error` alone won't stop the batch.

---

### IC-2 · Read the RED dashboard · solution

**Model answer schema.** One JSON object per event with `{timestamp, endpoint, status_code, latency_ms}` — four fields are sufficient.

If the student describes the computations as "read the JSON lines, bucket by endpoint and minute, then":

- **Rate** → count rows per (endpoint, minute).
- **Errors** → count rows where `status_code >= 400` per (endpoint, minute), divided by rate.
- **p95 latency** → the 95th percentile of `latency_ms` over the rows in each (endpoint, minute) bucket.

Students may express this as pseudocode, a sketch of a `defaultdict` aggregation, or words — all fine. The content we care about is the four-field shape and that each panel is a reduction over those rows.

Bonus field: **`request_id`** — not needed for RED, but needed the moment you want to drill from a suspicious panel down to a specific request. Give credit for mentioning it unprompted.

**What to look for.** Students should realise RED is cheap — four fields. The extra field that matters (request_id) isn't for the dashboard, it's for the drill-down. This is the setup for Slide 7.

**Common wrong answers.**

- *"Include the full request body."* → Privacy foot-gun. Ask "what would you do if GDPR showed up?" Segues nicely into Slides 9-10.
- *"Include user_id."* → Fine if hashed; raw is a problem.

---

### IC-3 · The untraceable request · solution

**Model answer.** Per-service RED aggregates show averages and percentiles. A single 14:03 slow checkout can be lost inside p95s because the user's request was *unusually slow on each of three hops*, but each hop stayed within its own p95. Without a **shared request id** (trace id) propagated across all three services, you can't correlate the user's one request across the three log streams — you're stuck with distributions per service, which hide the path.

**What to look for.** Two ideas in the answer: (a) averages hide individual events, and (b) correlation across services requires a shared key. Both are required for full credit.

**Common wrong answers.**

- *"The logs weren't detailed enough."* → No, they were detailed; the problem is correlation, not verbosity. Redirect.
- *"They should log slower."* → Not wrong but irrelevant to the structural issue.

---

### IC-4 · Which assertion broke? · solution

**Model answer table.**

| Assertion | Cause | Who gets paged | Fix |
| --- | --- | --- | --- |
| `assert isinstance(user_id, int)` | **Code bug** — some caller is passing a string. | On-call engineer. | Patch the caller; add a typed signature. Probably a hotfix. |
| `assert acc >= 0.85` on nightly eval | **World change** — data distribution shifted, or the upstream feature pipeline broke, or the model is stale. | Data/ML on-call. | Investigate drift, retrain, or roll back the last model push. No code change may be needed. |

**What to look for.** Students should separate "the system's internal contract broke" from "the world moved." That's the whole point of Section 2's thesis. Bonus if they mention that the same `assert` *syntax* hides two very different operational stories.

**Common wrong answers.**

- *"Both are code bugs."* → Miss.
- *"Retrain for both."* → Miss — retraining won't fix a type bug.

---

### IC-5 · PII sorting · solution

**Model answer table.**

| Item | In user-facing answer? | In log? | Rationale |
| --- | --- | --- | --- |
| `jane@acme.co` (prompt) | Already there — user supplied it. Fine to echo. | **No raw.** Hash/tokenise. | It's the user's own email, not new info, but centralised logs shouldn't carry raw emails. |
| `order #7431` | Yes — it's what the user asked about. | Yes. | Not PII on its own; operationally useful. |
| `mark@acme.co` (model output) | **Block or redact.** | No. | The model volunteered a third party's email. Privacy violation in the answer itself; also shouldn't be persisted. |

**What to look for.** The decision table must treat "in answer" and "in log" as two independent axes (the whole Slide-17 point). Students who use a single "OK / not OK" column have missed the separation — partial credit only.

**Common wrong answers.**

- *"It's fine, the user's own email is OK."* — True for the answer, but misses the log side of the axis.
- *"Block everything."* — Over-blocks order numbers; product breaks.

---

### IC-6 · Tree vs. rows · solution

**Model answer (3+ questions only the tree can answer).**

1. *Was the search tool call inside `retrieval.agent` the bottleneck of the whole request?* — needs parent/child; flat rows can't tell you whether the search was nested under retrieval or a separate top-level call.
2. *How much of the 4.2s was spent inside retrieval vs. answering?* — needs hierarchy to sum span self-times.
3. *Did `llm.call plan` finish before `retrieval.agent` started, or did they overlap?* — needs the causal order reconstructable from parent ids, not just timestamps.
4. *If we killed the retrieval branch, what's the critical path remaining?* — a tree question.
5. *Which LLM call spawned which tool calls?* — parent/child again.

**What to look for.** Answers must require *parent/child structure*, not just "more detail." If a student's question can be answered by adding another column to the flat log, it doesn't count.

**Common wrong answers.**

- *"What model was used?"* → Can be answered from flat rows. Doesn't count.
- *"What was the latency?"* → Same.

---

### IC-7 · Spot the pathology · solution

Three trees are shown during lecture (ascii). Expected labels:

**Tree A — planner loop.**

```
orchestrator.task [14.1s]
├── llm.call plan [190ms]
├── llm.call plan [180ms]
├── llm.call plan [210ms]
├── llm.call plan [200ms]
└── llm.call plan [170ms]
```

Evidence: the same child step repeats without progressing to a different operation. Shape is tall-and-skinny with no branching into sub-agents or tools.

**Tree B — cascading repair.**

```
orchestrator.task [22s]
└── sub_agent.writer [21s]
    ├── llm.call draft [600ms]
    ├── llm.call repair [650ms]
    │   └── llm.call repair [700ms]
    │       └── llm.call repair [710ms]
    └── ...
```

Evidence: repair depth > 2. Every layer is trying to fix the previous layer's output, so cost and latency explode.

**Tree C — healthy.**

```
orchestrator.task [3.4s]
├── sub_agent.research [1.8s]
│   ├── llm.call [300ms]
│   └── tool.search [1.4s]
└── sub_agent.writer [1.5s]
    └── llm.call [1.4s]
```

Evidence: bounded depth, branching into sub-agents, each sub-agent calls its own LLM/tool, no repeats.

**What to look for.** Students should name the *shape feature* (repetition, depth, fan-out) that gave it away, not just "looks bad." Reward evidence-based reasoning.

**Common wrong answers.**

- *"Tree A is too slow."* → Slowness is a symptom; the shape feature is repetition. Push them there.
- *"Tree B is healthy, it completed."* → Completion hides the pathology. Ask them what cost looks like.

---

## Part 2 · Lab exercise solutions

Each lab solution is a reference sketch, not a full submission. The focus is on the bits we actually grade.

### LX-1 · Extend the logging primitives · solution

**Reference `charge.py` core.**

```python
import json
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

class InsufficientFundsError(Exception):
    pass

@dataclass
class Account:
    account_id: str
    balance: float

def charge(account: Account, amount: float, low_balance_threshold: float = 10.0) -> float:
    assert amount > 0, f"amount must be positive, got {amount}"
    if account.balance < amount:
        log.info(
            "charge rejected",
            extra={"account_id": account.account_id, "amount": amount,
                   "balance": account.balance, "reason": "insufficient_funds"},
        )
        raise InsufficientFundsError(
            f"balance {account.balance} < amount {amount} on account {account.account_id}"
        )
    account.balance -= amount
    log.info(
        "charge ok",
        extra={"account_id": account.account_id, "amount": amount,
               "balance_after": account.balance},
    )
    if account.balance < low_balance_threshold:
        log.warning(
            "low balance after charge",
            extra={"account_id": account.account_id,
                   "balance_after": account.balance,
                   "threshold": low_balance_threshold},
        )
    return account.balance
```

Plus a driver that runs ten calls with one negative-amount (triggers `AssertionError`), two where balance < amount (raises `InsufficientFundsError`), seven valid including one that crosses the low-balance threshold.

JSON formatter (core of what we grade):

```python
class JsonFormatter(logging.Formatter):
    def format(self, record):
        base = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        # merge anything passed via `extra=`
        for k, v in record.__dict__.items():
            if k not in ("args", "msg", "exc_info", "exc_text", "stack_info",
                         "levelname", "levelno", "pathname", "filename",
                         "module", "funcName", "lineno", "name", "created",
                         "msecs", "relativeCreated", "thread", "threadName",
                         "processName", "process"):
                base[k] = v
        return json.dumps(base)
```

**Grading.**

- (1) Correct primitive at each site — `assert` for invariant, `raise` for insufficient funds, `log.info` for success, `log.warning` for the threshold crossing.
- (2) Each log line is a single well-formed JSON object.
- (3) The driver actually produces an `AssertionError`, one `InsufficientFundsError`, and at least one `WARNING`.
- (4) `level=WARNING` vs `level=INFO` actually filters — easy to verify `wc -l` on two runs.

**Common failures.**

- Using `log.error` for insufficient funds (the caller recovered; not an error).
- Using `raise` for negative amounts (it's an invariant; `assert` is right, even though `raise ValueError` is a defensible alternative — accept either with a one-sentence justification).
- Putting string interpolation inside `extra`; breaks the JSON formatter.

---

### LX-2 · Catch the incident earlier · solution

**The incident.** Demo 2 injects 15 minutes of elevated 500s on `/checkout` starting at minute 347 of the synthetic day. The existing error-rate panel catches it at ~minute 349-350 (threshold = 2% sustained for 2 min).

**A leading signal.** The latency p95 on the upstream `POST /checkout/validate-card` call climbs starting at **minute 343**, ~6 minutes before 500s become visible. Why? The injected failure is a timeout cascade: the card-validation dependency gets slow, `/checkout` retries, retries time out, user sees a 500.

**Reference panel.**

- Metric: `p95(latency_ms)` for `endpoint = /checkout/validate-card`, 1-minute window.
- Alert rule: **p95 > 800 ms sustained for 3 minutes**, evaluated every minute.
- Justification: the upstream latency climbs *before* retries fail. Catches the incident ~5 minutes earlier.

**Grading.**

- (1) Panel computes only from `logs.ndjson` — no new fields fabricated.
- (2) The student's rule, when applied to the data, fires at least 2 min before the error-rate panel would. (Graders: a tiny check script is in `LX2_check.py`.)
- (3) Threshold and window are stated explicitly.

**Common failures.**

- Picking a lagging signal (overall error rate is lagging; alerting on it earlier just gives false positives).
- "Alert on any spike" — too vague, graders can't check it.

---

### LX-3 · Hung, crashed, or drifting? · solution

**Reference triage table** — for the ten scenarios shipped in `scenarios/`.

| Run | Classification | Log line that gave it away | Action |
| --- | --- | --- | --- |
| run_01 | HEALTHY | `"status": "SUCCEEDED", "holdout_acc": 0.89` | Nothing |
| run_02 | HUNG | `"last_heartbeat_at"` is 18 min old; last log: `"data_loader: waiting on shard 7"` | Fix the corrupt shard, then restart |
| run_03 | CRASHED (OOM) | `"error_kind": "OOM"`; `"RuntimeError: CUDA out of memory"` | Restart with smaller batch |
| run_04 | CRASHED (NaN loss) | `"loss: nan at step 412"` | Fix code: inspect for divide-by-zero or unstable initialisation |
| run_05 | CRASHED (SchemaMismatch) | `"KeyError: 'purchase_amount_usd'"` — column was renamed upstream | Coordinate with upstream team, update feature spec, then restart |
| run_06 | RUNAWAY | Duration 3.4× rolling median; still running | Investigate before it becomes a crash; often an infinite loop |
| run_07 | DRIFT (gradual) | Rolling accuracy trending down over 48h in prediction stream | Refresh training data, retrain |
| run_08 | DRIFT (sudden) | Rolling accuracy drop coincides with upstream pipeline deploy | Rollback upstream; do *not* retrain yet |
| run_09 | HIDDEN-REGRESSION | Holdout acc = 0.91 (passes); production acc = 0.72 | Refresh holdout set; investigate why holdout doesn't represent prod |
| run_10 | HEALTHY | `"status": "SUCCEEDED"` | Nothing |

**Assertion for the hidden regression case.**

```python
# Runs in CI against a freshly sampled-from-production holdout.
prod_sample = sample_production_traffic(n=500, lookback_days=7)
preds = model.predict(prod_sample.X)
prod_acc = accuracy_score(prod_sample.y, preds)
assert prod_acc >= baseline_acc - 0.03, (
    f"quality regression on production-representative sample: "
    f"prod_acc={prod_acc:.3f}, baseline={baseline_acc:.3f}"
)
```

**Grading.**

- (1) ≥ 8 correct classifications out of 10.
- (2) Evidence is a specific log line, not paraphrase.
- (3) Action matches cause: restart only when restart fixes it; schema mismatch gets a coordination step.
- (4) Assertion fails on `run_09`'s production stream and passes on the healthy ones.

**Common failures.**

- "Restart it" for run_02 without reading the log. Walks right back into the shard problem.
- "Retrain" for run_08. Retraining on broken upstream data makes things worse; rollback first.
- Hidden-regression case missed: holdout passes, so they mark it HEALTHY.

---

### LX-4 · A new safety category · solution

**Design discussion.** `medical_advice` is specifically chosen because it's one of those categories where (a) detection is noisy, (b) false-negatives are very costly, (c) over-blocking breaks legitimate uses (someone asking about dosage timing for their own prescription). This forces a fail-open-vs-closed conversation with real trade-offs.

**Reference check** (keyword baseline acceptable for the lab):

```python
MEDICAL_MARKERS = {
    "diagnose", "prescribe", "dosage", "mg", "mcg",
    "ssri", "beta blocker", "chemo", "insulin",
}

def is_medical_advice(text: str) -> bool:
    t = text.lower()
    return sum(m in t for m in MEDICAL_MARKERS) >= 2
```

Students who use an LLM-judge or a real classifier (e.g., a Hugging Face zero-shot) get full credit as long as the interface is the same.

**Integration points.**

1. Runs *after* Pydantic validation in `llm_calls.py`. If structural fails, don't waste cycles on content safety.
2. On trip, append to `safety.ndjson`: `{"request_id": ..., "category": "medical_advice", "marker_count": 3, "completion_snippet": ...}`.
3. Dashboard panel-4 gets a new stacked-bar slice. Panel-5 (guardrail outcomes) gets a `medical_advice_blocked` or `medical_advice_warned` bucket depending on the fail-closed/open choice.

**Reference fail-closed/open decision.** A defensible answer either way; what matters is the reasoning.

- *Fail-closed* memo: "Medical misadvice is high-severity, low-reversibility. Over-blocking is recoverable (user rephrases); bad medical advice may not be. We fail-closed and return a canned 'please consult a professional' response on trip."
- *Fail-open* memo: "Our user base is medical professionals using the tool for drug-interaction lookups. Fail-closed would break the core use case. We fail-open and flag for review — a nightly human pass audits flagged responses."

**Grading.**

- (1) Check runs after structural validation — verified by ordering.
- (2) `safety.ndjson` has the new rows and they're queryable independently.
- (3) Dashboard updates visually.
- (4) The fail-open/closed choice is defended with a specific user scenario — not "because safety."

**Common failures.**

- Collapsing the new check into the Pydantic model. That conflates structural and semantic (the whole Slide-17 point).
- No written rationale for fail-open vs closed.

---

### LX-5 · Instrument a RAG function · solution

**Reference instrumentation.**

```python
from opentelemetry import trace

tracer = trace.get_tracer("rag")

def rag_answer(question: str) -> str:
    with tracer.start_as_current_span("rag.answer") as root:
        root.set_attribute("rag.question_length", len(question))

        with tracer.start_as_current_span("rag.retrieval") as retr:
            chunks = retrieve(question, k=5)
            retr.set_attribute("rag.k", 5)
            retr.set_attribute("rag.n_chunks", len(chunks))

        prompt = build_prompt(question, chunks)

        with tracer.start_as_current_span("llm.call") as llm_span:
            llm_span.set_attribute("gen_ai.operation.name", "chat")
            llm_span.set_attribute("gen_ai.request.model", "gpt-4o-mini")
            response = llm.complete(prompt)
            llm_span.set_attribute("gen_ai.usage.input_tokens", response.in_tokens)
            llm_span.set_attribute("gen_ai.usage.output_tokens", response.out_tokens)

        return response.text
```

**Grading.**

- (1) Exactly three spans with correct parent/child: `rag.answer` → `rag.retrieval`, `rag.answer` → `llm.call`.
- (2) GenAI semconv names used on the LLM span (not home-grown names like `model_name`).
- (3) Span durations roughly sum to wallclock (sanity check — allow 10% for overhead).
- (4) Resulting `spans.ndjson` renders in `trace_viewer.html` without manual edits.

**Common failures.**

- Putting `rag.retrieval` at top level next to `rag.answer` instead of inside it (lost parent).
- Using custom attribute names (`model`, `tokens_in`) — point to Slide 21.
- Instrumenting inside `retrieve()` and `llm.complete()` internals — not wrong but goes beyond the ask and often breaks the tree in the shipped lab fixtures.

---

### LX-6 · Diagnose the multi-agent run · solution

**Instructor packet.** Three `spans.ndjson` files, generated with:

- File A: `multi_agent.py --failure-mode=planner_loop`
- File B: `multi_agent.py --failure-mode=cascading_repair`
- File C: `multi_agent.py` (healthy path)

Students are NOT told which is which.

**Reference diagnoses.**

| File | Label | Shape evidence | Task-level assertion | Coordination assertion |
| --- | --- | --- | --- | --- |
| A | Planner loop | 6 consecutive `llm.call plan` spans under `orchestrator.task`, no branching into sub-agents | `assert final_answer_satisfies_intent(question, answer)` via rubric (L7) | `assert planner_call_count <= 3 per request` |
| B | Cascading repair | Repair depth > 2; four `llm.call repair` spans nested inside each other | `assert rubric_score >= threshold` on final output | `assert repair_depth <= 1 per sub_agent` |
| C | Healthy | Bounded depth, branching fan-out, no repeated names at the same level | `assert final_answer_satisfies_intent(...)` (same rubric) | `assert total_step_count <= 8 per request` |

**Grading.**

- (1) At least 2/3 correct labels.
- (2) Evidence is structural — depth, repetition, branching — not "it looks slow."
- (3) Task-level assertion is checkable (rubric-based), not "the answer should be correct" (not checkable).
- (4) Coordination assertion is a concrete bound, not a wish.

**Common failures.**

- Diagnosing by total latency only (B is ~22s but so is a legit deep retrieval task).
- "Planner loop" label for B (it's repair, not re-planning — push them to read the span names).
- Unverifiable assertions like "the agents should cooperate" — push for a concrete bound.

---

### LX-7 · A/B with a decision · solution

**Model analysis.**

Setup:

- Demo 7 data: prompt v2 n≈1000, v3 n≈1000.
- Pass-rate (rubric score ≥ threshold): v2 = 78.4%, v3 = 81.2%.
- 95% bootstrap CI on the difference (v3 − v2): [+0.6 pp, +4.9 pp].
- Cost: v3 is +7% per request (longer prompts → more input tokens).
- Segmentation by user cohort: three cohorts, difference consistent in two, *v3 is slightly worse on "enterprise"* (−1.2 pp, CI [−3.5, +1.1]).

**Reference decision memo.**

> **Ship v3 to the consumer slice; hold on enterprise.**
>
> Across all traffic, v3 improves pass-rate by +2.8 pp with a 95% CI of [+0.6, +4.9]. The lower bound is above zero, so the effect is unlikely to be noise. Cost is +7% per request, which we judge acceptable given the quality gain.
>
> However, segmented by cohort, v3 is flat-to-slightly-negative on enterprise (−1.2 pp, CI crosses zero). We therefore recommend canary-ing v3 on the consumer slice first (about 65% of traffic) and running a dedicated test on enterprise prompts before expanding.
>
> We'd reverse this recommendation if: (a) a week of canary data moves the consumer CI lower bound below zero, or (b) enterprise loss widens with a CI that excludes zero, or (c) the cost delta grows past +12%.

**Grading.**

- (1) A 95% CI is reported and used, not a bare point estimate.
- (2) Segmentation result is surfaced and influences the decision (not just computed).
- (3) Memo takes a position — "ship," "don't ship," or a sliced-ship.
- (4) Pre-registered unchanged-mind criteria are specific and checkable.

**Common failures.**

- "Ship v3, it's better" from a point estimate. Most common failure; flag and send back.
- Running all operations but writing a memo that doesn't take a position.
- Bootstrap code that confuses "within-group CI" with "CI of the difference."

---

## Part 3 · Homework grading guide — "Make the Q&A bot observable"

This section is for the grader. It's organised around the six rubric cells from `exercises.md`.

### What a 10/10 submission looks like

A 10/10 submission has:

- **Logging (15/15).** Every LLM call produces a single structured JSON line matching the Slide-15 schema. `prompt_version` is present and used as a field, not a magic string in a comment. No raw emails/phones/tokens in logs — checked with a grep over a 50-request run. One privacy pattern from Slide 10 is applied (commonly: hash-then-log for user_id) and named in `MONITORING.md`.
- **Tracing (15/15).** One trace per request. Parent `qa.request` span; child spans for retrieval (if any) and each LLM call. GenAI semconv attribute names on the LLM span (`gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.operation.name`). File exporter writes `spans.ndjson` that opens in `trace_viewer.html` unmodified.
- **Dashboard (15/15).** Reads the same log file. Four panels: p95 latency per prompt version, failure rate, cost per request, and a quality signal. The quality signal is non-trivial: sampled rubric score with a 24-hour rolling mean, or a proxy like answer-length-distribution-vs-baseline — not just "count of OK responses."
- **CI gate (20/20).** `pytest tests/test_quality.py` loads the 20-item golden set, runs the bot, judges with the provided rubric, and compares pass-rate to the last release's pass-rate. The comparison uses a 95% CI on the difference (bootstrap is fine) — *not* "mean is lower, fail." Regression threshold is pre-registered in the repo. A student who passes the CI gate but has the wrong statistical framing gets capped at 14/20.
- **Incident detection (15/15).** The grader's harness patches in one of the three injected failures (see below). The student's monitoring must catch it. "Catch" means: either an assertion fires with a useful message, or a dashboard panel moves outside an alerting rule that the student had defined in advance.
- **Incident review (10/10).** Uses the Slide-33 structure. Correctly diagnoses the failure as a distribution shift, code bug, or silent-guardrail incident (depending on which was injected). Names the specific telemetry that caught it (or the specific telemetry that *should* have caught it and didn't).
- **Decisions memo (10/10).** Answers all three prompts: what they monitor, what they deliberately don't, biggest blind spot. Takes positions. Names trade-offs. Not marketing copy.

### Injected failure bank

Maintain three, rotate yearly. Each is a small patch applied to the student's repo before the grader harness runs.

**INJ-1 · Stuck call.** Patch adds a 30-second sleep to the LLM client on every tenth request. Catches: p95 latency panel, per-call latency assertion, timeout-rate metric. A student whose dashboard has *only* mean latency misses this.

**INJ-2 · Prompt regression.** Patch swaps the bot's system prompt for a deliberately degraded version (removes the "cite your sources" instruction). Catches: quality signal on dashboard if sampled rubric is in place; CI gate if run pre-merge; failure rate if rubric trips schema validation. A student whose only quality signal is "did it return 200?" misses this — this is the failure that separates B submissions from A submissions.

**INJ-3 · Safety leak.** Patch adds a pre-prompt line that coaxes the model to echo user-supplied email addresses in the answer. Catches: content-safety panel if the student added PII-in-answer detection. A student with only structural validation misses this — this is the failure that separates a technically-correct submission from one that has understood Slide 17.

### Graders' checklist (fast path)

1. `cd submission && git log --oneline | head -5` — is this a real repo, or a last-minute zip-dump?
2. `bash run_all.sh` — the student's own runner. If it doesn't work, stop; contact the student.
3. Open `logs.ndjson` in the lab's `log_viewer.html` — does the schema match Slide 15?
4. Open `spans.ndjson` in `trace_viewer.html` — does the trace tree render with parent/child?
5. Open `dashboard.html` — four panels, including a non-trivial quality signal?
6. `pytest -q` — does the CI gate run green on the baseline?
7. Apply the harness patch. Re-run. Did the monitoring catch it?
8. Read `MONITORING.md` and the incident review. Positions taken?

Budget ~30 min per submission on average, more for submissions that need a back-and-forth.

### Academic-honesty watchouts

- Copy-pasted `MONITORING.md` templates from a public repo. Easy to spot: too-polished prose, no references to the specific bot.
- Dashboards that render but pull from a sample dataset rather than the student's own run. Check that `logs.ndjson` contains the student's actual runs — timestamps and request counts should match what the bot produced.
- Using an LLM to write the whole repo is fine and encouraged for the boilerplate. Using it to write `MONITORING.md` without thinking is obvious and scores poorly.

---

## Part 4 · Stretch exercise notes

### SX-1 · Build your own log viewer

No single model answer. Instructor review: is the viewer functional? Did the student track their time honestly? A one-paragraph reflection hitting on "building a viewer turned out to be about X hours, and most of that was deciding which columns to show" is ideal — shows they've internalised the point.

### SX-2 · Budget envelopes

Look for: (a) per-cohort budget state that survives process restarts (file or simple sqlite), (b) circuit-breaker logic separate from the model-switch logic, (c) the dashboard actually shows when the breaker tripped. Common miss: the budget resets every run, so the breaker never trips during grading.

### SX-3 · OTel GenAI semconv memo

No single correct answer. Look for: (a) a specific named attribute, (b) a concrete reason rooted in a use case, (c) an honest counter-argument. Reject memos that don't engage with the actual spec.

### SX-4 · Multi-tenant API design

Rubric: (1) clear per-tenant vs. global vs. per-model separation; (2) noisy-neighbour handling (rate limiting, sharded dashboards); (3) privacy lines called out explicitly (tenant A must not see tenant B's prompts even in logs); (4) something hard and specific the student got right or honestly declined to solve.

### SX-5 · Phoenix verdict

Look for a verdict that actually takes a position. "Phoenix has more features" is a non-answer. "Home-grown viewer is enough until you have multiple developers debugging different runs simultaneously, then shared-state matters" — that's a thesis.

---

## Notes on using this file

- **Don't over-prescribe.** These are *model* answers, not *the* answers. A student whose reasoning is internally consistent and lands on a different conclusion should get full credit.
- **When a student is clearly wrong, say so clearly.** "Not quite — walk through what happens under `python -O`" beats "consider revisiting this."
- **Track which common failures actually show up** this cohort. The "common failures" lists above are hypotheses — refine them year over year.
