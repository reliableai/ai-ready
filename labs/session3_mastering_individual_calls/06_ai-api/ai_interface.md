```markdown
# MCP standardization notes (minimum standard, maximum leverage)

## What do we need to standardize?

The goal of a standard (like MCP) is **plug-and-play interoperability** between:
- **Clients/agents** (LLMs, orchestrators, IDEs, automations)
- **Tool servers** (internal services, SaaS, databases, enterprise systems)

To get that, the high-leverage things to standardize are the “interface surface”:

### 1) Capability discovery
- A consistent way to ask: **“What can you do?”**
- Enumerate tools (and optionally resources/prompts) with enough metadata to decide usage.
- Support **capability negotiation** and **versioning**.

### 2) Tool invocation contract
- A consistent request/response envelope:
  - tool name
  - args
  - correlation/request IDs
  - success vs error
- A **standard error shape** (type/code/message/details; retryable vs not).

### 3) Structured schemas + metadata (the big win)
- **Input/output schemas** (e.g., JSON Schema or equivalent)
- Clear descriptions + examples
- Tool properties that matter to agents:
  - side-effecting vs read-only
  - idempotent vs non-idempotent
  - latency/timeout hints (optional)
  - pagination/streaming support (optional)

### 4) Authn/Authz
- Minimal, well-defined authentication flows.
- **Scopes/permissions** tied to tools/resources (principle of least privilege).
- Clear token handling model and where secrets live.

### 5) Transport + streaming semantics (keep small)
- Prefer “prove it works everywhere” transports.
- If streaming exists: standardize frame/event semantics (start/data/end, partial results, cancellations).

### 6) Minimal observability
- Correlation IDs, structured logs/traces (even optional fields help a lot).
- Basic usage/error telemetry fields.

---

## Minimum we need (MVP standard)

If we want the smallest standard that still enables an ecosystem:

1. **`list_tools()`**  
   Returns tool specs: `{name, description, input_schema, output_schema, auth_scope, side_effects, risk_level, data_sensitivity, requires_confirmation}`

2. **`call_tool(name, args)`**  
   Returns either:
   - `{result: ...}` or
   - `{error: {type, code, message, details, retryable}}`

3. **Schemas** for inputs/outputs  
   Enables validation + automated clients.

4. **Auth** (one widely adoptable baseline + scopes)

Everything else (resources, prompts, streaming, deep observability) can be “phase 2”.

---

## Simplest thing that provides the most value

If you standardize only ONE thing, do this:

### ✅ Canonical “Tool Manifest” + Schemas (+ minimal safety/autonomy flags)
A machine-readable manifest that any agent can consume:
- list of tools + descriptions
- input/output schemas
- side-effect flags + risk level + required scopes
- versioning info

Why this is the best ROI:
- enables **automatic UI generation** (forms)
- improves **tool selection** (structured + semantic)
- reduces runtime failures (validation)
- makes tools portable across frameworks/models
- enables systematic evaluation and testing
- enables consistent governance (confirm writes, block destructive, etc.)

Soundbite:
> Standardize **how tools describe themselves** and **how they are called**, not how backends are implemented.

---

## Autonomy and control: where do we specify it?

Agents aren’t just “API clients”. They decide, plan, and act.
So we need a place to encode **how much autonomy is allowed** and
**what verification is required**.

### The 3-layer model (recommended)

**A) Tool-level policy metadata (server declares invariants)**
- `side_effects`: `none | read_only | write | destructive`
- `risk_level`: `low | medium | high`
- `data_sensitivity`: `public | internal | pii | financial | secrets`
- `requires_confirmation`: `never | always | conditional`
- `confirmation_type` (optional): `user_ok | user_text | supervisor_ok | 2fa | ticket_id`
- `allowed_automation`: `manual_only | assisted | fully_automated` (optional)

**B) Org/runtime policy (client config declares governance)**
- “Block destructive tools in prod”
- “Require confirmation for any write”
- “Only allow finance.write for certain roles”
- “Only allow calendar access for approved tenants”
- “Require citations/verification in regulated domains”

**C) Session/user consent (user sets the dial)**
- “Auto-run read-only tools”
- “Ask me before sending emails”
- “Never access calendar”
- “Only run tools 9–5”

**Layering rule:** effective autonomy = **minimum** of (server invariants, org policy, user consent).

### Verification ladder (teachable heuristic)
0. **No-run** (blocked)
1. **Read-only auto-run**
2. **Write with preview/diff + confirm**
3. **Write with strong confirmation** (type-to-confirm, ticket, 2FA)
4. **High-risk with dual control** (user + supervisor)
5. **Full automation** (only low-risk, bounded, monitored, reversible)

---

## Why do we need servers (and typically one client connection per server)?

This is the “architecture” part: MCP isn’t just a schema; it’s a *runtime boundary*.

### Why a server boundary exists at all
A server is where we centralize responsibilities that are **hard/unsafe** to push into the LLM client:

1. **Security boundary**
- Keep secrets out of the agent process (API keys, DB creds, service accounts).
- Enforce least-privilege and audit access centrally.

2. **Policy enforcement**
- Validate inputs against schemas.
- Apply org constraints: allowlists, rate limits, “destructive requires approval”, PII gating.

3. **Stable integration surface**
- Backends change; server absorbs churn.
- Server can wrap many internal APIs into coherent tools.

4. **Operational controls**
- Logging, tracing, metrics, quotas, caching, retries, circuit breakers.
- Consistent error normalization for agents.

5. **Performance and locality**
- Put the integration close to data (inside VPC, near DBs).
- Stream results efficiently, paginate, batch calls.

6. **Multi-tenant / multi-user mediation**
- Server can map user identity → entitlements → downstream credentials.

### Why “one client per server” often shows up in practice
(Interpretation: a dedicated MCP client *connection* to each MCP server instance.)

1. **Isolation of trust and permissions**
- Each server represents a distinct trust domain (e.g., HR vs Finance vs DevOps).
- Separate connections make it easier to apply per-domain policies and scopes.

2. **Dependency and failure containment**
- If one server is slow/down, it shouldn’t stall others.
- Independent connections allow independent timeouts, retries, backpressure.

3. **Different transports / auth / lifecycle**
- Each server might require different auth tokens, renewal cadence, or network path.
- Per-server client objects encapsulate that complexity cleanly.

4. **Concurrency and streaming semantics**
- Streaming responses and cancellations are simpler with a dedicated channel.
- Avoid interleaving issues and simplify correlation.

5. **Deployment reality**
- Servers can be local processes, remote services, per-tenant endpoints, or ephemeral sandboxes.
- A per-server client is the natural handle to “that endpoint”.

### BUT: it’s not necessarily “one client forever”
Good discussion point: there are valid variations:
- **Connection pooling** per server for throughput (still “per server” logically).
- **Gateway/aggregator server** that fronts multiple downstream MCP servers (trades simplicity for centralization).
- **Service mesh** patterns for auth/routing (server boundary remains, but wiring changes).

**Teaching-friendly framing:**
- “Per-server client handle” is primarily about **trust + lifecycle + failure isolation**,
  not a hard technical limitation.

---

## Lessons from “standards that didn’t work well” (UDDI, WSDL, and friends)

### UDDI
- Discovery without trust/governance and maintained metadata is useless.
- Registries weren’t meaningfully populated; teams hard-coded endpoints anyway.

Takeaway:
- Discovery must be **local, governed**, and backed by **accurate tool manifests**.

### WSDL/SOAP
- Overly heavy specs/tooling; debugging and adoption pain.
- Contracts described syntax, not semantics; codegen lock-in.

Takeaway:
- Keep MCP contracts **minimal + ergonomic**; schemas should be easy to author and evolve.

### CORBA (historical parallel)
- Over-ambitious abstraction hid distributed-systems realities.

Takeaway:
- Standardize interfaces and make side-effects/failures explicit.

---

## Design principles for a “winning” MCP-like standard

1. **Minimal surface area**
2. **Optimized for agent consumption** (schemas + metadata)
3. **Evolvable** (versioning, deprecation)
4. **Works with existing stacks** (wraps REST, doesn’t replace)
5. **Low friction** (hello world in minutes)
6. **Governable autonomy** (tool guardrails + org policy + user consent)
7. **Server boundary for secrets/policy/ops**

---

## Discussion prompts (to use in class)

1. What *minimum* policy fields are truly necessary for safe autonomy?
2. Should “requires_confirmation” be tool-level (server-owned) or client-owned?
3. What’s the right split between:
   - server-enforced invariants (hard safety)
   - org policy (compliance)
   - user consent (UX and trust)
4. When does a gateway/aggregator beat per-server clients?
5. What breaks if tool manifests drift from runtime behavior—and how do we prevent drift?
```
