# Demo 6 · Multi-agent traces

Pairs with Slides 29–32 of L10 (Section 04 — agents and systems of agents). Stage B in earnest. Where Demo 5
showed a single-agent RAG trace, this one adds an **orchestrator**
that routes each question to one of three **sub-agents** and
synthesises the final answer. With more spans come more failure modes
— and three of them only exist in multi-agent systems:

```
orchestrator.task                   ← root
  ├── orchestrator.plan             ← LLM: pick a sub-agent
  ├── subagent.<name>               ← one (happy) or many (trouble)
  │    ├── llm.call  (decide)       ← sub-agent reasons
  │    └── tool.*    (act)          ← db_query / kb_search / http
  └── orchestrator.synthesize       ← LLM: compose answer
```

## What's here

```
demos/6_multi_agent/
  gen_multi_agent.py   ← produces 60 traces, ~400+ spans
  spans.ndjson         ← one span per line
  spans.js             ← window.__SPANS__
  trace_viewer.html    ← the Demo 5 viewer, extended with mode badges
  README.md
```

## The three failure modes

These are seeded deterministically (`seed=19`, frozen `NOW`). The
counts vary slightly trace-to-trace but the breakdown stays close to:

  - **43 `ok`** — orchestrator picks the right sub-agent, tool
    returns a result, synthesize hedges-free.
  - **~13 `cascading_repair`** — sub-agent's tool 5xx's.
    Orchestrator emits a repair span, retries on a different
    sub-agent, which also fails. Synthesize runs with 150 input tokens
    and `answer.confidence="low"`. Three red spans in the waterfall
    for one trace.
  - **~2 `planner_loop`** — orchestrator calls the correct sub-agent
    twice for the same question, with near-identical prompts.
    Total latency roughly doubles. Tool results aren't cached
    anywhere; the trace is the only place this is visible.
  - **~2 `role_confusion`** — db_agent decides to call
    `tool.kb_search` instead of its own `tool.db_query`. The span is
    parented correctly (under `subagent.db_agent`) but the
    `tool.name` attribute is wrong. Single-service logs see two
    unrelated successes; the trace shows the misrouting.

Each root span carries a `failure_mode` attribute (when set) so the
viewer's left panel can render a purple badge. Clicking the badge'd
rows jumps straight to the failed waterfalls.

## How to run

```bash
python gen_multi_agent.py
open trace_viewer.html     # or double-click
```

Generator output:

```
wrote ~420 spans across 60 traces
  error traces: ~13
  span-name counts: {'orchestrator.task': 60, 'llm.call': ~210,
    'subagent.web_agent': ~28, 'subagent.kb_agent': ~29,
    'subagent.db_agent': ~18, 'tool.http': ~28,
    'tool.kb_search': ~30, 'tool.db_query': ~17}
  failure-mode distribution: {'planner_loop': 2, 'cascading_repair': 13,
    'role_confusion': 2, 'ok': 43}
```

## Teaching beats (Slide 32)

1. **Happy path first.** Open any OK trace. Point out the five spans:
   root, plan, one subagent, the sub-agent's two children (llm.call +
   tool.*), and synthesize. Note how synthesize's `input_tokens`
   jumps from ~50 (plan) to ~1000+ (synthesize fed the sub-agent's
   result). The trace *proves* information flowed; a flat log row
   can't.
2. **Cascading repair.** Pick a red trace with
   `failure_mode=cascading_repair`. Three red spans in the waterfall:
   first sub-agent's tool, a repair LLM call in the middle, second
   sub-agent's tool. Root inherits ERROR. The synthesize step *still
   ran* — it hedged because `answer.confidence="low"`. Discuss why
   hedge-answering is a correct design choice even when the data
   pipeline is broken.
3. **Planner loop.** Filter the trace list to `failure_mode=planner_loop`
   (purple badge). Two `subagent.<same_name>` under one root. The
   questions are almost identical. Point to the cost waste — we paid
   for retrieval *twice*. Slide 31 calls this the cheapest real-world
   failure mode to catch with traces, because it's invisible to
   per-call logs.
4. **Role confusion.** Filter to `failure_mode=role_confusion`. The
   db_agent span has a `tool.kb_search` child instead of
   `tool.db_query`. Click the tool span — the `tool.owner` attribute
   still says `db_agent`. This mismatch is the fingerprint. If you
   alert on `tool.owner != expected_tool_family`, you catch every
   role-confusion before it goes to prod.
5. **What an alert rule looks like.** Closing beat. "Multiple
   sub-agent spans under one root with the same agent.name" → planner
   loop. "ERROR span + orchestrator.repair span" → cascading_repair.
   "tool.name prefix doesn't match subagent.<X>" → role_confusion.
   All three rules are one-liners over the span stream.

## Reading the ndjson

```bash
# Which sub-agents ran most?
jq -r 'select(.name | startswith("subagent."))
       | .attributes["agent.name"]' spans.ndjson | sort | uniq -c

# Every trace's failure_mode + span count.
jq -s '
  group_by(.trace_id) |
  map({trace: .[0].trace_id,
       spans: length,
       mode:  ([.[] | select(.parent_span_id==null)] | .[0].attributes.failure_mode // "ok")})
' spans.ndjson | head -30

# Cost per trace (sum of input+output tokens across all llm.call spans).
jq -s '
  group_by(.trace_id) |
  map({trace: .[0].trace_id,
       tokens: ([.[] | select(.name=="llm.call")
               | .attributes["gen_ai.usage.input_tokens"]
                 + .attributes["gen_ai.usage.output_tokens"]] | add)})
  | sort_by(-.tokens) | .[0:5]
' spans.ndjson
```

## What's deliberately simple

- **No real concurrency.** In production the orchestrator might call
  two sub-agents in parallel. The spans would overlap in time; our
  generator serialises them so the waterfall reads left-to-right.
  The failure-mode rules still apply.
- **No sub-agent-to-sub-agent calls.** All sub-agents are leaves
  under the orchestrator. Real meshes have sub-agents calling other
  sub-agents. The parenting model scales — you'd just see deeper
  trees.
- **Three sub-agents.** In practice you'd have 8–20. Routing gets
  harder; planner_loop becomes more common.
- **No propagation headers.** We're in one process. A real multi-
  service orchestrator injects `traceparent` on every outgoing HTTP
  call so downstream services continue the trace. That's the
  distributed in "distributed tracing" — out of scope here, core
  production concern.
