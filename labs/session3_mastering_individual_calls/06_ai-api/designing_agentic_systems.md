# Designing Agentic Systems: Axes, Abstractions, and the Role of MCP

## Context

AI agents — systems composed of LLMs, tools, memory, and external services — are **not a new programming model**.

They are **a new failure mode for distributed systems**:
- systems that *act*,
- *infer intent*,
- and often *fail silently*.

To design them responsibly and at scale, we must stop focusing on tools and start focusing on **explicit abstractions**.

---

## Core Design Axes (Dimensions)

The following axes are **orthogonal**. Confusing them leads to brittle systems and misplaced expectations.

### Axis 1 — Who is the Agent?
- Human (web)
- Developer-written software (SOA)
- LLM-based agent
- Multi-agent system

> This determines *who reasons* and *who is accountable*.

---

### Axis 2 — How Capabilities Are Described
- HTML (for humans)
- Natural language documentation (for developers)
- Structured schemas (OpenAPI, MCP, JSON)
- Implicit knowledge from training vs explicit runtime description

> This determines *what the agent can know* and *how safely it can reason*.

---

### Axis 3 — Degree of Autonomy
- Advisory (suggest only)
- Plan + confirm
- Act within constraints
- Act independently

> Autonomy is **not binary**.  
> It is a design decision that must be explicit.

---

### Axis 4 — Observability
- Human-visible behavior
- Logs and technical traces
- Semantic traces (intent → action → outcome)
- Silent failures possible?

> If you cannot explain *why* something happened, you cannot debug or govern it.

---

### Axis 5 — Responsibility and Governance
- User
- Agent builder
- Platform / middleware
- Service provider

> Responsibility that is not explicitly designed will be discovered only after failure.

---

## The Abstractions We Need (But Largely Lack)

### 1. Capability Abstraction (What can be done)

**Today**
- Tool schemas
- Function signatures

**Missing**
- Preconditions
- Side effects
- Cost and risk
- Reversibility

> Equivalent to API contracts *plus operational semantics*.

---

### 2. Intent Abstraction (Why something is done)

**Today**
- Prompts
- Hidden internal plans
- Inferred goals

**Missing**
- Explicit representation of:
  - user intent
  - agent-derived intent
  - scope and expiration

> Intent must become a **first-class object**, not an emergent property.

---

### 3. Autonomy Abstraction (Who decides what)

**Today**
- Ad-hoc “autonomy sliders”
- Product-specific UX choices

**Missing**
- Explicit authority boundaries
- Approval requirements
- Escalation paths

> Autonomy errors are **design errors**, not model errors.

---

### 4. Observability Abstraction (What actually happened)

**Today**
- Logs
- Tool traces

**Missing**
- Semantic traces linking:
  - intent → plan → actions → outcomes
- Business assertions:
  - what must always be true
  - what must never happen

> The dominant risk in agentic systems is **silent failure**.

---

### 5. Responsibility Abstraction (Who is accountable)

**Today**
- Legal ambiguity
- Blame shifting
- Product disclaimers

**Missing**
- Explicit responsibility boundaries between roles

> Responsibility must be architected — not retrofitted.

---

## Where MCP Helps

MCP should be understood precisely — neither oversold nor dismissed.

### What MCP *Does* Provide

#### 1. Capability Discovery
- Machine-readable enumeration of tools
- Explicit invocation schemas

#### 2. Invocation Consistency
- Structured requests and responses
- Reduced prompt brittleness
- Clearer failure modes

#### 3. Mediation Layer
- Natural insertion point for:
  - logging
  - policy enforcement
  - access control

> MCP standardizes the **interaction surface** between agents and tools.

---

## Where MCP Does *Not* Help

MCP does **not** solve the hard problems by itself.

### MCP does NOT solve:
- Intent representation
- Autonomy decisions
- Correctness or alignment
- Safety or ethics
- Responsibility assignment

A valid MCP call can still be:
- wrong
- harmful
- misaligned
- unethical

---

## The Correct Mental Model for MCP

> MCP is to agentic systems what HTTP was to the web:
>
> **necessary, foundational — and wildly insufficient on its own.**

HTTP did not give us:
- UX
- trust
- governance
- security
- business models

And MCP will not either.

But without HTTP, none of those emerged.

---

## Final Synthesis

We are building systems that **act in the world**.

The challenge is not making them smarter.

The challenge is making their:
- capabilities,
- intent,
- autonomy,
- behavior,
- and responsibility

**explicit, inspectable, and governable**.

MCP helps standardize *how* agents talk to tools.

The real work is defining *what those interactions mean* —  
technically, socially, and legally.
