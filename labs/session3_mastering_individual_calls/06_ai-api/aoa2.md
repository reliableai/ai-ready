# Designing Agentic Systems: Roles, Axes, Abstractions, and the Role of MCP

## Context and Motivation

AI agents bring **new opportunities** and **new failure modes**.

However, AI agents are only *partly* different from humans.  
Because of this, we have a great deal to learn from what already works well — most notably, **the Web**.

A key part of the design challenge is therefore to:
- identify what is **similar** to prior systems,
- identify what is **genuinely new**,
- and understand how both opportunities and failures change as a result.

Once we do this, we can reason more clearly about:
- useful **abstractions**,
- necessary **middleware**,
- and eventually, meaningful **standardizations** — things we need to agree on as a community.

We also have lessons from Web services and SOA.  
But we must be mindful of a crucial difference:

> In Web services and SOA, the *consumer of specifications was human* —  
> a consumer that is, on average, **far less capable and far less careful** than a modern LLM at reading, interpreting, and consuming specifications.

This changes both the **power** and the **risk profile** of agentic systems.


---

## Core Design Axes

### Axis 1 — Who Reads What (and How Interaction Is Guided)

This axis combines two questions:

1. **Who consumes the service or tool description?**  
2. **What description and context do they consume — and with what guidance?**

Possible consumers include:
- Human users (via web pages)
- Developers (via API documentation)
- LLM-based agents
- Hybrid human + agent setups

#### A. New capability: LLMs as specification consumers

LLMs can read and digest specifications at a scale and level of detail that humans typically cannot:
- they can ingest long and complex descriptions,
- consistently follow mechanical constraints and schemas,
- cross-reference multiple sources,
- and operate “carefully” in the sense of not skipping steps or forgetting details.

We can actually specify more behaviors and constratints than we did for humans (or maybe we had them in Terms and Conditions - now LLMs can read those, too)


We had "specs" kind of working for the web: do we need something different here?



---

#### B. New weakness: agents are sometimes given *less* context than humans

Despite this increased capability, many agent tool ecosystems — including MCP-style descriptions — risk providing *less* context than classic web experiences.

On the Web, users are surrounded by rich and redundant context:
- information architecture and navigation
- page structure and visual hierarchy
- explanations, examples, caveats
- implicit “you are here” state

By contrast, tool descriptions often consist of:
- an operation name
- a JSON schema
- a short textual description
- little or no global view of the service

LLMs can consume much more context — yet we sometimes give them much less.

What is the equivalent of the “whole site” and its structure when exposing capabilities to agents?

---

#### C. Missing ingredient (or is it an opportunity to capture?): guided, step-by-step interaction

Web applications do not merely expose capabilities; they **guide users through safe sequences**.

For example, an Amazon purchase flow is not a single action, but a guided interaction:
- cart review
- shipping selection
- payment selection
- explicit confirmation
- post-action receipts and state

In many MCP- or tool-based integrations, how do we do this? do we one-shot it, always? Do we leave it to the client / agent?


**Open problem:**  
Assuming we know what we want to "support", how do we express and enforce guided flows for agents:
- what the next valid actions are,
- when confirmation is required,
- what must be shown to users,
- and what constitutes meaningful consent?

---
### Axis 2 — Decision and Authority (and Guardrails / Controls)



**who controls which decisions?**, and **how that control is expressed, enforced, and audited?**.

(And: control rarely sits in one place. **It is typically split across client, provider, and sometimes middleware.**)

#### A. “Acting” is a bundle of decisions

Even a seemingly simple action contains multiple decision points:
- **Interpretation**: what does the user mean?
- **Planning**: what sequence is acceptable?
- **Tool selection**: which capability is appropriate and allowed?
- **Parameter choice**: which values, thresholds, and scope?
- **Commitment**: when does it become irreversible?
- **Recovery**: what happens on partial failure (retry, compensate, escalate)?
- **Disclosure**: what must be shown to the user before proceeding?

> For each decision point: who controls it, and how do we prevent skipping or guessing?

#### B. Guardrails are not “extra safety” — they define behavior under uncertainty

Many “agent failures” are not model failures, but control failures:
- committing too early,
- filling missing parameters with guesses,
- suppressing errors,
- skipping required steps,
- presenting approvals that are not meaningful.

Guardrails are therefore part of the system’s **behavioral contract**, not a bolt-on.

This leads to a design tension:

> Which constraints must be enforceable (hard), and which can only be guidance (soft)?  
> And where can each realistically live?


#### C. Control lives across layers (and the split should be intentional)

In practice, different layers have different strengths:

- **Clients/agents** tend to control: intent elicitation, interaction policy (ask vs infer), step-by-step UX, user-facing summaries, recovery strategy.
- **Providers/services** tend to control: permissions, scopes, budgets, validation, refusal on ambiguity, commitment boundaries, receipts.
- **Middleware/platforms** often emerge to control: centralized policy, cross-tool enforcement, consent lifecycle, tracing, anomaly detection.



So the key question becomes:

> What should providers specify and how? Which abstractions, "standards" or best practices should we adopt? Should a new kind of middleware emerge to support this, and where should it reside? How can client side abstractions help client avoid pitfalls? What should we monitor? What can be learned quickly, at scale, from a community of clients usign a service? 

#### D. The autonomy leash 

A useful mental model is a leash as a **vector of constraints**, not a single “low/medium/high autonomy” knob:

- scope (which objects/resources)
- action class (read vs write vs transfer vs irreversible)
- risk tier (financial, privacy, safety, reputational)
- budgets (cost/time/volume/rate)
- data boundaries (what can be accessed/returned)
- reversibility (compensation possible?)
- time window (authority expiration)
- confirmation policy (what requires explicit approval, and when)

This framing forces a practical question:

> Where is each constraint declared, where is it enforced, and where is it merely suggested?

This also changes over time: in code, we have the notion of commit, and autonomy lives commit to commit (now). Are there similar business abstractions?

#### E. Observability is part of control (not an afterthought)

Guardrails that cannot be observed are hard to trust, hard to debug, and hard to govern.
So observability is not “logging later” — it is part of the control design.

A useful distributed-systems framing is to treat one agent run as a **trace**:
- the overall agent interaction is the trace
- each tool call (including MCP tool invocations) is a **span**
- approvals / confirmations / refusals / commits are **events** (or spans, depending on granularity)
- “receipts” are the durable record of what actually changed

This points naturally to **OpenTelemetry** (or something like it) as a baseline for *plumbing*:
- propagate trace context end-to-end (client → middleware → provider)
- correlate downstream service calls with the originating agent action
- enable cross-tool debugging when something goes wrong (or silently fails)

But “using traces” is not enough. We also need **semantic conventions**:
- what does a “tool invocation” mean?
- what event marks a “commit point”?
- how do we represent “approval requested” vs “approval granted”?
- how do we represent “refusal due to ambiguity” vs “refusal due to policy”?
- what constitutes a receipt?

MCP matters here in a specific way:
- it gives us a structured invocation surface where trace context *can* be attached and propagated,
- but it does not, by itself, define which semantic events, receipts, or approval artifacts should exist.

And then the obvious tension:
- traces can easily capture prompts, user data, and sensitive content
- so we also need conventions around redaction, access control, and retention:
  - what is safe to store?
  - who gets to see it?
  - what can be shared across org boundaries?

---

### Axis 3 — Consent, Approvals, Terms (and Responsibility)

This axis is where legal and social reality enters the system design.

Consent is not a checkbox.  
Approvals are not a modal dialog.  
Terms and conditions are not “some PDF somewhere” where the real assumption is that nobody reads them.

They define:
- what authority exists,
- what disclosures were required,
- what was agreed to (and when),
- and ultimately, who is responsible for outcomes.

#### A. What counts as meaningful consent?

In web flows, consent and approvals are embedded in interaction:
- the UI constrains what can happen,
- the user sees a concrete summary at commitment,
- the system records what was done.

In agentic flows, it is easy to degrade consent into something that is neither meaningful to users nor defensible later.

So we need to ask:

> What must be shown to the user before approval?  
> What does the user approve: a plan, a summary, a specific action, a delegation?  
> How do we avoid “consent fatigue” while keeping consent real?

#### B. Approvals and terms should become *artifacts*, not vibes

A practical stance is to treat approvals/consent/terms as first-class artifacts:
- what was approved (stable summary)
- under which scope and thresholds
- for how long (expiry / revocation)
- under which terms/policy version
- with what identity / principal

Otherwise we end up with:
- “approvals” that feel meaningful but are technically meaningless, or
- controls that are technically enforceable but legally indefensible.

The problem again is who can help where. What can providers do to help? what can frameworks do to help? what can standards do to help?


#### C. Responsibility is shared — but the boundaries must be explicit

A recurring failure mode is that responsibility is implicit until failure, and then becomes contested.

So the question is:

> When something goes wrong, what was preventable by the provider, what was preventable by the client, and what required middleware?  
> What evidence do we have (receipts, traces, consent artifacts) to support that answer?

---

## The Abstractions We Need

### 1. Capability Abstraction (What Can Be Done)

**Missing today**
- preconditions
- side effects
- cost, risk, reversibility

Needed outcome:
> Agents (and humans) must be able to reason about *world impact*, not just API calls.

---

### 2. Intent Abstraction (Why It Is Done)

**Missing today**
- explicit representation of:
  - user intent
  - inferred agent intent
  - scope and expiration

Needed outcome:
> Intent must be a **first-class object**, inspectable and auditable.

---

### 3. Control / Autonomy Contract (Who May Do What, When)

We need an explicit way to represent the “leash vector”:
- scope, action class, risk tier
- budgets and data boundaries
- confirmation policy
- expiry and revocation

And we need it to be:
- readable by clients/agents (for planning and UX),
- enforceable by providers/middleware (for safety/cost),
- and loggable for audit.

---

### 4. Guided Interaction / Flow Semantics (How to Proceed Safely)

If the Web’s superpower is guided flows, we need an equivalent abstraction:
- state (“where are we?”)
- allowed next actions
- required confirmations and disclosures
- commitment points
- recovery semantics

Otherwise “tools” stay as isolated calls, and safety/UX becomes ad hoc.

---

### 5. Observability with Meaning (What Happened, and Why)

Beyond logs, we need:
- semantic traces: intent → plan → actions → outcomes
- business assertions: invariants and postconditions that detect silent failure
- receipts: structured, auditable outcomes (what changed, where, under what authority)

---

### 6. Consent / Approval / Terms Artifacts (Authority Basis)

We need standard ways to represent:
- approvals (what was approved, by whom, when)
- consent grants (scope, thresholds, expiry, revocation)
- terms/policy versions referenced at commitment

These artifacts connect the technical system to legal accountability.

---

## Where MCP Helps (and Where It Does Not)

A useful way to think about MCP is that it standardizes a **tool invocation boundary**.

Specifically, MCP standardizes:
- how capabilities exposed by a *given server* can be enumerated,
- how those capabilities are invoked (inputs / outputs),
- and the structure of the interaction between a client/agent and that server.

This is **local, explicit discovery**:
- the client already knows *which server* it is talking to,
- MCP does not provide global search or semantic service discovery,
- it does not answer “who can do X?”, only “what can this server do?”.

This standardized boundary is important because it creates a **stable interposition point**:
a place where additional logic *can* sit between client and service.

Examples of what may be interposed here include:
- policy enforcement (permissions, quotas, budgets),
- logging and trace propagation,
- rate limiting and throttling,
- approval or consent checks,
- request/response validation.

MCP itself does not define these behaviors.
It merely provides a consistent surface where they can be implemented.


This is meaningful — but it is not the same as standardizing **meaning**, **flows**, **authority**, or **responsibility**.

A decent mental model remains:

> MCP is to agentic tool ecosystems what HTTP was to the Web:  
> foundational, enabling — and insufficient on its own.

### What MCP helps with

- **Discovery + invocation consistency**
  - a uniform way for clients/agents to find tools and call them
  - structured inputs/outputs reduces “stringly typed” prompt glue

- **A natural mediation and governance choke point**
  - a place where policy checks *can* be inserted
  - a place where rate limits / budgets *can* be enforced (depending on architecture)

- **A place to attach observability plumbing**
  - MCP calls map naturally to spans (“tool call as span”)
  - trace context can be propagated across boundaries (client → tool server → downstream services)
  - this is where OpenTelemetry-style propagation becomes practical

- **Potentially: richer descriptions than raw APIs**
  - MCP descriptions *could* include guidance, examples, risk metadata, and “what this is for”
  - whether we actually do that (and standardize it) is still unclear

### What MCP does not solve

MCP does not, by itself, solve the core problems highlighted by the axes:

- **Axis 1 (Who reads what / guidance):**
  - MCP does not guarantee that agents get “whole site” context
  - MCP does not define how to guide step-by-step interactions

- **Axis 2 (Control allocation / autonomy leash):**
  - MCP does not define an autonomy contract (scope, risk tiers, confirmation policy)
  - MCP does not define enforceable commitment points (preview vs commit)
  - MCP does not define recovery/compensation semantics

- **Axis 3 (Consent, terms, responsibility):**
  - MCP does not define what constitutes meaningful consent
  - MCP does not define approval/terms artifacts (what was approved, under which version, by whom)
  - MCP does not resolve responsibility boundaries when failures occur

- **Observability with meaning:**
  - MCP can carry trace context, but does not define semantic conventions:
    - what counts as “commit”?
    - what is a “receipt”?
    - what does “refusal” mean (policy vs ambiguity vs missing consent)?
  - without shared conventions, traces remain technically useful but semantically shallow

### The real question MCP raises

Not “do we adopt MCP?”, but:

> What do we standardize *on top of* MCP so that tool calling becomes governable?

Candidate targets (not yet solved by MCP):
- guided interaction / flow semantics
- preview → commit patterns
- receipts and business assertions
- consent / approval / terms artifacts
- semantic trace conventions (OpenTelemetry-compatible)

---

## Synthesis

AI agents are systems that **read**, **decide**, and **act**.

The challenge is not only “how do we call tools?”  
It is making explicit:
- what is read and what context is available,
- who controls which decisions and how constraints are enforced,
- what constitutes consent under which terms,
- and how responsibility is assigned and evidenced.

This is where abstractions, middleware, and (eventually) standardization matter.



# part II
# Proposal: Abstractions, Practices, and “Where They Live” for Governable Agentic Tool Ecosystems (MCP-compatible)

## Motivation

Agentic systems are distributed systems that can **read**, **decide**, and **act**.
The core risk is not “models are dumb”; it’s that:
- authority is implicit,
- commitments are blurred,
- failures are silent,
- and responsibility becomes a debate after the fact.

So the goal of this proposal is practical:

> Define a small set of abstractions and practices that make agentic systems **governable at scale** —  
> and be explicit about where each abstraction should be **declared**, **enforced**, and **evidenced**.

A useful framing is three planes:
- **Data plane**: actions that change state (tools/services)
- **Control plane**: authority, guardrails, policy
- **Evidence plane**: traces, receipts, approvals

MCP is best viewed as a standardized boundary in the data plane that can carry control and evidence metadata.

---

## Design principle: “Declare / Enforce / Evidence” (often different places)

For each abstraction, we should be able to answer:
1) **Where is it declared?** (who states the rule/meaning)  
2) **Where is it enforced?** (who can actually prevent violation)  
3) **Where is it evidenced?** (what artifacts prove what happened)

If we can’t answer these, we don’t have a system; we have vibes.

---

## Core abstractions to develop

### 1) Capability semantics (meaning, not just schema)
**What:** preconditions, side effects, reversibility, risk tier, cost model, common failure modes.

- **Declared by:** provider (they know semantics)
- **Enforced by:** provider (hard bounds) + middleware (cross-tool policy)
- **Evidenced by:** receipts + traces

**MCP fit:** MCP can carry this as structured metadata alongside tool descriptions, but MCP does not define the schema for “meaning”.

---

### 2) Action classes + risk tiers (shared vocabulary)
**What:** minimal taxonomy like:
- action class: `read`, `write`, `transfer`, `irreversible`, `safety_sensitive`
- risk category: `financial`, `privacy`, `safety`, `reputational`
- risk level: `low/med/high` (or numeric)

- **Declared by:** provider per operation
- **Used by:** clients/agents to decide confirmations and UI summaries
- **Enforced by:** provider/middleware (thresholds, scopes), client (UX gating)

**Why this matters:** it’s the cheapest “standardization” that unlocks consistent guardrails, monitoring, and consent.

---

### 3) Commitment points: Preview → Commit (two-phase)
**What:** make irreversible actions explicit and hard to bypass.

- `preview()` returns:
  - stable summary of effects (what the user would approve)
  - a `confirm_token` (or commit reference)
  - optional computed plan / price / constraints
- `commit(confirm_token, …)` performs the irreversible step
  - must be idempotent (idempotency key)
  - must return a receipt

- **Declared by:** provider (commit semantics are domain truth)
- **Orchestrated by:** client/agent (step-by-step flow + summaries)
- **Enforced by:** provider (cannot commit without token / policy)
- **Evidenced by:** commit event + receipt

**MCP fit:** MCP makes it easy to expose both calls consistently; it does not mandate the pattern.

---

### 4) Consent / delegation artifacts (authority objects)
**What:** consent is an object, not a chat message:
- principal (who authorized)
- scope (what resources)
- thresholds (limits)
- expiry / revocation
- terms/policy version references (see next)

- **Created by:** client UX and/or middleware consent service
- **Validated by:** provider at commit boundary (must be checkable)
- **Stored by:** middleware/platform (often) or provider (if account owner)
- **Evidenced by:** consent ID referenced in receipts + traces

**Why:** if consent isn’t an artifact, you can’t reason about responsibility or disputes.

---

### 5) Terms / policy artifacts (what rules applied)
**What:** treat “terms & conditions” and policy as versioned, referenceable inputs to authority:
- `terms_version`, `policy_version`
- what disclosures were shown (at least as a stable reference)
- which version was accepted for this action/authority grant

- **Published by:** provider/platform
- **Presented by:** client (at the moment it matters)
- **Enforced by:** provider/middleware at commit (must reference a valid version)
- **Evidenced by:** acceptance artifact + receipt fields + trace events

This is the bridge between “technical correctness” and “legal defensibility”.

---

### 6) Guided interaction / flow semantics (the “whole website” problem)
**What:** the missing web affordance: state + allowed next steps + required confirmations.

Two practical flavors:
- **Provider flow hints**: “if the user wants X, typical safe sequence is …”
- **Client-owned orchestration**: client chooses UX, but must respect constraints and commit points

- **Declared by:** provider as hints + hard constraints; client as UX flow
- **Enforced by:** provider at commitment points; middleware for cross-tool rules
- **Evidenced by:** trace shows step progression; receipts show commits

**Non-goal:** providers shouldn’t own everyone’s UX.  
**Goal:** providers should expose enough structure that clients don’t have to guess.

---

### 7) Receipts (durable outcomes)
**What:** every state-changing action returns a structured receipt:
- what changed (object IDs, deltas or stable summary)
- under what authority basis (consent/delegation reference)
- when, where, correlation IDs
- reversible? compensation path?

- **Produced by:** provider (source of truth)
- **Stored by:** client + middleware for audit/support
- **Evidenced by:** receipts are the evidence

Without receipts, responsibility becomes storytelling.

---

### 8) Semantic traces (OpenTelemetry + conventions)
**What:** tracing plumbing + a shared semantic layer:
- one agent run = **trace**
- each tool/MCP invocation = **span**
- approvals, refusals, preview, commit, compensation = **events** or spans
- receipts referenced by ID

- **Implemented by:** all layers (client/middleware/provider)
- **Standardized as:** OpenTelemetry-compatible semantic conventions (community)
- **Privacy controls:** redaction, access control, retention (must be explicit)

This matters because:
- guardrails without observability are unverifiable,
- “success” without meaning is misleading,
- silent failures dominate at scale.

---

### 9) Business assertions (postconditions / invariants)
**What:** detect “successful nonsense”:
- invariant checks (domain truth)
- postconditions (“intended outcome holds”)
- statistical assertions (system-level drift)

- **Declared by:** provider (domain invariants) + sometimes client (intent invariants)
- **Evaluated by:** provider + middleware
- **Evidenced by:** assertion outcomes in traces/metrics and receipts/errors

---

## Where these should live (quick residence map)

- **Clients/agents** should own:
  - intent elicitation, interaction policy (ask vs infer)
  - step-by-step UX and user-facing summaries
  - collecting approvals and producing consent artifacts (or calling a consent service)
  - propagating trace context, emitting semantic events

- **Providers/services** should own:
  - capability semantics metadata (as much as feasible)
  - enforceable constraints: permissions, scope, budgets, rate limits
  - commitment boundaries (preview/commit) and refusal on ambiguity at commit time
  - receipts as a first-class output

- **Middleware/platform** often must exist to own:
  - cross-tool policy (one place to encode org rules)
  - consent lifecycle (issuance, expiry, revocation)
  - trace pipeline defaults (redaction, retention, access control)
  - anomaly detection + automated analysis loops

A healthy system uses all three intentionally.

---

## Practices to develop (not optional at scale)

### Provider practices
- publish action class + risk tier per capability
- require preview/commit for irreversible/high-risk actions
- refuse ambiguous requests at commit boundaries (structured refusal reasons)
- always return receipts for state changes
- version semantics (meaning changes are breaking changes)
- agentic misuse-case design (ambiguity, escalation bypass, consent laundering)

### Client/agent practices
- do not guess across commitment boundaries (clarify or preview)
- show stable summaries that match commits
- treat consent as an artifact (IDs, scope, expiry), not chat text
- handle recovery deliberately (retry vs compensate vs escalate)
- propagate trace context and emit semantic events consistently

### Middleware practices
- central policy engine (cross-tool budgets/scopes/data rules)
- consent lifecycle service (grant, revoke, audit)
- OpenTelemetry-based trace pipeline with strict redaction rules
- automated error analysis (detect patterns of refusal, silent failure, misuse)

---

## What to standardize first (minimal viable “community agreement”)

If we want the smallest set that unlocks the most:

1) **Action class + risk tier vocabulary**
2) **Preview → Commit pattern** (confirm tokens + idempotency)
3) **Receipt schema** (what changed + authority basis + correlation IDs)
4) **Consent/delegation schema** (scope/threshold/expiry/revocation + terms/policy version refs)
5) **OpenTelemetry semantic conventions** for agent-tool runs:
   - tool invocation span
   - preview, approval requested/granted, refusal, commit, compensation events
   - receipt reference fields

Everything else can evolve around these.

---

## Where MCP helps (and where it does not)

### MCP helps with
- **Local capability enumeration (per server)** and consistent invocation structure
- a stable boundary where:
  - policy hooks can be inserted,
  - trace context can be propagated,
  - validation and throttling can be applied (architecture-dependent)

### MCP does not define
- capability semantics (meaning)
- guided flow semantics
- autonomy/authority contracts
- consent/terms artifacts
- receipts and business assertions
- semantic tracing conventions

So the strategy is not “MCP solves governance”. It is:

> Use MCP as the substrate, then standardize the semantics and evidence on top.

---

## Closing thought

If we do this well, we get something the Web had implicitly:
- guided interaction,
- meaningful commitment,
- and a paper trail.

But we make it explicit and machine-operable:
- authority becomes a contract,
- safety becomes enforceable,
- and responsibility becomes evidence-backed rather than narrative-driven.
