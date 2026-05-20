# How to expose your API to an AI agent

A recipe for adding a *third caller* to the small app from lesson 1:  
an LLM-driven agent that does work on a  
user's behalf. 

The example throughout is the same `wazzup` app.

**Worked example.** A terminal client. The user types a request
("post a message from alice in the daily-standup conversation
saying we're shipping today"); an LLM, given the right tools,
picks the sequence of HTTP calls that get it done; the agent
reports back. Stack: lesson 1's running FastAPI app, any LLM
provider, `httpx` for tool invocations, plain Python for the loop
itself — no agent framework needed.

> **Two ways to read this.** Top-to-bottom if you're following the
> recipe yourself. Or — paste this entire file into an AI coding
> tool (Cursor, Claude Code) as the build spec, with one
> instruction: *"build the `exposed_tools` surface and the client
> following this recipe in order; pause after step 3 and step 5 for
> review; ask before guessing."* The doc is written to work both
> ways.

---

## 1. Purpose of this document: identifying the abstractions we need

The thought (and applied) exercise we do here is to think what we need if we are to expose our APIs to agents.

We are assuming we use no standard aside from http / json / rest, so, commonly accepted internet practices and protocols. Part of the motivation is to think which are abstractions we would like a library - or a standard protocol - to provide. 

## 2. A curated tool surface

Lesson 1 left you with two layers: an internal Python API
(`wazzup/api/`) and an HTTP surface that exposes it for humans
and other services (`wazzup/http/`). To add an agent caller,
you don't expose a third copy of the whole API — you expose a
**curated subset**, described in *words* the LLM can read.

The artifact is a markdown file (`wazzup/exposed_tools.md`),
one section per tool. Each section is a *hybrid*: markdown for the  
descriptive parts (the tool name as an H2 header, plus a small prose  
description) and a fenced YAML block for the structured metadata  
(the HTTP endpoint and the input schema). Markdown does what it's  
good at — readable narrative, easy to review in a PR — and YAML  
does what it's good at — typed, parseable, identical to JSON  
Schema for the input block. Each section has four parts:

- A **name** — the H2 header text. The LLM uses this to refer to
the tool.
- A **description** — the prose paragraph below the header. The
LLM treats this as documentation; bad descriptions cause bad
agent behavior, full stop.
- An **input schema** — JSON Schema, written in YAML. The LLM
uses it to construct arguments; the client uses it to validate
them before the call goes out.
- A **target** — the HTTP method + path template in the YAML
block. Tells the client how to invoke the tool when the LLM
picks it.

The reason for markdown is that some unstructured info is helpful to both humans and machines and readability from both helps achieve some sync. 

Some reasons the tool surface is *not* "all my routes":

- **Curation is a safety boundary.** Some routes are fine for an
authenticated human but should never be in the hands of a
hallucinating agent (hard-delete, billing, anything irreversible).
- **The LLM has a finite context budget.** Twenty well-described
tools beat eighty thin ones. The model picks better when the
menu is shorter and each item is unambiguous.
- You may want to expose "groups" of operations that achieve different purposes and are intended to be used separately.

The rest of this recipe is: how to think about *what* to expose,
how to write the descriptors, where to put them, and how to write
the client loop that actually drives the LLM around the tools.

---

## 2.1 What to expose (and what not to)

A simple decision tree to start with:

- **Read operations are usually safe.** `get_user`, `query_messages`,
`list_rels` — the agent looking things up doesn't change the world.
Default to exposing these.
- **Write operations need a deliberate yes.** `create_message`,
`add_rel`, `update_user_bio` — the agent may get this wrong  
sometimes (humans too); decide whether the cost is acceptable. Often the answer  
is "yes, but with a confirmation step in the client" (the agent  
*proposes*, the user approves, the client executes).
- **Destructive operations stay off.** Soft-delete is sometimes
acceptable (it's recoverable). Hard-delete is not. Anything that
emails real people, charges money, or hits another system: not
without a human in the loop, and probably not via an exposed tool
at all.

Rule of thumb: *would I let a confused new contractor with a stale
runbook call this endpoint?* If no, it doesn't go in
`exposed_tools` — at least not without an extra layer (rate limit,
confirmation, separate auth scope).

This is also why we don't auto-derive tools from the OpenAPI schema
by default (option C in section 5). Auto-derivation
optimizes for DRY at the cost of conflating "exposed to humans"
with "exposed to LLMs". Those are different audiences with
different risk profiles.

---

## 3. Communicating tool behavior to the agent

Section 2 was about *which* operations to expose. The next question
is just as important and almost never written down: of the tools we
*do* expose, **how do we tell the agent what kind of tool each one
is?** A read-only lookup, a non-idempotent write, an irreversible
delete, and a "calls a third-party billing API" all sit in the same
list, all look like callable functions to the LLM, and all carry
very different risk profiles.

This is the *provider-side* version of the autonomy-leash question
lesson 1 named in bucket 2 of *"What we haven't built (yet)."* We
chose what to expose; we still need to *signal what behavior to
expect* so the consumer (the LLM, the client app, the human in the
loop) can decide how cautious to be. There are four facets worth
calling out separately:

- **Read-only.** The tool only reads state; calling it does not
change anything. `query_messages`, `get_user`. Safe to retry,
safe to call speculatively, safe to auto-execute even on a tight
leash. This is the strongest "go ahead" signal we can give.
- **Idempotent.** Calling the tool twice with the same arguments
has the same effect as calling it once. `add_user_to_group` if
membership is a set, `open_dm` if it's find-or-create. Matters
because retries are safe — a network blip mid-call doesn't force
the LLM (or the loop) to ask the user *"did this go through?"*
- **Destructive.** The tool removes or overwrites state in a way
that's hard or impossible to undo. Hard-delete, account closure,
message recall. Even when we do expose one, the LLM should reach
for it last and the client should consider mandatory
confirmation.
- **Side effects beyond our world.** The tool causes something to
happen *outside* our service: an email gets sent, a charge gets
posted, an external webhook fires. Different from destructive
(the data inside our app might be perfectly recoverable), and
worth flagging separately because the blast radius is somebody
else's system.

A fifth, orthogonal axis: **does this operation need explicit human
supervision before it runs?** That's a *policy* on top of the four
behavioral facts above. A tool can be non-destructive and
non-idempotent and still warrant a human-in-the-loop confirmation
(e.g., posting on the user's behalf to a public channel). The four
facets help the consumer *decide* about supervision; the explicit
"requires confirmation" flag is the provider's *demand* that
supervision happen, regardless of how the consumer would otherwise
classify the call.

### Ad-hoc solution: extra YAML keys in the catalog

The MCP spec — covered in lesson 3 — standardizes all of this with
named annotations on every tool. Until we adopt MCP, we can do the
same job ad-hoc by extending the YAML block in `exposed_tools.md`
with optional fields. Section 4 introduces the catalog format with
these fields baked in; the shape we'll use:

```yaml
endpoint: GET /conversations/{conversation_id}/messages
read_only: true
idempotent: true
destructive: false
external_side_effects: false
requires_confirmation: false
input:
  type: object
  ...
```

Defaults matter: the *safe* default for `read_only`, `idempotent`,
`destructive`, and `external_side_effects` is the *cautious* one
(treat as not-read-only, not-idempotent, possibly destructive,
possibly side-effecting) so a tool author has to *opt in* to each
"safe" claim. `requires_confirmation` defaults to `false` only
because most tools don't need it; flagging the ones that do is a
deliberate act.

**Where do these defaults actually live? In the client's loader.**
The catalog file itself (`exposed_tools.md`) is silent on what an
omitted flag means; the defaults are documented in this section but
only *enforced* in `wazzup/client/load_tools.py` via the
`bool(meta.get(..., default))` calls. This works fine when the
catalog author and the client author are the same person (the
convention is implicit between them) but it's a real gap for
cross-team use: a different client reading the same catalog could
hardcode different defaults — defaulting `destructive` to `false`,
say — and silently treat tools you consider unsafe as safe. No
warning, no error, just different behavior from the same input.

Three places defaults *could* live, in increasing order of
portability:

| Where defaults live                    | Concretely                                                | Trade-off                                                                  |
| -------------------------------------- | --------------------------------------------------------- | -------------------------------------------------------------------------- |
| **(a) In the client's loader** (what we do) | `load_tools.py`, doc'd in this section               | Implicit; correctness assumes every reader has read this doc.              |
| **(b) In the catalog file itself**     | A `defaults: {...}` YAML preamble at the top of the catalog | Self-describing — every reader of the file learns the defaults from the file. |
| **(c) In a shared protocol spec**      | A standard's reference doc (e.g. MCP's `ToolAnnotations`) | Maximum portability — every compliant client agrees automatically.         |

The point worth keeping in mind: **client-side defaults are
convention, not contract.** Lesson 3 (MCP) standardizes both the
flag *names* and their *defaults* via `ToolAnnotations`, which is
the cross-ecosystem combination of (b) and (c) above.

These flags are **hints, not enforcement** — the loader passes them
through, and it's up to the loop and the client to honor them. A
minimal honor policy in our hand-rolled client (lesson 2's loop):

- Auto-execute `read_only: true` calls without prompting.
- Auto-execute idempotent non-destructive writes, but log them at a
higher level via `deviation()` so they're visible in review.
- For `destructive: true` or `requires_confirmation: true`, *pause
the loop*: print the tool name, the arguments, and the
description back to the user, and require a typed *yes* before
dispatching. Only then feed the result back to the LLM.
- For `external_side_effects: true`, do the same as destructive
unless the operator has explicitly opted into auto-execute for
this tool.

This is exactly the "autonomy slider" pattern lesson 1 referenced
in bucket 3, applied at the tool granularity. We're choosing per
tool, declaratively in the catalog, instead of hand-coding the
policy at every dispatch site.

**One policy choice the loop has to make: per-tool-name or
per-(tool, target)?** The reference implementation in
`wazzup/client/main.py` uses **per-tool-name**: approving
`post_message` once authorizes *every* subsequent
`post_message` call in the same session, regardless of which
conversation or what text. The alternative — re-prompt for each
new `conversation_id` — is safer but feels heavy in a demo where
the agent does several posts in a row. For a teaching artifact
the per-tool-name choice keeps the interaction watchable; a
production policy would re-prompt per target, rate-limit, scope
by recipient, or move to the heavier propose-then-confirm
pattern below. Flag this design choice when you adopt the
pattern in earnest.

### Alternative: flags-as-prose

The structured-flags approach we just described isn't the only option.
Instead of a boolean `requires_confirmation: true`, you could put the
meaning directly in the description text:

> *"This operation is destructive — always ask the user to confirm
> before calling. If the user has already approved a similar call
> earlier in this conversation, you may skip the confirmation."*

The LLM reads the prose, asks the user, and tracks the answer in its
own growing conversation history. No client-side policy code at all —
the LLM *is* the policy engine. The "memory of preferences" lives
inside the LLM's message history, not in a Python set.

Trade-off:

| Approach                        | What it gives you                                                          | What it costs                                                                 |
| ------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **Structured flags** (us)       | Deterministic, enforceable by the client, cheap (no LLM tokens), auditable | Vocabulary lock-in across ecosystems; limited expressiveness (boolean yes/no) |
| **Flags-as-prose** (LLM-driven) | No vocabulary problem (English is universal); expressive                   | Non-deterministic; client can't enforce; token-expensive every turn           |

We picked structured flags because we want **enforcement**: the client
can refuse to call `post_message` even if the LLM forgot to ask the
user — one boolean, one line of policy code, done. Prose-only puts
the policy decision inside the LLM, which is fine when you trust the
model and the prompt, less fine when prompt injection or model
variance enters the picture.

A subtler point that connects to the defaults discussion above: **the
flag names themselves are also our convention.** We chose `read_only`,
`idempotent`, `destructive`, `external_side_effects`,
`requires_confirmation`. A different catalog might call them
`is_dangerous` or `mutating`; our `_should_prompt` wouldn't recognize
those. Both the *names* and the *defaults* need agreement for
cross-ecosystem use — which is exactly what MCP's `ToolAnnotations`
provides.

### The escape hatch: propose-then-confirm pairs

For operations that genuinely warrant a human in the loop and where
a typed-prompt confirmation isn't strong enough, the heavier
pattern is splitting one tool into two: `propose_X` returns a
short-lived token plus a human-readable summary of what would
happen; `confirm_X` requires that token to actually execute. The
LLM cannot bypass the surface — it has to render the summary
somewhere a human will see it before it can pass the token along.

This costs more (two endpoints, a token store, an expiry) and
should be reserved for operations where the cost of the LLM
slipping past a confirmation prompt is genuinely unacceptable.
Most tools don't need it; a few do, and it's worth knowing the
pattern exists.

---

## 3.5 What reaches the LLM — and what doesn't

Before wiring up the loader and the loop, it's worth being explicit
about which parts of the catalog reach the LLM and which stay on the
client side. The split shapes the rest of the design.

**Per tool, only three things go to the LLM:** the `name` (H2 header),
the `description` (the prose paragraph), and the `input` schema (the
YAML block's `input:` field, which becomes the OpenAI `parameters`
field). The behavioral flags (`read_only`, `idempotent`,
`destructive`, `external_side_effects`, `requires_confirmation`) and
the `endpoint` field **never reach the LLM** — they're consumed by
the client. Two audiences for the same catalog entry:

| Field                                       | Sent to LLM? | Consumed by                                                |
| ------------------------------------------- | :----------: | ---------------------------------------------------------- |
| File-level preamble (before first `## name`) | NO          | Humans only (PR reviewers; the loader drops it via `re.split(r"^## ")[1:]`) |
| `name` + `description` + `input` schema     |    YES       | The LLM (becomes `tool.name` / `tool.description` / `tool.parameters` in the OpenAI tools API) |
| `endpoint`                                  |    NO        | The client's HTTP dispatcher (`invoke.py`)                 |
| Behavioral flags                            |    NO        | The client's policy (`_should_prompt` etc. in `main.py`)   |

**Descriptions teach the LLM what to do; flags tell the client what
to allow.** Same file, two readers, two different jobs.

### The user's prompt: a client-owned template

The user's typed input doesn't reach the LLM raw either. The client
renders it through a Jinja template
(`wazzup/client/prompts/user_turn.md.j2`) before constructing the
user message. The template is short today but the seam matters: it's
where the **client retains control** over the LLM-facing prompt.
When you want to add a system constraint, identity hint, format
requirement, or any other framing on every turn, you edit the
template — not the loop, not the dispatch logic.

### Conversation history: in the prompt, not in `messages=[...]`

There are two reasonable places to put cross-turn conversation
history:

1. **In the OpenAI `messages=[...]` parameter** as structured entries
   (`[{"role": "user", ...}, {"role": "assistant", ...}, ...]`). Let
   OpenAI handle threading. Most direct, OpenAI-native shape.
2. **Inside the user prompt** itself, rendered as prose by the template
   from a client-owned `history: list[{"user": ..., "assistant": ...}]`.
   The client owns the format.

This recipe picks (2). Reason: putting history in the prompt gives
the client control over format — summarize, truncate, filter,
reformat — all by editing the template, no Python change. Putting it
in `messages=[...]` hardcodes the OpenAI format and removes that
flexibility.

The split between within-turn and across-turn:

- **Within-turn:** structured `messages` list, recreated fresh each
  user turn. Tool call → tool result threading happens here — the
  OpenAI tools API requires `tool_call_id` matching between assistant
  tool-call messages and tool-result messages, so it can't collapse
  to prose.
- **Across-turn:** prose-rendered history in the template. Client
  owns the format.

The reference implementation in `wazzup/client/main.py` exposes a
`/reset` command to clear `history` mid-session, plus a Jinja
template that today renders each prior turn verbatim and could
trivially be edited to summarize or truncate instead.

---

## 4. The tool catalog

The catalog lives at `wazzup/exposed_tools.md` — one document,
hand-authored, reviewable as prose by anyone, durable across
whatever you build on top of it. The shape we'll use: an `H2`
header per tool (the name), a paragraph of prose (the description),
and a fenced YAML block (the structured metadata, including the
behavioral annotations from section 3). One full entry looks like
this:

```markdown
## query_messages

List recent messages in a conversation. Use this when the user
asks "what did X say" or "show me the last N messages". Returns
up to `limit` messages, newest first. Soft-deleted messages are
excluded.

```yaml
endpoint: GET /conversations/{conversation_id}/messages
read_only: true
idempotent: true
destructive: false
external_side_effects: false
requires_confirmation: false
input:
  type: object
  properties:
    conversation_id: {type: integer}
    limit: {type: integer, default: 20, maximum: 100}
  required: [conversation_id]
  additionalProperties: false
```

```

Each entry has the following parts the runtime extracts:

- **Name** — the H2 header text. The LLM uses this to refer to the
tool. Verbs scoped to the entity work best (`query_messages`,
`create_user`, `add_user_to_group`). Avoid generic names that
could match more than one thing.
- **Description** — the prose paragraph between the header and the
YAML block. This is what the LLM treats as documentation; bad
descriptions cause bad agent behavior, full stop. Treat it like
microcopy: *what does this do, when should the LLM use it, what
does it return, what does it not do?* If a description is one
sentence, it's almost certainly too short. Re-read it from the
LLM's perspective: could *you* pick between this tool and a
similarly-named one with only the description in front of you?
- `**endpoint`** — the HTTP method and path template the client
uses to invoke the tool. Path placeholders (`{conversation_id}`)
get filled from the LLM's arguments at call time.
- **Behavioral annotations** — `read_only`, `idempotent`,
`destructive`, `external_side_effects`, `requires_confirmation`.
Optional booleans that tell the loop and the client *how to
treat this call* (auto-execute, prompt the user, log loudly,
etc.). All default to the cautious value. Section 3 covers the
semantics; the loader reads them as plain dict keys and the
loop's dispatch logic branches on them.
- `**input`** — a JSON Schema describing the arguments. The LLM
uses it to construct calls; the client uses it to validate
before hitting the API. Tight schemas — typed fields, enums,
ranges, `additionalProperties: false` — cut malformed calls
dramatically.

Why YAML inside markdown rather than pure prose or pure JSON: the
prose description is unambiguously human-authored, the YAML is
unambiguously machine-readable, and each does the thing it's good
at. The YAML's `input` block is structurally identical to JSON
Schema (which is what every LLM provider — and MCP, in lesson 3 —
expects on the wire), so the same block flows through unchanged
with no transformation step.

Why a markdown file at all, instead of a Python module of
descriptors: the catalog stops being engineering's exclusive
artifact. A PM, a security reviewer, or a non-Python contributor
can read it, comment on it, propose edits in a PR. Curation
becomes a document review, not a code review.

---

## 5. Where the catalog lives

One file at `wazzup/exposed_tools.md`, listing every exposed
tool top to bottom. That's the whole story. The runtime loads it
via a small parser (~20 lines, section 6) into a list of plain
dicts the loop can hand to any LLM provider.

For a project that grows past ~20 tools, splitting per entity
(`exposed_tools/messages.md`, `exposed_tools/users.md`) is fine —
the loader takes a path or a glob, no logic changes — but resist
the urge to do it early. One file, read top to bottom, *is* the
auditable description of what the agent can do. A directory of
files isn't, and the moment the catalog stops being one document
the document-review property starts to leak.

Two alternatives we explicitly don't take, and why:

- **Decorators on FastAPI routes** (`@expose_to_agent`). Couples
the agent surface to the HTTP surface; descriptions clutter the
route file; the catalog stops being a single artifact a
non-engineer can open. The reason curation belongs in a doc
rather than scattered through code.
- **Auto-derive from OpenAPI.** Zero curation — every endpoint
becomes a tool, including the dangerous ones. Saves 30 minutes,
costs you the first time someone (or an AI scaffolder) exposes a
destructive route by default. The whole point of section 2 is
that this is the wrong default.

The rest of this recipe assumes the loader (section 6) returns a
list of dicts of the shape `{"name", "description", "endpoint", "input_schema"}` — one per `H2` section in the catalog.

---

## 6. The loader and the loop

Two small pieces of runtime: a loader that turns the markdown
catalog into a list of dicts, and an agentic loop that hands those
dicts to the LLM and dispatches whatever it picks.

**The loader**, ~15 lines of stdlib + `pyyaml`:

```python
# in client/load_tools.py
import re, yaml
from pathlib import Path

def load_tools(path: Path) -> list[dict]:
    """Parse exposed_tools.md → list of {name, description, endpoint, input_schema}."""
    sections = re.split(r"^## ", path.read_text(), flags=re.M)[1:]
    tools = []
    for section in sections:
        name, _, rest = section.partition("\n")
        description, _, after = rest.partition("```yaml")
        yaml_block, _, _ = after.partition("```")
        meta = yaml.safe_load(yaml_block)
        tools.append({
            "name": name.strip(),
            "description": description.strip(),
            "endpoint": meta["endpoint"],
            "input_schema": meta["input"],
        })
    return tools
```

The output is plain `dict`s, no class ceremony. That dict shape
flows unchanged through the loop and the dispatcher. If a tool is
malformed (missing the YAML block, or YAML that doesn't parse), the
loader raises at startup, not at agent runtime — that's the right
place to fail, before the LLM sees a broken tool list.

**The loop** is provider-agnostic. Each provider (Anthropic,
OpenAI, etc.) has its own SDK and tool format; we hide that behind
a thin `LLMClient` adapter that takes the dict-shaped tools, sends
them in the provider's expected shape, and returns a normalized
response dict:

```python
# the abstraction the loop talks to
from typing import Protocol

class LLMClient(Protocol):
    def chat(self, messages: list[dict], tools: list[dict]) -> dict: ...
        # response shape:
        # {
        #   "text": str | None,                     # plain reply, or None
        #   "tool_calls": list[dict],               # each: {"id", "name", "args"}
        #   "assistant_msg": dict,                  # raw msg to append to history
        # }
```

The loop itself takes two pieces of *cross-turn* state — the prompt
template (a Jinja template) and the conversation history list — and
recreates the *within-turn* `messages` list fresh on every user
turn:

```python
def run_agent(client: LLMClient, tools: list[dict],
              user_input: str, history: list[dict],
              prompt_template, max_turns: int = 10) -> str:
    """Run one user turn. Mutates `history` (appends the completed
    user+assistant pair). Returns the final assistant text."""

    # 1. Render the user prompt through the template, with prior
    #    history baked in by the template (NOT passed as separate
    #    structured `messages` entries).
    rendered = prompt_template.render(user_input=user_input, history=history)

    # 2. Within-turn messages list: structured shape (the OpenAI
    #    tools API requires tool_call_id pairing between assistant
    #    and tool messages, so this can't collapse to prose).
    messages = [{"role": "user", "content": rendered}]
    final_text = None

    for _ in range(max_turns):
        response = client.chat(messages=messages, tools=tools)
        messages.append(response["assistant_msg"])   # record what the LLM said
        if not response["tool_calls"]:
            final_text = response["text"]            # ← terminating case
            break
        for call in response["tool_calls"]:
            result = invoke(call, tools)             # HTTP call to FastAPI
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": result,
            })
    else:
        final_text = f"(gave up after {max_turns} turns)"

    # 3. Append to cross-turn history — raw user input + final
    #    assistant text only, NOT the structured `messages` trace.
    #    The template controls how this appears in future prompts.
    history.append({"user": user_input, "assistant": final_text})
    return final_text
```

The REPL wrapping it is one `while True:` reading user input, calling
`run_agent` once per input, with `history` persisting across calls
and being cleared by a `/reset` command. See
`wazzup/client/main.py:run_repl` for the full version.

Four things that fall out of this loop:

- **The LLM controls termination.** When it's done with tools and
has an answer, it returns text and the loop ends. You don't tell
it "stop using tools now" — the model decides. The `max_turns`
cap is a safety net, not the primary stop condition; if you hit
it, something is wrong (usually a tool that keeps failing in a
way the LLM keeps misreading).
- **Within-turn `messages` is the trace; across-turn `history` is
the memory.** `messages` is rebuilt fresh each user turn and
captures only that turn's dispatch (assistant → tool → assistant →
tool → final). The cross-turn `history` carries only the
user/assistant final pair per turn, rendered as prose by the
template — see §3.5.
- **Tool results are just messages.** Within one turn, every tool
result becomes a `{"role": "tool", ...}` entry the next LLM call
sees. By the time the inner loop ends, `messages` contains a
complete trace of what the agent did this turn — useful for
logging via the `deviation()` helper from lesson 1 (*LLM picked a
tool not in our list*, *schema validation failed*, *HTTP timeout*,
*max turns exceeded*).
- **Errors are signal, not crashes.** When a tool fails (4xx, 5xx,
validation error), the *result* you feed back is the error
string. The LLM often recovers by trying a different argument or
giving up gracefully. Crashing the client on a tool error is
almost always wrong — it removes the agent's ability to react.

Two adapters of ~50 lines each (one per major provider) cover the
SDK translation without leaking provider-specific shape into the
loop. The loop never imports from `anthropic` or `openai`; only the
adapter does.

---

## 7. Wiring tool calls to HTTP

When the LLM picks a tool, the client has to actually execute it.
For this lesson the execution path is HTTP back to the running
FastAPI server (lesson 1's `http/` package, served on `BASE_URL`).

```python
# in client/invoke.py
import httpx

def invoke(call: dict, tools: list[dict]) -> str:
    tool = next((t for t in tools if t["name"] == call["name"]), None)
    if tool is None:
        return f"error: unknown tool {call['name']!r}"

    method, _, path_template = tool["endpoint"].partition(" ")
    args = call["args"]
    path_args = {k: v for k, v in args.items()
                 if "{" + k + "}" in path_template}
    body_args = {k: v for k, v in args.items() if k not in path_args}
    path = path_template.format(**path_args)

    response = httpx.request(
        method,
        BASE_URL + path,
        params=body_args if method == "GET" else None,
        json=body_args if method != "GET" else None,
        headers={"Authorization": f"Bearer {TOKEN}"},
        timeout=10.0,
    )
    if response.status_code >= 400:
        return f"error {response.status_code}: {response.text}"
    return response.text
```

A few practical points:

- **Auth is the client's responsibility.** The agent runs with a
*user's* token (or a service token with scoped permissions). The
client puts it in the `Authorization` header on every request.
Never embed credentials in tool descriptors or in the LLM's
context — the LLM doesn't need to see the token to use the tools.
(If you've followed lesson 1, this is the same `require_auth`
dependency on the FastAPI side.) This bullet is *operational
shorthand* — the deeper "what kind of token, and on whose
behalf" question is deferred to the **Authentication** item
under *"What we haven't built"* below; lesson 3 §10 spells out
the MCP version in more detail.
- **Errors come back as text, not exceptions.** A 4xx response is
signal the LLM should see and react to: `"error 404: user not found"` is enough for the model to try a different `user_id`. A
5xx response is also returned as text, but the client should
*also* log it loudly via `deviation()` — that's exactly the kind
of unexpected path lesson 1's logging section is built for.
- **Timeouts are non-negotiable.** Without `timeout=`, a slow
endpoint freezes the entire agent. Pick a value (10s is reasonable
for interactive use), surface timeouts as errors the LLM can see,
and log every timeout as a deviation. A pattern of timeouts means
your API is the problem, not the agent.
- **Validate against the schema before sending.** It's tempting to
trust the LLM's argument output, but a quick `jsonschema.validate`
against `descriptor.input_schema` before the HTTP call catches
malformed calls earlier and produces a more useful error message
for the LLM than a 422 from FastAPI.

---

## 8. Putting it together: the example client

A minimal terminal client, ~40 lines, with cross-turn history rendered
through a Jinja template and `/reset` to clear it:

```python
# in client/main.py
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .load_tools import load_tools
from .llm import make_client          # returns whichever LLMClient
from .invoke import invoke

TOOLS = load_tools(Path("wazzup/exposed_tools.md"))

# Client-owned prompt template — see §3.5
_env = Environment(loader=FileSystemLoader("wazzup/client/prompts"),
                   undefined=StrictUndefined, autoescape=False)
_user_turn = _env.get_template("user_turn.md.j2")

def main():
    client = make_client()
    history: list[dict] = []                              # cross-turn memory
    while True:
        user_input = input("you> ").strip()
        if user_input == "/quit": break
        if user_input == "/reset":
            history = []
            print("(history cleared)")
            continue
        if not user_input: continue

        # Render the user turn with history baked in by the template
        rendered = _user_turn.render(user_input=user_input, history=history)
        messages = [{"role": "user", "content": rendered}]   # per-turn only
        final_text = None

        for _ in range(10):                                  # max turns
            response = client.chat(messages=messages, tools=TOOLS)
            messages.append(response["assistant_msg"])
            if not response["tool_calls"]:
                final_text = response["text"]
                print(f"agent> {final_text}")
                break
            for call in response["tool_calls"]:
                print(f"  [tool: {call['name']}({call['args']})]")
                result = invoke(call, TOOLS)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })
        else:
            final_text = "(gave up after 10 turns)"
            print(f"agent> {final_text}")

        history.append({"user": user_input, "assistant": final_text})

if __name__ == "__main__":
    main()
```

The template at `wazzup/client/prompts/user_turn.md.j2` is short —
roughly:

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

Edit the template to summarize, truncate, or filter history without
touching `main.py`. That's the *"client owns the prompt"* point from
§3.5.

A sample interaction:

```
you> show the last 3 messages alice sent in the daily-standup
     conversation
  [tool: get_user({"name": "alice"})]
  [tool: query_messages({"conversation_id": 12, "sender_id": 4, "limit": 3})]
agent> Alice's last three messages in #daily-standup were:
  1. (10:14) "shipping the auth fix today"
  2. (09:55) "review on PR #142 ready"
  3. (09:30) "morning"

you> /quit
```

The two `[tool: ...]` lines correspond to two iterations of the
loop in step 5: LLM emits a tool call, client runs `invoke`, the
tool result goes back into the conversation, the LLM decides what
to do next. Printing the tool calls inline is cheap observability;
it makes the agent's reasoning legible without needing a debugger.

To run: start lesson 1's FastAPI server (`uvicorn wazzup.http.main:app`),
set `BASE_URL=http://localhost:8000` and `TOKEN=...` in the client's
config, then `python -m client.main` in another terminal.

---

## 8b. The reference implementation in `wazzup/`

The recipe above is the teaching shape. The matching reference
implementation lives at:

- **`wazzup/exposed_tools.md`** — the catalog, with the same 7 tools
  the MCP server (lesson 3) curates. One file, top-to-bottom
  auditable.
- **`wazzup/client/`** — the four modules from §6–§8 with a few
  practical additions (the path-placeholder regex, timeout handling,
  duplicate-tool-name detection at load time): `load_tools.py`,
  `invoke.py`, `llm_adapter.py`, `main.py`.
- **`wazzup/client/prompts/user_turn.md.j2`** — the Jinja prompt
  template from §3.5. Renders `user_input` plus prior `history` as
  prose into the user message on every turn. Today it's
  pass-through-with-history; edit it to inject system constraints,
  summarize history, or change the format without touching the loop.

To run it against the dev server:

```bash
# one-time setup: create the schema and seed 7 canonical users + 3 topics
cd wazzup
uv run python -m examples.seed

# terminal 1: start the FastAPI server in dev mode
AUTH_DISABLED=1 uv run uvicorn wazzup.http.main:app --port 8000

# terminal 2: launch the agent client
uv run python -m wazzup.client.main
```

The seed step is idempotent — re-running it is safe. Skip it only
if you already have users in `wazzup.db`. (Without it, `GET /users`
returns `500: no such table: user` and the picker has nothing to show.)

The client reads `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` from
the same `.env` that `wazzup/__init__.py` loads on import (see
`.env.example` for the variable names). Override on the command
line only if you want to point at a different provider for this
run.

The client prompts `Run as: ` at startup — type a seeded user's
slug (`alice`, `trump`, `min-ho`, etc.). From there it's a REPL: type
a request, watch the `[tool: name(args)]` traces, see the agent's
reply. The first time the agent picks `post_message`, the loop
prompts `[CONFIRM] post_message(...)? approve? (yes/no)`; once
approved, subsequent posts in the same session auto-execute (the
per-tool-name policy from §3).

Two things the reference implementation does *differently* from the
recipe code samples above, both honest about the dev posture:

- **Auth header.** The recipe uses `Authorization: Bearer {TOKEN}`
  as a placeholder; the reference uses `X-User-Slug: {slug}` because
  wazzup's `require_auth` dep accepts that header in development
  mode (`AUTH_DISABLED=1`) and 501s in production mode. This is the
  "localhost short-circuit" the *Authentication* item under *"What
  we haven't built"* below calls out — the agent has no real auth.
  Adopt MCP (lesson 3 §10) for the OAuth 2.1 + PKCE flow when going
  beyond the local-dev posture.
- **No client-side schema validation.** §7 floats `jsonschema.validate`
  before sending; the reference skips it and lets FastAPI's existing
  Pydantic body-validation return `422 {...detail...}`. The 422
  body comes back to the LLM as the tool result and the model
  recovers (re-emits with corrected args). One fewer dependency,
  one fewer place schemas can drift between client and server.

The reference and the MCP server (`wazzup/mcp/server.py`) cover the
same 7 tools through different mechanisms — useful as a side-by-side
when reading lesson 3.

---

## 9. Where this leads — toward MCP

You wrote four components by hand in this lesson:

1. A **loader** that turns `exposed_tools.md` into a list of dicts.
2. A **loop** that drives the LLM through tool calls until it answers
   (with a Jinja prompt template and a cross-turn `history` list).
3. A **dispatcher** that turns each tool call into an HTTP request.
4. An **LLM adapter** that translates the catalog dicts into the
   provider's tool format (OpenAI's `{"type": "function", ...}` in our
   case).

The next lesson swaps all four for a single protocol — MCP. Your
*catalog* (the same `exposed_tools.md`) becomes the source the MCP
server registers from; the loader, the loop, the dispatcher, and the
provider-specific adapter all become "what any MCP-aware host (Claude
Code, Cursor, etc.) gives you for free." You don't redesign the
substrate — you publish it through a different door, and any
MCP-aware host brings its own loop and dispatcher.

The mental shift to expect: in *this* lesson the client owns the
tool list (it loads from disk on startup). In the next, the
*server* owns it, and any client that speaks MCP can ask "what
tools do you have?" over the wire and get a live answer. Same
recipe, one more layer of indirection — and that indirection is
what makes the tool surface portable across every MCP-aware agent
that exists, without anyone having to copy your `exposed_tools.md`.

---

## What we haven't built, standardized, or solved (yet)

A concrete inventory in three buckets, so you know what stands
between this recipe and an agent you can actually expose or
consume in production.

**Not built — features missing from the recipe:**

- Real `LLMClient` adapters per provider. The protocol shape is
sketched; the actual Anthropic/OpenAI/etc. integrations are
exercises.
- Conversation persistence across *process restarts*. The
reference impl keeps history in an in-memory `conversation`
list that grows across user turns and is cleared by `/reset`
or process exit; persisting it to disk for a "resume your
last session" feature isn't built.
- Cost / token tracking per session — needed before you can
set budgets or detect runaway loops.
- LLM retry logic with backoff. Provider rate limits, transient
5xxs, network blips — none of these are handled.

**Not standardized — patterns we touched but didn't nail down:**

- The `LLMClient` return shape across providers. The Protocol is
declared in prose; the adapter contract isn't enforced.
- Tool error format the LLM can parse reliably. We return error
strings; a structured `{error_code, message, retryable}` shape
would let the LLM decide what to do without re-reading the
string.
- `BASE_URL` / `TOKEN` config loading. We assume globals; a
single config-loading point would match lesson 1's same gap.
- Per-endpoint result-shape normalization. Different endpoints
return different JSON shapes; the LLM has to figure them out
every time.

**Not yet solved — what's between this recipe and an actual
deployment of (or consumption of) this agent:**

- **Authentication.** §7 says "auth is the client's
responsibility" and stops there. What's *actually* unaddressed:
**(a)** *whose* token the agent uses — the human user's
(impersonation, agent has the human's full permissions) or a
service token narrowed to a specific scope (less power, more
plumbing). Both are reasonable; neither is the obvious default.
**(b)** how to *issue and rotate* the token — embedded in
config? loaded from `.env`? minted via OAuth at agent start?
We assume "it's just there." **(c)** how to *narrow per
session* — when alice asks the agent to look at the
`#engineering` channel, can it also touch `#hr`? Multi-tenant
deployments need scope-narrowing at request time, not just at
token issuance. **(d)** the **localhost short-circuit** — for
this teaching app, if you bind `BASE_URL` to `127.0.0.1` and
trust the local user, no auth at all is defensible (same
reasoning as MCP §10's local-dev posture). The recipe doesn't
even acknowledge this option exists; production deployments
absolutely need to. If you adopt MCP (lesson 3), §10 takes
this from "TODO" to "here is the spec-defined OAuth 2.1 + PKCE
flow"; the manual recipe in lesson 2 would either copy that
shape or punt to a static Bearer until then.
- Provider rate-limit handling end-to-end. Beyond per-call
retry, what happens to the loop when the provider is down?
- Streaming responses to the user while tool calls are in
flight. The recipe is non-streaming.
- Concurrent / parallel tool calls when the LLM picks several
independent tools in one turn.

---

## Suggested order of work

1. Decide which API operations to expose (section 2). Write the
  list down with one-line justifications for each include and
   each exclude. This is the only step you can't outsource.
2. Author `wazzup/exposed_tools.md` with **one** tool — the
  safest read tool, e.g. `query_messages`. Prose description
   plus YAML block. Verify the YAML's `endpoint` resolves to a
   real FastAPI route, and the `input` schema matches the route's
   Pydantic body / query params.
3. Build `client/load_tools.py` (section 6) and verify it parses
  the one-tool catalog into the expected dict shape. Test with
   a malformed YAML block to confirm the loader fails loudly at
   startup.
4. Repeat step 2 for the rest of the curated list. Each new tool
  should round-trip cleanly through the loader before you add
   the next.
5. Build the provider-agnostic `LLMClient` interface and **one**
  adapter (whichever provider you have credentials for). Test
   the adapter against a single tool with a stub `invoke()` that
   returns canned strings, before adding the real dispatcher.
6. Build the agentic loop (section 6) with terminal IO. Make sure
  it terminates on plain-text responses and caps iteration count.
   Also: create the Jinja prompt template at
   `wazzup/client/prompts/user_turn.md.j2` (start with just
   `{{ user_input }}`) and a `history: list[dict]` declared *outside*
   the REPL loop so it persists across user turns. The loop renders
   `user_input` + `history` through the template each turn and
   appends a `{user, assistant}` entry to `history` on completion
   (see §3.5 for the why).
7. Wire `invoke()` to httpx (section 7). Test end-to-end with a
  read-only tool first; only then unlock the write-side tools.
8. Add logging through the loop using the same `deviation()`
  helper from lesson 1. Every unexpected branch — LLM picks a
   non-existent tool, schema validation fails, HTTP timeout, max
   turns exceeded — is a deviation. Run with `STRICT_MODE=1` in
   tests; unset in production.

**If an AI is building this for you**, the natural review pauses
are after step 3 (eyeball the catalog and confirm the loader's
output dict matches what the loop expects) and after step 6 (drive
the loop manually with a stub `LLMClient` returning canned tool
calls, before plugging in a real provider). Those are the layers
that everything else depends on.

---

## Where this leads next

Lesson 3 (MCP) takes the same curated tool surface and standardizes
the client/server contract so multiple agents and clients can use it
without duplication. The recipe doesn't change — same 7 tools, same
descriptions, same `input` schemas. What changes is *who owns the
loop*: instead of you hand-rolling the loader / loop / dispatcher /
adapter, an MCP-aware host (Claude Code, Cursor, or any conforming
agent runtime) brings its own and asks your server *"what tools do
you have?"* over the wire. Compare `wazzup/mcp/server.py` to
`wazzup/client/` side by side to see the same tool surface published
through a different door.