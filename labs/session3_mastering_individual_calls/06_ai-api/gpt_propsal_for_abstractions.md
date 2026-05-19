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
