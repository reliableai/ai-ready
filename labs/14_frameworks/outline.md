# Lesson 16 · Week 8 — Using AI Frameworks
_Instructor outline and notes_

## Target

90 minutes. Students have built from scratch in Labs 1–13: single LLM call,
stateful agents, context/memory management, tool calling, evals, monitoring,
councils, complex systems, key abstractions. This lecture answers: **now that
you know how the pieces work, should you throw them away and adopt LangChain?**

## Learning objectives

By the end of the lecture, students can:

1. Explain what frameworks actually provide beyond "less code" (integrations,
   standard patterns, observability hooks, ecosystem).
2. Read and write a small LangChain (LCEL) pipeline, and map each operator to
   the from-scratch version they built in Labs 2–4.
3. Compare LangChain vs. LlamaIndex vs. LangGraph along three axes —
   **orchestration, data/retrieval, state** — and pick an appropriate tool.
4. Explicitly design **memory and context management** using either framework
   primitives (ConversationBufferMemory, ConversationSummaryMemory,
   VectorStoreRetrieverMemory, LangGraph checkpointers) or their own code, and
   articulate the trade-off.
5. Instrument a running system with **observability** using LangSmith,
   Langfuse, or OpenTelemetry / OpenLLMetry, and explain the difference
   between vendor-specific tracing and open standards.
6. Apply a decision rule for when a framework is a net positive vs. a net
   negative for a given system.

## Prerequisites

- Lab 2 (stateful agent), Lab 3 (context management), Lab 4 (tool calling).
- Lab 9 (monitoring) — we will contrast their `monitoring.py` with
  framework-native tracing.

## Running example

A **course-assistant agent** with three tools, multi-turn memory, and a real
tool-calling loop. Retrieval is just one of the tools, not the whole thing —
which is the point, so students see memory/context management, tool-calling
loops, and observability all in one example.

Shared across all variants: `tools_shared.py` holds three plain-Python tools —
`search_syllabus` (retrieval), `get_office_hours` (deterministic structured
lookup), and `compute_grade` (pure function). Each framework wraps them in
its own type system.

Four implementations:

1. **From scratch** (`agent_scratch.py`) — ~150 lines. Explicit OpenAI
   tool schemas, explicit dispatch table, summary+window memory compressed
   by hand, structured `Trace.emit()` events. The honest baseline.
2. **LangChain** (`agent_langchain.py`) — same loop, written by hand on top
   of `bind_tools`. Tools come from `@tool`-decorated functions;
   `InMemoryChatMessageHistory` replaces the classic Memory classes;
   `BaseCallbackHandler` is the observability hook every vendor subscribes to.
3. **LlamaIndex** (`agent_llamaindex.py`) — `FunctionAgent` owns the loop;
   `ChatMemoryBuffer` handles token-budgeted memory. Shortest of the four,
   least transparent.
4. **LangGraph** (`agent_langgraph.py`) — the shape LangChain now recommends
   for non-trivial agents. `ToolNode` + `tools_condition` for the loop;
   `State` TypedDict + `SqliteSaver` for memory. Time-travel debugging via
   `get_state_history()`.

---

## Lecture flow (90 min)

### 0. Opener — "We waited until Week 8 on purpose" (5 min)

- Show the diff of lines of code: the Lab 2 stateful agent in ~80 lines vs.
  a LangChain agent in ~15. Ask: _which one do you want to debug at 3am?_
- Frame the lecture as a **decision framework**, not a tutorial. By the end,
  students should know how to decide, not just how to import.

### 1. What frameworks actually give you (15 min)

- Four categories of value:
  - **Abstractions** — prompt templates, retrievers, chains, memories, agents.
  - **Integrations** — swap OpenAI ↔ Anthropic, Pinecone ↔ Chroma ↔ Weaviate,
    without rewriting your pipeline.
  - **Observability hooks** — callbacks / tracing that plug into LangSmith,
    Langfuse, Phoenix, OpenTelemetry.
  - **Ecosystem** — shared mental model, cookbooks, Stack Overflow answers,
    hires who already speak the vocabulary.

- Counter-point (foreshadow §7):
  - Abstractions leak. Breaking changes are the norm.
  - "It's one line" is a feature of the demo, not of your production system.

### 2. The framework landscape, fast (10 min)

A 2×2 mental map:

|                     | Orchestration-first        | Data/RAG-first        |
|---------------------|----------------------------|-----------------------|
| **Batteries-in**    | LangChain, LangGraph, CrewAI, AutoGen | LlamaIndex   |
| **Minimalist**      | OpenAI Agents SDK, PydanticAI, Anthropic SDK | Haystack (lean), plain vector-store SDKs |

Also mention: DSPy (prompt *compilation*, different axis entirely), Mastra
(TypeScript-first), Semantic Kernel (Microsoft ecosystem).

### 3. Case study — the tool-calling agent (15 min)

- Walk through `agent_scratch.py` on screen: OpenAI tool schemas,
  explicit dispatcher, hand-written memory with summary+window compression,
  the classic while loop that dispatches tool calls and feeds results back.
  This is the pattern they built in L4; it's the honest baseline.
- Then `agent_langchain.py` — same loop, kept deliberately by-hand on top
  of `bind_tools` so the diff against the scratch version is 1:1 line for
  line. Point out what vanishes: the tool JSON schema, the dispatch table,
  the ad-hoc trace class.
- Discussion:
  - What did we save? (Schema generation, dispatch, callback plumbing,
    the option to swap provider with one import.)
  - What did we *still* write? (The loop, max_steps, system prompt,
    memory policy. Frameworks can't decide these for you.)
  - **Demo the hidden cost:** turn on `langchain.debug = True` and watch
    what a single turn actually does. Count the LLM calls. Explain why
    the tool-result messages in the history blow up the second-turn
    prompt if you don't compress.

### 4. Memory and context management (15 min)

This is where Lab 3 (context) becomes a _design_ lesson, not a coding one.

- Recap the from-scratch options from Lab 3:
  - Full history (grows without bound)
  - Windowed (loses long-range context)
  - Summarised (compression is lossy and costly)
  - Vector-retrieved (retrieval quality becomes the bottleneck)

- LangChain memory primitives and which Lab-3 variant they match:
  - `ConversationBufferMemory` → full history
  - `ConversationBufferWindowMemory(k=N)` → windowed
  - `ConversationSummaryMemory` → summarised
  - `ConversationSummaryBufferMemory(max_token_limit=...)` → summarised + windowed
  - `VectorStoreRetrieverMemory` → vector-retrieved
  - _Note:_ In LangChain ≥0.3, `RunnableWithMessageHistory` is the modern API;
    classic `Memory` classes still work but are considered legacy.

- LangGraph's model: state is an explicit typed dict, persisted by a
  **checkpointer** (in-memory, SQLite, Postgres, Redis). Conversations
  become "threads." Memory is a first-class object, not a hidden argument.

- Key teaching point: **memory is a design decision, not a feature**.
  The framework gives you six labelled boxes; you still have to pick the right
  one for your workload. Picking wrong is how production agents lose context
  at p95 token budgets.

### 5. Observability (15 min)

What you actually want (recap from Lab 9):
- Traces (call graph of every LLM/tool/retriever call in a request)
- Cost and latency per step
- Eval runs on sampled production traffic
- Regression detection across prompt / model versions

Four tiers of implementation:

1. **Hand-rolled** — their `monitoring.py` from Lab 9. Full control, zero
   ecosystem.
2. **Framework callbacks** — LangChain's `BaseCallbackHandler`,
   `CallbackManager`. Everything a framework does emits events; you subscribe.
3. **Vendor-integrated tracing:**
   - **LangSmith** (Anthropic-of-LangChain: tightly integrated, paid for teams,
     excellent LangChain / LangGraph support, eval runs in UI).
   - **Langfuse** (OSS, self-hostable, framework-agnostic via decorators and
     OTel ingestion).
   - **Phoenix / Arize** (OSS, strong on RAG tracing and eval visualization).
   - **Logfire** (Pydantic; OTel-native, strong type-safe DX).
   - **Helicone** (proxy-based, no code changes).
4. **Open standards** — OpenTelemetry GenAI semantic conventions + OpenLLMetry
   / Traceloop. Your traces become OTLP, any backend can read them. Future-
   proof against vendor changes.

Demo: enable LangSmith with one env var; show the same trace in LangSmith UI
and in Langfuse via OTel export. Point out that the trace IDs propagate.

Teaching point: **pick your observability layer before you pick your
framework**, not after. If you care about OTel, that constrains your
framework choice (LangChain/LangGraph and LlamaIndex both emit OTel now;
DSPy currently does not natively).

### 6. Alternatives, briefly (10 min)

- **LlamaIndex (`agent_llamaindex.py`)** — same agent in ~20 lines because
  `FunctionAgent.run()` owns the tool loop. Mental model: "LlamaIndex is
  a framework for your *data and default workflows*; LangChain is a
  framework for your *pipeline*." Good when their defaults match your
  problem (document QA, structured extraction); harder when you need to
  deviate from them.
- **LangGraph (`agent_langgraph.py`)** — "what LangChain agents should have
  been." The tool-calling loop becomes a two-node graph (`agent` ↔ `tools`)
  with a conditional edge. State is an explicit TypedDict; the checkpointer
  persists memory. Time-travel debugging via `get_state_history()`.
  The honest recommendation for new agentic systems where you want framework
  help but also want to debug the control flow.

### 7. When to use / when to avoid (10 min)

**Use a framework when:**
- You need to support multiple providers / vector stores.
- You want observability to "just work" (LangSmith/LangGraph/LlamaIndex).
- You're prototyping and optimizing for velocity over clarity.
- Your team is large and benefits from a shared vocabulary.
- You want pre-built integrations (Slack, Gmail, SQL, 100+ loaders).

**Avoid a framework when:**
- Your core loop is small and stable (a 3-step agent does not need a graph
  library).
- You have hard latency/cost budgets — every abstraction adds overhead and
  hides retries.
- You need to reason about exactly what token sequence the model sees.
- You are on the critical path for production SLAs and cannot tolerate
  breaking changes every few months.

**The "framework tax" checklist** (share with students):
- Can I print the exact prompt that was sent?
- Can I step through the retry logic without reading framework source?
- Can I pin a version and not have to upgrade for 6 months?
- Is my observability independent of the framework (OTel) or coupled to it?
- If the framework were abandoned tomorrow, how many days would it take to
  rip it out?

### 8. Wrap-up + homework (5 min)

Homework (one week):
1. Pick one component of your running project. Rewrite it with LangChain,
   LlamaIndex, **or** LangGraph. Keep both versions in git.
2. Measure: lines of code, p50 and p95 latency, cost per call, and a qualitative
   note on debuggability.
3. Add LangSmith **or** Langfuse tracing. Link three interesting traces in
   your report.
4. Write a 1-page decision note: would you ship the framework version? Why?

---

## Discussion prompts

- "LangChain's Expression Language hides six LLM calls behind one pipe
  operator. Is that good DX or dangerous DX?"
- "If memory is a design decision, why does every framework ship ten different
  memory classes? What does that tell you about the design space?"
- "You cannot add observability to a system you don't own. How do the tracing
  stories of these frameworks differ, and which one would you bet on for five
  years?"
- "A fifth-year grad student says 'frameworks are just vendor lock-in for
  people who can't read source.' Is that fair?"

## Notes on what to skip if running short

- §2 (landscape survey) can be reduced to showing the 2×2 table.
- §6 (alternatives) can be cut if §3 ran long — the notebook has the code.
- Never cut §4 (memory) or §5 (observability): they're the reason this lecture
  follows Lab 3 and Lab 9.
