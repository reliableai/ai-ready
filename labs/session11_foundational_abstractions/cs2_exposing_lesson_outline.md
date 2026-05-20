# Session outline: How to expose your API to an AI agent

Companion to `2-how to expose your api to an ai agent.md`. The recipe doc is the spine; this is the delivery plan — what to demo, what to discuss, what to assign. 75–90 minutes total; a 45-minute cut at the bottom.

## Session arc

### 0. Open with the demo (10 min)

Don't introduce the topic — show it. Run `python -m wazzup.client.main`, let it prompt, pick `alice`, and walk through three flows:

- `what topics exist?` — one tool call, one prose answer.
- `show me the last 5 in daily-standup` — two tool calls chained; point out the second `[tool: ...]` line.
- `post "shipping today" to daily-standup` — the `[CONFIRM]` prompt fires. Approve. Re-run a read to show the agent personas auto-replied.

Then ask the room: *"What just had to exist for that to work?"* Let them list what they noticed: a list of tools, descriptions, an HTTP loop, parameter shapes, the confirm prompt. Write the list on the board. That list becomes the section map for the rest of the session.

### 1. Frame the question (5 min)

Anchor the *"we have a working HTTP API"* claim concretely. Three things on screen, in this order:

- **The wazzup UI tab** (`http://localhost:8001`) — have alice post a message; *"this is what session 1 built: the API and its first consumer, the web UI."* **Keep browser DevTools open (F12 → Network tab)** alongside the UI. Every click in the UI produces a visible HTTP call with full headers, payload, and JSON response in DevTools — lands *"the UI is just another HTTP consumer"* without you having to argue for it.
- **Swagger UI tab** (`http://localhost:8000/docs`) — scroll the route list; *"this is the full HTTP surface — 12 routes. Anything that speaks HTTP can call them."* You'll point at this tab again in §2 when defending the catalog's curation.
- **Optional one-line curl** in a terminal:
  ```bash
  curl -H "X-User-Slug: alice" http://localhost:8000/topics
  http localhost:8000/topics X-User-Slug:alice
  ```
  JSON comes back. *"And here's a third consumer — a shell one-liner. Same surface, no UI, no framework."*

Then pose the framing question:

*"We have a working HTTP API and a working LLM. What abstractions do we need to bridge them — and which of those abstractions exist as libraries, conventions, or standards already, vs. things we have to hand-roll?"* This is the §1 framing from the recipe; it sets up session 3 (MCP) by making *"what's standardized?"* an explicit question.

Timing inside the 5 minutes: ~1 min UI, ~1 min /docs, ~30 sec curl (skip if you're tight), ~2–3 min question + audience answers on the board. The answers map onto §2 (curation), §3 (behavior signaling), and §5–6 (loop + dispatcher) — write them up so you can refer back as the session unfolds.

### 2. Decision and Curation — §2 (10 min)

First, disucss what we would like to expose to an AI client. Then lets decide what we may want to expose. 

Open `wazzup/exposed_tools.md` next to the Swagger UI tab from §1 (`http://localhost:8000/docs`). The catalog has 7 entries; the Swagger surface has 12 routes. Walk the diff out loud: `DELETE /conversations/{slug}/messages`, `POST /users`, `POST /topics` are in Swagger but **not** in the catalog. Ask: *"Why didn't I expose those? Would you change my picks?"* Land the rule of thumb (*"would I let a confused new contractor call this?"*). Tie to the cautious-default policy in `load_tools.py` — you have to opt in to *"safe"*; defaults assume *"dangerous."*

### 3. Descriptions — §4 (10 min)

Pick one tool's description — `post_message` is the most informative. Walk through the four things the prose carries: *what the tool does, when to use it, when NOT, what it returns, what side effects fire*. Then strip the description down to its first sentence and re-run the demo. Watch the agent struggle. (Edit `exposed_tools.md` and restart the client live.) This is the demo that lands *"bad descriptions = bad agents"* fastest.

### 3b. How the catalog reaches the LLM (3 min)

A short technical aside that explains *why* §3's strip-down demo works — and bridges naturally into §4's flag discussion.

At startup, `wazzup/client/main.py:run_repl` calls `load_tools(catalog_path)` where `catalog_path` defaults to `wazzup/exposed_tools.md` (see `main.py:DEFAULT_CATALOG`). The loader reads the file *once*, splits on `## ` headers, parses each tool's YAML block, and returns a list of dicts. That same list is then handed to the LLM on every API call inside the REPL loop:

```python
# main.py:run_repl
def run_repl(...):
    tools = load_tools(catalog_path)         # ← runs ONCE at startup
    ...
    while True:                              # ← REPL loop (one iteration per user input)
        ...
        for _ in range(MAX_TURNS):           # ← within-turn loop (one per LLM round-trip)
            response = llm.chat(messages=messages, tools=tools)   # ← same `tools` every time
            ...
```

Edits to `exposed_tools.md` only take effect the next time the client starts. (Live-edit + restart is exactly the §3 strip-down demo.)

Inside the OpenAI adapter (`llm_adapter.py:_to_openai_tool`), each dict gets translated into the OpenAI tools schema:

```python
{
    "type": "function",
    "function": {
        "name":        tool["name"],
        "description": tool["description"],   # the prose paragraph from .md
        "parameters":  tool["input_schema"],  # the YAML "input:" block
    },
}
```

So the LLM literally sees the prose you wrote in the markdown, embedded in the function definition the OpenAI API exposes. That's why editing `exposed_tools.md` and restarting the client changes the agent's behavior.

**What about the user's typed input?** It doesn't go to the LLM as-is — it's rendered through a Jinja2 template at `wazzup/client/prompts/user_turn.md.j2` before becoming a `{"role": "user", "content": ...}` message. Today the template renders two things: the user's just-typed line, and any prior conversation history as prose (see *"Where does conversation history go?"* immediately below for the full format). The reason to have a template at all is **client-side prompt control**: every framing decision — what to include from history, how to format it, what additional context to inject (system constraints, identity hints, format requirements) — happens in the template, not in `main.py`. Keeps the LLM-facing surface and the dispatch logic separate, and gives the catalog (server-owned) and the prompt (client-owned) two clean seams instead of one tangled one. The template itself carries a Jinja comment block documenting its role; open it during the session so the room sees how it's annotated.

**Where does conversation history go?** *In the template, not in `messages=[...]`.* This is a deliberate design choice worth calling out.

Another way would be to put history in the `messages=[...]` API parameter as structured entries — `[{"role": "user", ...}, {"role": "assistant", ...}, ...]` — and let OpenAI handle threading. Here we deliberately don't do that. Why: it hardcodes the format of historical context and gives the client zero control over what the LLM sees about prior turns. No summarization, no truncation, no filtering — the whole trace verbatim, every call.

Instead, the client owns a `history: list[{"user": ..., "assistant": ...}]` and the Jinja template renders it into the *user prompt*:

```jinja
{% if history -%}
Prior turns in this session:

{% for turn in history -%}
[you] {{ turn.user }}
[agent] {{ turn.assistant }}

{% endfor -%}
---

{% endif -%}
{{ user_input }}
```

Now the client controls everything — change `for turn in history` to `for turn in history[-3:]` to keep only the last 3; replace the loop with a single summary; filter to turns mentioning a particular topic — all template edits, no Python change.

**One wrinkle worth mentioning:** *within a single user turn*, structured `messages` still get used. The OpenAI tools API requires `tool_call_id` matching between assistant tool-call messages and the corresponding tool-result messages, so the inner dispatch loop can't collapse to prose. The split is:

- **Within-turn:** structured `messages` list, recreated fresh each user turn. Tool call → tool result threading happens here.
- **Across-turn:** prose-rendered history in the template. Client owns the format.

Type `/reset` at the `you>` prompt to clear history mid-session.

**Pedagogical payoff:** when someone asks *"how do I make the agent remember less?"* or *"summarize history into one sentence?"* or *"only remember turns about deletion?"* — the answer is **edit `user_turn.md.j2`**. The room sees that the prompt is fully under client control and the LLM-facing surface is one rendered string, not a structured trace dictated by a vendor's API.

**Only `name`, `description`, and the input schema go to the LLM.** The behavioral flags (`destructive`, `read_only`, `requires_confirmation`, etc.) live in the client-side dict and are consulted by `_should_prompt` and the dispatch policy in `main.py` — they're never sent to the LLM. Two audiences for the same catalog entry:


| Field                                 | Who reads it                 | Where it's used                    |
| ------------------------------------- | ---------------------------- | ---------------------------------- |
| `name`, `description`, `input` schema | the **LLM** (via the API)    | picking the tool, formatting args  |
| `read_only` / `idempotent` / etc.     | the **client** (`main.py`)   | auto-execute vs. confirm vs. block |
| `endpoint`                            | the **client** (`invoke.py`) | building the actual HTTP request   |


Bridge into §4: **descriptions teach the LLM what to do; flags tell the client what to allow.** Same file, two readers, two different jobs.

**Twist for the room:** *"What if we DID send `destructive: true` as part of the prose description? Would the LLM behave differently?"* Sometimes — it's prose, the LLM might respect it or not — but weaker than a flag the client enforces. 

### 4. Behavior signaling — §3 (15 min)

The four facets (`read_only`, `idempotent`, `destructive`, `external_side_effects`) plus `requires_confirmation`. Open `exposed_tools.md`, point at the YAML flags. Each flag is a *claim* about the tool that the **client** (not the LLM — see §3b) consults to decide what to do.

**What each flag means in our convention:**


| Flag                    | Claim about the tool                                                       | Default when omitted | What the client does                                                |
| ----------------------- | -------------------------------------------------------------------------- | -------------------- | ------------------------------------------------------------------- |
| `read_only`             | Calling does not mutate state.                                             | `false`              | If `true`: auto-execute; safe to retry; no prompt.                  |
| `idempotent`            | Two identical calls have the same effect as one.                           | `false`              | If `true`: safe to retry on transient failure.                      |
| `destructive`           | Removes or overwrites state in a way that's hard to undo.                  | `true`               | If `true`: block or hard-prompt. None in our catalog claim it.      |
| `external_side_effects` | Causes something to happen *outside* the service (email, charge, webhook). | `true`               | If `true`: treat like destructive. None in our catalog claim it.    |
| `requires_confirmation` | Provider demands a human go/no-go regardless of the other flags.           | `false`              | If `true`: prompt the human the first time; remember per tool name. |


**Asymmetric defaults are deliberate.** `destructive` and `external_side_effects` default to `true` — a tool author has to opt *in* to the safe claim. `read_only` and `idempotent` default to `false` — the cautious assumption is that you can't claim them either. `requires_confirmation` defaults to `false` only because most tools don't need it; flagging the ones that do is a deliberate act. The whole policy: *assume the tool is unsafe until proven otherwise.*

**But where do these defaults actually live? In the *client's loader*.** Concretely, in `wazzup/client/load_tools.py:65–70`:

```python
"read_only":             bool(meta.get("read_only", False)),
"idempotent":            bool(meta.get("idempotent", False)),
"destructive":           bool(meta.get("destructive", True)),
"external_side_effects": bool(meta.get("external_side_effects", True)),
"requires_confirmation": bool(meta.get("requires_confirmation", False)),
```

The catalog file itself (`exposed_tools.md`) is **silent** on what an omitted flag means. The defaults are documented in §3 of the recipe doc, but they're not encoded anywhere a different client could discover them. The convention is *implicit*: catalog author and client author have to be reading from the same playbook.

**This is fine for a single-team deployment, and a real problem for anything cross-team.** A different client reading the same catalog file could hardcode different defaults — defaulting `destructive` to `false`, say — and silently treat tools we consider unsafe as safe. No warning, no error, just different behavior from the same input. The catalog gives a foreign reader no way to discover what we assumed.

Three places defaults *could* live, in increasing order of portability:

| Where defaults live                         | Concretely                                                | Trade-off                                                                                  |
| ------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| **(a) In the client's loader** (today)      | `load_tools.py:65–70`, doc'd in §3 of the recipe          | Implicit; correctness assumes every reader has read our recipe. Works inside one team only. |
| **(b) In the catalog file itself**          | A `defaults: {...}` YAML preamble at the top of the catalog | Self-describing — every reader of the file learns the defaults from the file.              |
| **(c) In a shared protocol spec**           | A standard's reference doc (e.g. MCP's `ToolAnnotations`) | Maximum portability — every compliant client agrees automatically without reading our docs. |

**The point worth landing in the room: client-side defaults are convention, not contract.** Our catalog file plus our recipe doc together describe the agent surface; one without the other is incomplete. Session 3's MCP discussion picks this up — MCP standardizes both the flag *names* and their *defaults* via `ToolAnnotations`, which is the cross-ecosystem combination of (b) and (c) above.

Then ask: *"Why is `external_side_effects: false` for `post_message`, but `requires_confirmation: true`?"* Forces the broadcasts-vs-external-systems distinction (from §3 of the recipe).

Then walk the policy in `main.py:_should_prompt` — *per-tool-name approval*. Discussion: *"What goes wrong with per-tool-name? What's better? What's the cost of better?"* The doc has the answer (per-target / propose-then-confirm); let the room reach it before you show.

### 4b. The flag vocabulary is our convention (4 min)

A point worth calling out explicitly: the flag *names* we put in the catalog (`read_only`, `idempotent`, `destructive`, `external_side_effects`, `requires_confirmation`) are **our convention**. We chose them. We wrote the catalog. We wrote `_should_prompt`. Producer and consumer of the convention are the same person, so nothing breaks.

The moment that stops being true — a different client reads our catalog, or our client reads someone else's catalog — the convention doesn't transfer. Flags called `is_dangerous` or `mutating` in another catalog mean nothing to `_should_prompt`; the call would go straight through with no confirmation. Same N×M problem that shared vocabulary exists to prevent.

**The alternative worth naming explicitly in the room: flags-as-prose.** Instead of a structured `requires_confirmation: true` boolean, put the meaning directly in the description text:

> *"This operation is destructive — always ask the user to confirm before calling. If the user has already approved a similar call earlier in this conversation, you may skip the confirmation."*

The LLM reads the prose, asks the user, and tracks the answer in its own growing conversation history. No client-side policy code at all — the LLM is the policy engine. The "memory of preferences" lives inside the LLM's message history, not in a Python `set`.

Trade-off worth weighing with the room:


| Approach                        | What it gives you                                                          | What it costs                                                                 |
| ------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **Structured flags** (us)       | Deterministic, enforceable by the client, cheap (no LLM tokens), auditable | Vocabulary lock-in across ecosystems; limited expressiveness (boolean yes/no) |
| **Flags-as-prose** (LLM-driven) | No vocabulary problem (English is the universal substrate); expressive     | Non-deterministic; client can't enforce; token-expensive every turn           |


We picked structured flags because we want **enforcement**: the client can refuse to call `post_message` even if the LLM forgot to ask the user — one boolean, one line of policy code, done. Prose-only puts the policy decision inside the LLM, which is fine when you trust the model and the prompt, less fine when prompt injection or model variance enters the picture.

**Set up the §7 reveal without naming MCP yet:** *"If we want a flag vocabulary that works across many clients and many catalogs — without us writing a per-server adapter for every other vendor's flag names — we need agreement on the names. Either everyone copies our convention, or someone proposes a shared standard. Hold that thought; we'll come back to it."*

### 5. The loop & the dispatcher — §6, §7 (15 min)

Open `main.py:run_repl` and `invoke.py` side by side. First name what each file does, then drive the three teaching points:

**What each file does at a glance:**

- `**main.py:run_repl`** — the **agent loop**. Reads a line of user input; renders it through `wazzup/client/prompts/user_turn.md.j2` (the client-owned prompt template — see §3b) with the cross-turn `history` list baked in; hands the rendered prompt and the tool catalog to the LLM; gets back either plain text (we're done — print it, append `{user, assistant}` to `history`, prompt next) or one-or-more `tool_calls`. For each tool call, dispatches it (applying the `_should_prompt` confirmation gate from §4) and feeds the result string back to the LLM as a structured tool message. Loops until the LLM emits plain text or `MAX_TURNS` is hit. Within-turn structured `messages` are recreated each turn (the OpenAI tools API requires `tool_call_id` matching); across-turn `history` is rendered as prose into the template. Type `/reset` at the prompt to clear `history` mid-session.
- `**invoke.py`** — the **HTTP dispatcher**. Takes one tool call (name + args), looks up the tool's `endpoint` in the catalog (e.g. `"GET /topics/{slug}"`), parses it into method + path template, fills path placeholders from args, sends the rest as query string (GET) or JSON body (POST), adds the `X-User-Slug: <slug>` header for identity, and returns the response body as a string. On 4xx/5xx or network failure, returns `"error 404: ..."` or `"error: timeout calling ..."` strings rather than raising — that's the *errors-as-signal* point below.

Together: the loop decides *what* to call; the dispatcher knows *how* to call it. `exposed_tools.md` is the shared seam — the loop reads tool names, descriptions and arg shapes from it (and forwards them to the LLM, per §3b); the dispatcher reads the `endpoint` field to build the request.

**Three things to land:**

- **The LLM controls termination.** No `tool_calls` in the response → stop. The `max_turns` is a safety net.
- **Tool results are just `messages` entries.** Show how `messages` grows *within* one user turn (assistant message → tool message → assistant message → tool message → final assistant text), capturing the dispatch trace. Across user turns, `messages` is recreated fresh — the cross-turn `history` list (rendered into the template, see §3b) carries only the user/assistant final pair from each completed turn.
- **Errors are signal, not crashes.** Demo it live: edit a tool's `endpoint` to a bad path, restart, ask a question. The LLM sees `error 404` in the tool result and adapts (or surrenders gracefully).

### 6. What's missing (5 min)

Walk the *"What we haven't built / standardized / solved"* section of the recipe. Spend most of the time on **Authentication** — the agent has no real auth in the reference; it just passes `X-User-Slug`. Name this as the deferred problem that session 3's MCP authorization story addresses.

### 7. Toward MCP (5 min)

Land the punchline: *"You just hand-rolled four components — the loader, the loop, the HTTP dispatcher, and the LLM adapter. Session 3, MCP gives you all four for free, plus a contract any agent on the planet can speak. Same 7 tools, different door."* Open `wazzup/mcp/server.py` next to `wazzup/client/`. The MCP file is mostly the same tool wrappers we already have in `exposed_tools.md` (one `@mcp.tool()` decorator per function); the loader/loop/dispatcher/adapter machinery from `wazzup/client/` is *gone* — those four files of work are replaced by *being an MCP server* and letting any MCP-aware host (Claude Code, Cursor, etc.) bring its own loop and dispatcher.

## Exercises

Assign as homework, or use as a 30-minute lab block if there's one.

- **Easy.** Write the description and YAML block for `react_to_message(message_id, emoji)`. Critique each other's pair-wise. *What's missing? What's redundant? Would the LLM pick this tool over `post_message` correctly?*
- **Medium.** Change the confirmation policy in `main.py` from per-tool-name to per-`(tool_name, conversation_id)`. Watch what changes in the second `post_message` demo.
- **Stretch.** Add a new tool to the catalog (e.g. `count_messages_from_user`), implement it in `api/messages.py` and `http/messages.py`, and verify the existing client picks it up with zero changes to the client code. Lands the *"catalog is the seam"* observation.

## Discussion prompts to keep in reserve

- *"You exposed `post_message` but not `DELETE /conversations/{slug}/messages`. Defend both choices."*
- *"The catalog says `external_side_effects: false` for `post_message`. Other readers might disagree — visible to 30 colleagues feels external. What would change if we added a `broadcast: true` flag? Who reads it?"*
- *"In the loop, the LLM controls termination. Is that good or bad? When does it bite?"*
- *"What's the LLM-side cost of having 20 tools vs. 80? Why does curation matter for accuracy, not just safety?"*

## Pre-session prep

**Done in advance (10 min):**

- Fresh `wazzup.db` seeded: `uv run python -m examples.seed`. Idempotent — re-running the morning of is fine.
- `.env` has `LLM_API_KEY` set; `LLM_PROVIDER` / `LLM_MODEL` match the model you'll use live.
- Two tabs open in the editor: `wazzup/exposed_tools.md` and `wazzup/client/main.py`. You'll switch between them six or seven times.
- **Browser DevTools open on the UI tab, pinned to the Network panel.** F12 (or Cmd-Opt-I on Mac) → Network. Reload the UI once so the panel starts capturing. This is the primary tool for showing HTTP traffic during §0 and §1 — the class sees requests appear as you click.
- Backup non-LLM trace ready — paste in `[tool: ...]` lines and `agent>` lines from a prior successful run so you don't lose the room if the network dies mid-session.

**Start the stack (3 terminals, all run from `wazzup/`):**


| #   | Command                                                           | Serves                       | Port |
| --- | ----------------------------------------------------------------- | ---------------------------- | ---- |
| 1   | `AUTH_DISABLED=1 uv run uvicorn wazzup.http.main:app --port 8000` | FastAPI server (the API)     | 8000 |
| 2   | `python -m http.server 8001 -d ui/`                               | Static wazzup UI             | 8001 |
| 3   | `uv run python -m wazzup.client.main`                             | The agent REPL — pick a slug | —    |


Start them in this order. Terminal 1 must be up before 2 and 3 (the UI and the agent both call it). Pick `alice` at terminal 3's prompt.

**Browser tabs to open:**

- `http://localhost:8001` — the wazzup UI (the API's first consumer; demo this in §0 and again in §1 as *"this is what already exists"*).
- `http://localhost:8000/docs` — FastAPI's auto-generated Swagger UI; the full HTTP surface in one scrollable list. Point at it in §2 when defending the catalog's curation: 12 routes total, 7 exposed.

**Sanity check before students walk in:**

- Post a message in the UI; see it land in the daily-standup conversation.
- In terminal 3, ask `what topics exist?`; see one `[tool: ...]` trace and a prose reply.
- Scroll `/docs` and count routes.

If all three respond, the stack is good.

## What to cut if you only have 45 minutes

- Drop §2 (curation) to 5 minutes; accept the premise *"don't expose everything"* and move on.
- Drop the stretch exercise from class; assign as homework.
- Spend the recovered time on **§5 the loop & dispatcher** — that's the part students most often handwave and most often get wrong when they go build their own.

---

The doc is the spine; the demo is the hook; the exercises are the test. Run it that way and the *"agents need standards, not just abstractions"* setup for session 3 (MCP) falls out without you having to argue for it.