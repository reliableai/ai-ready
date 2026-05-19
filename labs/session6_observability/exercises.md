# L10 · Exercises and assignments

Companion to `slides_outline.md` and `demos_plan.md`. Three tiers, designed to be used in this order during the week:

1. **In-class exercises** — short (2-5 min), done live during lecture, solo or pair. Purpose: force students to commit to an answer before we give ours.
2. **Lab exercises** — one per demo, done during the lab session. 20-45 min each; code-producing but scoped.
3. **Homework assignment — Instrument the Q&A bot** — the week's capstone, due at the start of Week 6. Builds on the Week-4 Q&A-bot starter; takes 4-6 hours.
4. **Stretch exercises** — optional, for students who want to go further or have a final-project hook.

Each exercise is stated with **purpose** (what concept it drills) and **learning outcome** (what the student can do by the end), then task, deliverables, rubric. Time estimates and slide/demo anchors are called out at the top of each entry.

---

## Grading breakdown (suggested)

| Component         | Weight | Form                                           |
| ----------------- | ------ | ---------------------------------------------- |
| In-class exercises | 0%    | Formative; credit-for-participation at most.   |
| Lab exercises (7) | 30%    | Checked off in lab; rubric per exercise.       |
| Homework assignment | 60% | Submitted repo + short memo; rubric below.     |
| Stretch           | 10% bonus | Optional; can replace one lab exercise.   |

---

## Part 1 · In-class exercises

Seven quick drills, each tied to a specific slide. Use as a pause-and-check; ~3 min solo, then 1 min discussion.

### IC-1 · Pick the primitive  · after Slide 5

**Purpose.** Lock in the distinction between `assert`, exceptions, and `logging` before we build anything on top of it.

**Learning outcome.** Student can match each control-flow primitive to the situation it fits and justify the choice in one sentence.

**Task.** For each of the following, say which primitive (or combination) you'd use and why — in one line:

1. A function expects a non-empty list; an empty list means the caller has a bug.
2. A function expects a non-empty list; an empty list is possible when the user has no orders yet.
3. You want to keep a record of which prompt version served each request, for analysis next week.
4. Halfway through a long batch job you detect that the output shape is wrong; the rest of the batch should abort and an operator should know.

**Deliverable.** Four one-line answers.

**Rubric.** Full credit if (1) `assert`, (2) raise/except, (3) `log.info`, (4) `log.error` + raise — or any answer with defensible reasoning.

---

### IC-2 · Read the RED dashboard  · after Slide 6

**Purpose.** Make students work backwards from a dashboard shape to what the underlying log stream must contain.

**Learning outcome.** Student can name the minimum fields a log event must carry for each RED panel to be computable.

**Task.** Here are three panels:

- Requests/sec per endpoint.
- Error rate per endpoint per minute.
- p95 latency per endpoint.

What fields must each log event carry? What's the smallest common shape?

**Deliverable.** A 4-5-field log schema on the board.

**Rubric.** Must include at minimum: `timestamp`, `endpoint`, `status_code` (or `ok`), `latency_ms`. Bonus: `request_id`.

---

### IC-3 · The untraceable request  · after Slide 7

**Purpose.** Prime the motivation for traces by exposing what flat logs can't answer.

**Learning outcome.** Student can articulate, unaided, that without a shared id per request, you can't reconstruct which downstream calls belonged to which user request.

**Task.** You have three services (API / feature-store / model). Each logs its own RED. A user reports a slow checkout at 14:03. You open all three dashboards and every one shows green p95s around that time. Why can the user still have had a slow request? What's the single field that would let you answer the question?

**Deliverable.** One paragraph naming the concept ("shared request id / trace id") and why averages hide the event.

**Rubric.** Credit for naming the concept *and* explaining why it's invisible in per-service aggregates.

---

### IC-4 · Which assertion broke?  · after Slide 13

**Purpose.** Make the link between the Slide-5 code assertion and the Slide-13 statistical assertion explicit.

**Learning outcome.** Student can explain how a single failing `assert acc >= 0.85` differs — in cause, frequency, and response — from a single failing `assert isinstance(x, int)`.

**Task.** Both of these fire in prod:

- `assert isinstance(user_id, int)` fires once, on one request.
- `assert acc >= 0.85` fires on the nightly eval job.

For each, answer: (a) is this a bug in the code or a change in the world? (b) who gets paged? (c) what's the fix?

**Deliverable.** Two rows in a 3-column table.

**Rubric.** Correct attribution: (a) code bug vs. data/world change; (c) patch code vs. retrain/rollback prompt.

---

### IC-5 · PII sorting  · after Slide 17

**Purpose.** Force students to confront that PII-in-log and PII-in-answer are separate problems with separate knobs.

**Learning outcome.** Student can decide for each PII appearance whether to redact in the log, block in the response, both, or neither.

**Task.** A support-bot exchange:

- *User:* "My account is jane@acme.co — charge hasn't refunded yet."
- *Bot:* "I can see order #7431 for jane@acme.co, refund processed 2026-04-10. For future reference you can reach your account manager at mark@acme.co."

For each of `jane@acme.co` (prompt), `order #7431`, `mark@acme.co` (output): should it appear in the user-facing answer? should it appear in the log? justify.

**Deliverable.** A 3-row decision table.

**Rubric.** Credit for separating "in the answer" from "in the log" and treating them as independent decisions.

---

### IC-6 · Tree vs. rows  · after Slide 20

**Purpose.** Make the expressive-power gap between flat logs and traces visceral.

**Learning outcome.** Student can name at least three questions answerable from the tree that the flat log cannot answer at all.

**Task.** Given the Slide-20 ASCII trace and an equivalent set of flat log rows (with `request_id` but no parent id), list questions you can answer from the tree but **not** the flat log.

**Deliverable.** 3+ questions.

**Rubric.** Credit for questions that genuinely require parent/child info — e.g., "Did the retrieval agent's search call block the answer call?", "What fraction of the 4.2s was spent inside retrieval vs. answering?", "Was plan called before or after retrieval as an ordering?", etc.

---

### IC-7 · Spot the pathology  · after Slide 26

**Purpose.** Make multi-agent failure modes recognisable as *shapes*, not as vocabulary.

**Learning outcome.** Student can look at a span tree and name the failure mode.

**Task.** Three small ASCII trees are shown. For each, identify the pathology (planner loop / cascading repair / role confusion / healthy) and say what evidence in the shape told you.

**Deliverable.** Three labels with one-sentence justifications.

**Rubric.** Full credit for correct labels + correct evidence; partial for correct label alone.

---

## Part 2 · Lab exercises

One per demo, completed during the lab session with the demo code as starting point. Each exercise takes 20-45 min. Students submit a small diff + a short written answer.

### LX-1 · Extend the logging primitives  · pairs with Demo 1

**Purpose.** Force students to write and run a real logging-bearing function from scratch, picking the right primitive at each step.

**Learning outcome.** Student can (a) instrument a function with `assert`, exceptions, and `logging` without reaching for examples; (b) configure level filtering and show the effect; (c) produce a JSON log line their teammates can read.

**Task.** Starting from Demo 1, write a `charge(account_id, amount)` function that:

1. Asserts `amount > 0` (invariant).
2. Raises `InsufficientFundsError` when the balance is too low (expected exceptional).
3. Logs `INFO` on success with `account_id`, `amount`, `balance_after`.
4. Logs `WARNING` when the balance drops below a configurable threshold after the charge.

Then write a driver that calls `charge` ten times with a mix of inputs — one invariant violation, two insufficient-funds, seven valid — and produces a log file.

**Deliverable.** `charge.py` + its produced `charge.log` (JSON lines).

**Rubric.** (1) Correct primitive at each site · (2) Log shape matches schema from Demo 1 · (3) Driver exercises all three primitives · (4) Log filter: running with `level=WARNING` produces strictly fewer lines than `level=INFO`.

**Time.** ~25 min.

---

### LX-2 · Catch the incident earlier  · pairs with Demo 2

**Purpose.** Turn students into dashboard designers — if they'd had the right panels, the injected incident in Demo 2 would have been caught 10 minutes earlier.

**Learning outcome.** Student can (a) identify an alertable leading indicator distinct from the already-monitored RED trio; (b) add it as a dashboard panel over the same `logs.ndjson`.

**Task.** Using Demo 2's `logs.ndjson`, add one new panel that would have flagged the `/checkout` incident sooner than the existing error-rate panel. Hint: latency of upstream calls, 95th percentile of a specific endpoint, a ratio — something leading.

**Deliverable.** `dashboard.html` patched with the new panel + a one-paragraph note on what signal it uses, why it leads, and what the alert rule should be.

**Rubric.** (1) Panel computes from `logs.ndjson`, no new data source · (2) Signal is demonstrably leading on the provided incident (earlier threshold crossing) · (3) Alert rule is stated precisely (threshold, window, evaluation period).

**Time.** ~30 min.

---

### LX-3 · Hung, crashed, or drifting?  · pairs with Demo 3

**Purpose.** Make students do the triage that Demo 3's dashboard makes *possible* — reading the board and prescribing the right response.

**Learning outcome.** Student can look at a training-run board + error-log tail and decide, per run, whether to restart, fix code, or retrain on fresh data.

**Task.** Demo 3 ships a `scenarios/` folder with ten pre-generated runs covering all six failure modes. For each run:

1. Classify it (HUNG / CRASHED / RUNAWAY / DRIFT / HEALTHY / HIDDEN-REGRESSION).
2. Give the single log line that gave it away.
3. Prescribe the next action (restart-as-is / restart-with-smaller-batch / fix-code-then-restart / refresh-holdout-set / rollback-model / nothing).

Then write an assertion (Slide-13 shape) that would have caught the hidden-regression case in CI.

**Deliverable.** `triage.md` with a 10-row table + the new assertion in `assertions.py`.

**Rubric.** (1) 8+ correct classifications · (2) Evidence is a real log line for each · (3) Action is defensible · (4) Assertion fails on the bad run and passes on the others.

**Time.** ~40 min.

---

### LX-4 · A new safety category  · pairs with Demo 4

**Purpose.** Exercise the separation from Slide 17 (structural validity vs. content safety) by adding a *new* content-safety check end-to-end — classifier, dashboard panel, guardrail trip log.

**Learning outcome.** Student can (a) add a new check without touching the Pydantic schema — keeping structural and semantic concerns separate; (b) wire its output through to both the raw viewer and the aggregation dashboard; (c) decide fail-closed vs. fail-open and justify it.

**Task.** Add a `medical_advice` content-safety check to Demo 4. Define it however you want (keyword list, small classifier, LLM judge — the method isn't the point). The check must:

1. Run *after* structural validation.
2. Append a `safety.ndjson` row with `category="medical_advice"` on trips.
3. Show up as a new bar in Panel 4 and a new bucket in the guardrail-outcomes panel.
4. Have a documented fail-closed / fail-open decision with a one-paragraph rationale.

**Deliverable.** Patched `llm_calls.py` + `dashboard.html` + `SAFETY_DECISION.md`.

**Rubric.** (1) Check runs in the right order · (2) Structural and semantic outcomes remain separately queryable · (3) Dashboard shows the new category · (4) Fail-open/closed choice is defended with a scenario.

**Time.** ~35 min.

---

### LX-5 · Instrument a RAG function  · pairs with Demo 5

**Purpose.** Put students through the mechanical exercise of going from un-instrumented code to properly-spanned OTel output with GenAI semconv names.

**Learning outcome.** Student can add OTel spans to an existing function, set the correct GenAI attributes, and read the resulting trace in the viewer.

**Task.** A provided `rag_answer(question)` function (uninstrumented) does: retrieve top-k chunks → build prompt → LLM call → return answer. Instrument it so that one call produces a trace with a root `rag.answer` span, child spans for retrieval and the LLM call, and the GenAI semconv attributes (`gen_ai.request.model`, input/output tokens, operation.name) set on the LLM span.

Verify the resulting trace renders correctly in Demo 5's `trace_viewer.html`.

**Deliverable.** Instrumented `rag_answer.py` + a screenshot (or exported HTML) of the resulting trace in the viewer.

**Rubric.** (1) Three spans, correct parent/child · (2) GenAI attributes on the LLM span · (3) Timings sum to the wallclock (within 10%) · (4) Viewer renders it without manual editing.

**Time.** ~30 min.

---

### LX-6 · Diagnose the multi-agent run  · pairs with Demo 6

**Purpose.** Translate Section-04 vocabulary into reading trace shapes.

**Learning outcome.** Student can diagnose a multi-agent failure from the trace alone — without looking at the scenario flag used to generate it.

**Task.** The instructor provides three `spans.ndjson` files generated with `multi_agent.py` and *without* telling the students which failure mode each one was run with. For each file, open it in the viewer and submit:

1. The failure mode (or "healthy").
2. The shape evidence (e.g., "depth > 6, three retries of the same tool call").
3. One task-level and one coordination assertion (from Slide 25) that would have caught this earlier.

**Deliverable.** `diagnoses.md` with three sections.

**Rubric.** (1) 2/3 correct labels · (2) Evidence is structural, not just "it looks bad" · (3) Assertions are specific and checkable — not "the answer should be correct."

**Time.** ~35 min.

---

### LX-7 · A/B with a decision  · pairs with Demo 7

**Purpose.** Make students produce the thing that actually matters to a PM — a written decision, not just a number.

**Learning outcome.** Student can (a) run the five Slide-31 operations on real data; (b) produce a one-paragraph memo that takes a position, names the CI, and states what they'd need to see to change their mind.

**Task.** Using the combined `llm_calls.ndjson` + `task_judgments.ndjson` from Demo 7, answer: *"Should we ship prompt v3?"* Run:

- A/B on pass-rate with 95% CI.
- Segmentation by user cohort — does v3 help evenly?
- Drill-down: pull the 20 worst traces for v3 and read them.
- Cost delta per request.

Write a one-paragraph decision memo: *ship / don't ship / ship-to-a-slice,* with the numbers and caveats.

**Deliverable.** `analysis.py` with your code + `decision_memo.md` (≤ 250 words).

**Rubric.** (1) CI is reported, not a bare point estimate · (2) Segmentation surfaces or rules out a cohort issue · (3) Memo takes a position · (4) Memo names what would change the decision (pre-registered).

**Time.** ~45 min.

---

## Part 3 · Homework assignment — Instrument the Q&A bot

**Title.** *"Make the Q&A bot observable."*

**Purpose.** Force students to integrate every layer from this lecture into one working system — not as isolated pieces but as a coherent stack where the logs, traces, dashboard, CI gate, and analysis all read from the same structured data.

**Learning outcome.** By the end of this assignment a student can:

1. Instrument an existing LLM-powered service with structured per-call logging that conforms to the Slide-15 schema.
2. Instrument the same service with OTel tracing using GenAI semantic conventions.
3. Build (or adapt) an aggregation dashboard that reads the log stream.
4. Write a CI gate using the golden-set judging from L7 plus the CI-of-the-difference framing from L8–L9.
5. Run an end-to-end incident review on a failure the grader injects into their code.
6. Explain, in writing, *what they chose to monitor, why, and what they deliberately chose not to monitor.*

**Starter.** The Q&A bot students built in Week 4 (`hw04_qa_bot/`). If a student missed that week, a reference implementation is provided.

**Required work.**

1. **Structured logging.** Wrap every LLM call in a log event matching the Slide-15 schema. Include prompt, completion, request id, prompt version, tokens, cost, latency, outcome. Apply one privacy pattern from Slide 10 and state which.
2. **Tracing.** Add OTel spans around the request handler, each LLM call, and the retrieval step (if any). Use the GenAI semconv attribute names. Spans must render in Demo 5's viewer.
3. **Dashboard.** An `dashboard.html` over the log file showing at least: p95 latency, failure rate, cost per request, and one quality signal of the student's choice (rubric score sample, length stats, etc.).
4. **CI eval gate.** A `tests/test_quality.py` that loads a 20-item golden set, runs the bot, judges with a provided rubric, and asserts that the pass-rate is not statistically worse than the last release — reported with a 95% CI.
5. **Incident review.** The grader's test harness will patch the bot with one of three injected failures before running. The student's monitoring stack must (a) detect it and (b) produce a 1-page incident review afterwards, in the Slide 33 format.
6. **Decisions memo.** A `MONITORING.md` (≤ 800 words) answering: what do you monitor and why? what did you choose not to monitor and why? what's your biggest blind spot, and what would it take to close it?

**Deliverables.**

- A single repo with clear `README.md` on how to run each layer.
- The four artefacts above.
- The incident-review doc (produced during the grader's harness run).
- The decisions memo.

**Rubric (100 pts).**

| Area | Weight | What we look for |
| ---- | ------ | ---------------- |
| Logging | 15 | Schema conformance; privacy pattern applied; no raw PII; level discipline. |
| Tracing | 15 | Correct parent/child; GenAI semconv names; renders in viewer. |
| Dashboard | 15 | Reads the same file; panels match stated metrics; one non-trivial quality signal. |
| CI gate | 20 | Golden set loaded; rubric judged; CI-based comparison, not point estimate; green/red reliably. |
| Incident detection | 15 | The grader's injected failure is actually caught by the student's assertions/panels. |
| Incident review | 10 | Follows the Slide-33 structure; names distribution shift vs. bug; identifies the silent guardrail. |
| Decisions memo | 10 | Takes positions; names trade-offs; identifies a specific blind spot. |

**Budget.** 4-6 hours of focused work for an average student. **Due.** Start of Week 6, before L11.

---

## Part 4 · Stretch exercises

Optional. Any one can replace one failed/missing lab exercise.

### SX-1 · Build your own log viewer

**Purpose.** Internalise the "building a viewer is almost free today" claim from Demo 4.

**Task.** Pick a log format *not* used in this lab — nginx access logs, systemd journal, your editor's debug log. Build a single-file `viewer.html` with search, filter, and row-expansion. Time yourself honestly.

**Deliverable.** The viewer, a note on elapsed time, and a one-paragraph reflection.

---

### SX-2 · Cost monitoring with budget envelopes

**Purpose.** Go beyond "log the cost" to a real budget-control loop.

**Task.** Extend Demo 4 with a per-user-cohort daily budget. When a cohort exceeds its budget, the bot switches to a cheaper model. Instrument the switch so the dashboard shows it clearly. Write the circuit-breaker rules in code.

---

### SX-3 · Read the OTel GenAI semconv

**Purpose.** Make the standard concrete and form an opinion on it.

**Task.** Read the current GenAI semantic conventions. Pick one attribute you think is missing or poorly named. Write a 300-word memo explaining what it is, why you'd add/rename it, and what a counter-argument from the working group might be.

---

### SX-4 · Design-only: multi-tenant LLM API monitoring

**Purpose.** Design-level reasoning, no coding.

**Task.** You run a B2B LLM API used by 50 enterprise tenants. Design the monitoring stack on paper: what's per-tenant, what's global, what's per-model, how do you handle a noisy tenant, and where do the privacy lines go. 2-3 pages.

---

### SX-5 · Real OTel backend

**Purpose.** See the data in a production-grade UI.

**Task.** Run Demo 5 with `--with-otlp` and a local Phoenix (or Jaeger) instance. Compare what the Phoenix UI surfaces vs. the lab's `trace_viewer.html`. One-paragraph verdict: when is the home-grown viewer enough, when is Phoenix worth it?

---

## Design notes for the instructor

- **Progression.** In-class → lab → homework is deliberately "show me → do with scaffolding → do on your own." Don't skip the in-class exercises; they're where misconceptions surface cheaply.
- **Pairs vs. solo.** In-class and lab exercises work well in pairs. The homework is solo — the grader's injected failure is individual.
- **Graders.** The homework rubric has exactly two subjective cells (memo, incident review); the rest is mechanically checkable against the repo structure and the grader harness. Budget ~30 min/submission.
- **Failure injection.** Maintain three injected failures — one per category (stuck call / prompt regression / safety leak). Rotate each year.
- **Golden set.** Students share a 20-item golden set provided by the course, not their own — keeps the CI bar comparable across submissions.
- **Re-use for L13 and L15.** The instrumented Q&A bot is the base for L13's multi-agent extension and L15's long-term maintenance lab. Encourage students to keep the repo clean.
