# L10 · Week 5 — Monitoring, Observability and Reporting

Status: **revised outline v2** (structure approved; restructure of `monitoring.html` and slides pending).

## Goal of the lecture

By the end of this session, students should be able to:

1. Explain **why we log** in software — the primitive act — and how that reason builds up through metrics, traces, and monitoring, and then extends to AI.
2. Describe **what we monitor and how**, using the unifying notion of **assertions**: code-level, business-level, statistical, and semantic.
3. Walk up the complexity ladder — single LLM call → memory → tool-calling loop → agents-of-agents — and at each step say *what new failure modes appear and which assertions catch them*.
4. Implement vendor-neutral **logging** (stdlib `logging` + structured JSON) and **tracing** (OpenTelemetry, GenAI semantic conventions) for an agent.
5. Wire an **eval harness into CI**, ship **telemetry** off the box to a remote backend, and run **online evals** (canary, shadow, drift) on live traffic.
6. Turn raw traces into **reports** a team can act on.

## Position in the course

- **Builds on:** L5–L6 (eval fundamentals, organizational blindness), L7 (LLM-as-judge, rubrics), L8–L9 (experiments, uncertainty).
- **Feeds into:** L13 (multi-agent / complex systems — where "agents of agents" becomes concrete), L15 (long-term maintenance of AI systems).
- **One-line framing:** *Monitoring is continuously checking the assertions you can't prove at compile time. Telemetry is what makes "continuously" possible.*

---

## Unifying thread: assertions + the summary matrix

Running through every section is one concept — the **assertion**, something we expect to hold and continuously check — that evolves as systems get more open-ended:

| System kind | Assertion kind | Example |
|---|---|---|
| Traditional SW / SaaS | Code-level assertions | `assert x > 0`, exceptions, pre/postconditions |
| Classical ML | Statistical assertions | `KS(feat_train, feat_prod) < 0.1`, accuracy drop ≤ 2 pp |
| LLM per-call | Semantic assertions | Output JSON valid; no PII; used the requested tool |
| LLM session (memory/tools) | Session / trace assertions | No contradiction across turns; step budget respected; no tool-arg drift |
| Agent task / orchestration | Task-level assertions | Plan executed; user intent satisfied (LLM-as-judge rubric over span tree) |

The lecture introduces each kind at the level where it first *has to* exist, so students feel the motivation rather than receiving a taxonomy.

**The summary matrix** — shown partially in Section 01 as a roadmap, filled in row-by-row through the lecture, and shown whole as the closing recap:

| System | What we monitor | How | Why |
|---|---|---|---|
| **Traditional SW / SaaS** | Control flow, exceptions, return values, latency, error rates, resource use (RED / USE metrics) | `assert`, exceptions, structured logs, dashboards on aggregated metrics, SLOs | Know when something broke, restore service fast, debug post-hoc, hit SLAs |
| **Classical ML** | Feature distributions, prediction distribution, accuracy where ground truth is available, training-serving skew | Statistical assertions (K-S, PSI, χ²); shadow deploys; offline eval gates | You can't check `pred == label` per sample — only *distribution-level* properties are testable at request time |
| **Single LLM call** | Output shape, schema validity, policy (toxicity, PII), tokens, cost, latency | Semantic assertions: Pydantic/JSON schema, regex/PII scrubber, classifier-based guardrails, one structured log event per call | Output is open-ended — no HTTP 500 for "wrong answer"; proxies must fail before users do |
| **+ context / tool / memory** | Above + session coherence, tool-arg validity, step count, retry loops, cost/session | OTel span tree (`trace_id` ↔ `session_id`), session-keyed logs, per-span guardrails, step-budget counters | A request is now a *tree* and a user is a *sequence*; flat logs can't show causality or session drift |
| **Systems of agents** | Above + task-level completion, plan validity, coordination, role adherence | Task-level LLM-as-judge rubric over span trees; coordination assertions on orchestrator spans; statistical assertions on task success / repair / cost-per-task | Correctness is defined at the *task* level; no single call holds "the answer" — you need the whole span forest to judge |

---

## Pedagogical arc (5 sections, same L7 template)

Numbered sections, `content-card` blocks, `thesis-block` "Key insight" boxes, short highlight.js code snippets.

---

### 01 / LOGGING, THEN MONITORING, IN SOFTWARE AND SAAS — THE BASELINE

Start from what students already know. No LLMs yet. Lead with logging — it's the primitive; monitoring is what we build on top.

- **Why we log in software — the primitive act.** A log line is a statement of "this happened, here, with these values, at this time." The original use cases predate SaaS: post-hoc debugging ("why did it crash at 3am?"), audit trails, and replaying a run. Logging exists before you have any dashboard or alert.
- **From logs to metrics to traces** — the three pillars of observability, in the order they historically appeared.
  - *Logs:* unstructured → structured (JSON). One event per interesting thing that happens.
  - *Metrics:* aggregations over logs (counts, rates, histograms). Cheap to store; lose detail.
  - *Traces:* logs stitched together by causality (request id, span hierarchy). Needed once systems stopped being single-process.
- **From logging to monitoring.** Monitoring = *automated, continuous inspection* of logged/metric/trace data against expectations. That's where **RED** (Rate, Errors, Duration) and **USE** (Utilization, Saturation, Errors) come in, plus **SLOs, error budgets, MTTR**, alerting culture.
- **Assertions in code** — the Python `assert`, exceptions, preconditions, postconditions. Fail-fast philosophy. This is the simplest form of "a thing we expect to hold, continuously checked."
- Code snippet: a Python function with an `assert` guarding an input + a structured `logging.info(...)` event recording the call. The pairing is intentional — asserting catches violations at the moment they happen; logging lets us reconstruct them later.
- Roadmap table (shown with only the first row filled in): *what / how / why* across the five system kinds we'll walk through. Each subsequent section fills in its row.
- **Key insight:** *Monitoring is the act of continuously running the checks you can't prove at compile time. Everything in this lecture is a variation on that theme.*

---

### 02 / MONITORING TRADITIONAL ML — WHEN ASSERTIONS GO STATISTICAL

The bridge section. Classifiers, not LLMs — but already non-deterministic at the aggregate level.

- Why classical monitoring isn't enough: **"was this prediction correct?" is unanswerable at request time.** You can't `assert pred == label` because you don't know `label`.
- **Statistical assertions** as the new primitive: you assert properties of *distributions over time*, not of single outputs.
  - **Data drift** on inputs (Kolmogorov–Smirnov, Population Stability Index, χ² for categoricals).
  - **Prediction-distribution shift** (output histogram changing).
  - **Concept drift** (label-free proxies).
  - **Training-serving skew** (features at training time ≠ features at serving time).
  - **Confusion-matrix rebalance** — overall accuracy stable but per-class errors moving.
- Per-sample assertions still matter: input schema, value ranges, null-rate — these *are* code-level assertions, just at the feature layer.
- Model cards, offline-vs-online performance gap, shadow deployments (yes, these predate LLMs).
- Code snippet: a tiny K-S drift check between last-week and this-week feature distributions, with a CI-style threshold.
- **Key insight:** *When you can't assert ground truth per sample, you assert the shape of the distribution instead. This is what traditional ML monitoring taught us; LLM monitoring inherits it.*

---

### 03 / LLM SYSTEMS, ESCALATING — EACH STEP FORCES A NEW PRIMITIVE

The heart of the lecture. Three stages, each adds failure modes and forces new observability.

**Stage A · A single LLM API call**
- What to log per call: request id, model, prompt version, temperature, input/output tokens, latency, cost, raw output shape.
- **Per-call semantic assertions** (the "guardrails"): output JSON valid; schema matches Pydantic model; policy passed (toxicity, PII); uses the tool it was asked to.
- Design patterns: **fail-closed vs. fail-open** per check; **retry-with-repair** (ask the model to fix a schema-invalid output once); **fallback chains** (cheap → strong → human); **circuit breakers** when reject-rate spikes.
- PII/redaction patterns belong here: hashed user ids, regex scrubbers, env-gated verbosity, typed-secret wrappers.
- Code snippet: a `@guardrail_structured` decorator that (a) calls the model, (b) validates against a Pydantic schema, (c) re-asks on failure, (d) emits a structured log event either way.
- Data structure so far: **one JSON row per call.** Still flat.

**Stage B · Add memory / sessions**
- A call is now one turn in a conversation. Assertions climb to **session level**: no contradiction across turns; agent hasn't changed its stated identity; session cost under budget; turn count bounded.
- PII surface area grows dramatically — you are now storing user history. Retention, deletion, redaction get real.
- Session-level metrics: resolution-in-one-turn rate, mean turns to success, cost/session, sessions needing handoff.
- Data structure: **session-keyed rows, linked by `session_id`.**

**Stage C · Add a tool-calling loop**
- A single user request now produces a **tree** of LLM and tool calls. Flat logs can't express the causal structure.
- Enter **tracing**: trace = root span; child spans for each `llm.call` and `tool.call`; attributes carry prompt version, cost, guardrail verdict, rubric score; events carry retries and repairs.
- **OpenTelemetry GenAI semantic conventions**: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`. Using standard names = portability across backends (Jaeger, Tempo, Phoenix, Langfuse, LangSmith).
- New assertions that require the tree: tool args valid; tool response fits schema; step budget not exceeded; no repair loop; guardrail verdict OK on every leaf.
- Code snippet: `trace_llm_call` context manager setting GenAI attributes; hand-rolled `trace_viewer.py` that renders the exported JSON as a collapsible HTML span tree. Content-card: *"What exists out there"* — Phoenix, Langfuse, Jaeger, LangSmith, Grafana Tempo — with a build-vs-buy thesis.
- Data structure: **a causal tree per request.**
- **Key insight:** *Each rung of the complexity ladder forces a new data structure: row → session-keyed rows → causal tree. When you can't reconstruct a bad output from its trace alone, you're not observable yet.*

---

### 04 / AGENTS AND SYSTEMS OF AGENTS

Orchestrators, planners, reasoners, multi-agent teams. Conceptual-heavy (the runnable multi-agent lab lives in L13).

- Topology: a task produces a **forest** — planner span → sub-agent spans → per-sub-agent tool/LLM spans — sometimes with handoffs and re-entry.
- **Task-level assertions** become dominant: "did the final answer satisfy the original user intent?" This is usually an LLM-as-judge rubric (L7) run against the leaf output, with the *full span tree* as evidence.
- **Coordination assertions**, new to this level: planner produced a valid plan; no agent loop / ping-pong; step budget bounded across the whole tree; no role drift ("the research agent started writing code"); reasoner and actor stayed in their lanes.
- **Statistical assertions at this level**: task success rate, repair rate, human-escalation rate, mean agents invoked per task, mean depth of plan.
- The dashboard becomes 2-D: per-call metrics (cost, latency, guardrail) *and* per-task metrics (success, plan length).
- Failure modes worth naming: silent agent disagreement, cascading repair, planner loops, role confusion, cost explosions from nested retries.
- **Key insight:** *In agent systems, correctness is defined at the task level and can only be read from the span tree — never from a single call. Monitoring and evaluation converge: the production trace is the eval sample.*

---

### 05 / CI-INTEGRATED EVAL HARNESSES, TELEMETRY, AND REPORTING

The operational closing section. This is where "assertions" become a system.

- **Offline eval / CI gate:**
  - Golden set + rubric judges run on every PR = a suite of *assertions* run on representative data.
  - Budget: tokens, wall-clock, dollars — fail the build if exceeded.
  - Regression policy: block merges that drop aggregate score beyond a threshold, using the **confidence intervals from L8–L9** (not raw means).
  - Versioning: dataset, judge, prompt — all pinned in the run artifact.
- **Telemetry — what makes remote monitoring possible:**
  - Definition: the operational act of *shipping* structured data (logs, metrics, spans) off the service to a remote backend. Without telemetry you can only monitor by SSHing into a box.
  - OpenTelemetry Protocol (**OTLP**) as the vendor-neutral wire format — same spans go to Tempo, Jaeger, Phoenix, Langfuse, LangSmith without code changes.
  - Sampling: head-based (decide at trace start) vs. tail-based (keep all errors, 1% of successes).
  - Cardinality discipline — don't explode metrics with user-generated string tags.
  - Code snippet: how the lab swaps console exporter → OTLP exporter with 3 lines.
- **Online eval on live traffic:**
  - **Canary** (small % on new prompt/model, side-by-side rubric/guardrail comparison).
  - **Shadow** (new version sees real inputs; outputs judged but not shown to users).
  - **Sampled LLM-as-judge** on prod traffic (with L7 caveats).
  - **Drift signals** — rising guardrail-reject rate; shifting input embedding distribution; changing output-length distribution; changing tool-call mix.
- **Reporting cadences — who reads what:**
  - Real-time: engineer alerts on hard assertion breaks (error rate, p95 latency, safety).
  - Daily: quality/cost summary for the team.
  - Weekly: PM/leadership — one quality number *with CI*, one cost number, one safety number, prose "what changed and why."
  - Anatomy-of-a-good-weekly-report content-card + full charted example in the lab (4-week fake dataset with a Week-3 regression and Week-4 partial recovery).
  - Incident reviews: LLM failures are usually *distribution shifts*, not bugs — post-mortems look different from Software 1.0.
- Code snippet: a pytest-style `test_rubric_regression` that loads the golden set, runs the judge, and asserts on a CI threshold with uncertainty (ties back to L8–L9).
- **Key insight:** *The CI gate and the production dashboard are the same set of assertions, checked on different data at different cadences. Telemetry is what lets the second one exist.*

---

## Deliverables (to refresh after outline approval)

1. **`monitoring.html`** — rewrite to 5 sections above, preserving L7 template (nav, content-cards, thesis-blocks, highlight.js).
2. **`monitoring_slides.pptx`** — rebuild to mirror the 5 new sections; keep Ocean Gradient palette.
3. **`monitoring_lab.ipynb` + `*.py`** — **code stays valid** (it's a Stage-A + Stage-B + Stage-C lab already: API call + memory + tool loop, with schema/toxicity guardrails and a golden-set rubric). Light edits to notebook narration to use the assertions vocabulary.
4. **`trace_viewer.py`**, **`weekly_report_demo.py`**, **`golden_set.json`**, **`minimal_agent.py`** — no changes needed.
5. **`index.html`** L10 card already points here — no edit.

## Resolved decisions (carried forward, still good)

- **Lab agent:** fresh minimal agent (~30 LoC) for self-containment.
- **OTel depth:** console exporter for the runnable lab + commented OTLP snippet for swap-in. Hand-rolled `trace_viewer.py` renders the console JSON as a collapsible HTML span tree.
- **Tool landscape:** content-card in Stage C ("What exists out there — and when to reach for it") naming Phoenix, Langfuse, Jaeger, LangSmith, Grafana Tempo, each with one sentence on its specific value, plus a build-vs-buy thesis block.
- **Reporting:** anatomy-of-a-weekly-report card in Section 05; charted example (4-week synthetic dataset) in the lab.
- **PII/safety:** medium coverage — dedicated content-card in Stage A (logging) on PII/redaction patterns (regex scrubbers, hashed ids, log-level policy, environment-gated verbosity). Deeper safety eval deferred to later lessons.

## New decisions in v2

- **Unifying concept:** *assertions*, escalating from code → business → statistical → semantic → task-level. Each section names which kind it introduces.
- **Section 5 expanded** to cover **telemetry** explicitly (OTLP, remote backend, sampling, cardinality) alongside CI and reporting.
- **Agents section (04)** is concept-heavy; runnable multi-agent code defers to L13 and is explicitly cross-referenced.
