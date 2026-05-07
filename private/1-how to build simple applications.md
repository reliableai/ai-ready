# How to build simple applications

A recipe for building a small app end-to-end. The chat-for-AI-agents
example below is just an *illustration* — the recipe is the point.

> **Worked example.** Four entities: `user` (a unified agent —
> human or AI), `conversation`, `message`, `topic`. `persona` is
> a markdown field on `user`, not a separate entity. Stack:
> SQLite + raw SQL, Pydantic, FastAPI, pytest, stdlib logging.

> **Two ways to read this.** Top-to-bottom if you're following the
> recipe yourself. Or — paste this entire file into an AI coding tool
> (Cursor, Claude Code) as the build spec, with one instruction:
> *"scaffold the project following this recipe, in the order at the
> bottom; pause after step 2 and step 5 for me to review; ask before
> guessing."* The doc is written to work both ways. Sections that read
> as advice to a student also read as instructions to the tool.

---

## What you will build

**wazzup** is a small chat app with one twist: *humans and AI
agents are the same kind of user*. They share a table, a slug,
an auth surface, and a conversation history. The only thing
that distinguishes them is a `type` field (`'human'` or
`'agent'`) and a `persona` markdown field that gives the AI
ones a voice.

By the end of this recipe you'll have:

- **A FastAPI backend** with CRUD over four entities (`user`,
`conversation`, `message`, `topic`), a single relationships
table for everything else, soft-delete with cascade, slug-
based URLs, structured logging, a dev-mode auth bypass, and
CI-grade tooling.
- **A simple browser UI** (plain HTML + JS + CSS, no
framework) — login, conversation list, message view, message
composer. Served separately from the API so the *consumer of
the API* role is visible.
- **A handful of seeded AI users** with famous-person personas
(Donald Trump, Marie Curie, Yoda — pick any voices you find
fun) that can be addressed alongside human users.
- **An `LLM` helper** that can call OpenAI / Azure /
OpenRouter from a single config — the building block AI
users use to compose their replies.

What you *won't* have at the end of lesson 1: real auth (an
`AUTH_DISABLED=1` flag bypasses it), an  
agent tool-loop (lessons 2–3), production observability  
(lesson 4), or a deployment story. The recipe is deliberately  
minimal — runnable, demoable, hardenable later.

A typical run-through, top to bottom: a human Alice logs in
via the UI, opens the *#daily-standup* topic, posts *"shipping
the auth fix today"*, and sees the agent **Trump** reply
*"TREMENDOUS. The greatest auth fix. Everyone's saying it."* —
all backed by the same `messages.create()` call, just one with
a human user_id and one with an agent's. *That's* the shape
this lesson teaches.

---

## 1. Start with a conceptual model

Sketch the entities and the relationships between them on paper before  
you touch code. Don't agonize — you will iterate. You're aiming for  
"plausible v0.1", not "final schema".

For the example app:

- `user` — anyone who talks: humans and AI agents both live
here. Carries a `type` field on the user table (`'human'` or
`'agent'` — same table, same auth, same persona, same
conversations; the only thing that differs is who's typing)
and a `persona` field (markdown) describing voice, role, or
behavior — see section 2 for why persona is a column on
`user`, not a separate entity.
- `topic` — a public chat room (channel, team, audience). The
user-facing surface, alongside users themselves: posts on a
topic are how groups talk. v0.1 topics are public — anyone
reads, anyone writes — but the model leaves room for private
or group-restricted topics later (see *member_of* below).
- `conversation` — internal plumbing for messages. **Not user-
facing.** Two valid shapes:
  - the **default conversation** for a topic (auto-created
    when the topic is created), which holds posts to that
    topic; and
  - a **DM** between exactly two users (no topic, two
    `participates_in` rels).
  The UI never shows the word "conversation" — users only see
  *people* (DMs) and *topics* (rooms). Conversations exist so
  messages have one stable place to live regardless of which
  surface they came from.
- `message` — a single utterance in a conversation.

Relationships you'd expect: conversation *in_topic* topic
(written by `topics.create()`, exactly one per topic), user
*participates_in* conversation, message *belongs_to*
conversation, message *sent_by* user. Plus user *member_of*
topic — *defined and reserved for future private topics*; not
written or checked by v0.1.

A note on shape evolution: an earlier draft of this lesson
taught a Slack-style hierarchy of *topics → conversations →
messages*, with users joining topics and threading
conversations under them. That extra level turned out to be
machinery the user never sees. The shape above keeps the
*conversation* row (it's still the home for messages) but
demotes it from user-facing concept to plumbing. Two surfaces
— users and topics — is the smallest model that supports
both DMs and group chat without inventing more entities. The
*member_of* rel survives unchanged because group/private
topics will need it; the lesson just doesn't exercise it yet.

**One half is private; one half is public.** Topics are
explicitly public in v0.1 — anyone authenticated can read or
post on any topic. DMs are the opposite: a 1:1 conversation
between exactly two users, and *only* those two should ever
see its messages. The model needs a single rule that handles
both shapes: a user may access a conversation iff it's a
topic-default they're allowed to see (gated by a future-
private hook), OR it's a DM they're a participant of. We
encode that as `conversations.is_accessible_by(db, *,
conversation_id, user_id)` and call it from every read or
write route. The api layer answers the structural question
("is this user a participant?"); the http layer ties it to
the authenticated caller. See section 8 for the routing
mechanics.

---

## 2. One shape for every entity table

Every named entity has the same default shape:


| Column         | Purpose                                                                                                                            |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `id`           | Primary key — internal, integer, auto-increment                                                                                    |
| `name`         | Human-readable display name (`"Alice Smith"`); **not unique**                                                                      |
| `slug`         | URL-friendly handle (`alice-smith`, `daily-standup`); **unique among live rows** (partial unique index `WHERE deleted_at IS NULL`) |
| `created_at`   | Insert timestamp                                                                                                                   |
| `updated_at`   | Last-write timestamp                                                                                                               |
| `deleted_at`   | NULL = alive; non-NULL = soft-deleted                                                                                              |
| *indexed cols* | extra attributes you query by (e.g., `type`)                                                                                       |
| `details`      | JSON blob for everything else                                                                                                      |


**Why this shape?**

- Uniformity makes a generic API layer trivial — one helper handles
every entity.
- `**id` vs. `slug` is internal vs. public.** `id` is the
primary key and FK target everywhere internally — stable, tiny,
opaque. `slug` is what URLs, logs, and agent prompts see —
human-readable, stable across migrations and fixtures
(`/users/alice` not `/users/42`). Carrying both means you don't
have to choose between internal stability and external
readability.
- **Uniqueness lives in the schema, scoped to live rows.** Each
named entity carries a *partial* unique index on `slug`, scoped
to `WHERE deleted_at IS NULL` — that's what makes "no two live
rows share a handle" a real guarantee while letting soft-deleted
slugs be reusable when the user creates a fresh entity with the
same name. The application's `make_slug` helper does the
friendly suffix-on-collision (section 6); the partial unique
index is the race-safety net the application alone can't
provide. `name` carries no uniqueness constraint: two users
named "Alice" coexist, distinguished by their slug. Display
names are for humans; slugs are for code.
- The JSON column lets you evolve the model without migrations. New
optional field? Drop it in `details`. Promote to an indexed column
only when you actually query by it.
- Soft delete via `deleted_at` keeps an audit trail and makes "undo"
cheap.
- **Timestamps are UTC, ISO-8601, server-set.** SQLite has no native
datetime type, so `created_at` / `updated_at` / `deleted_at` are
stored as ISO-8601 strings (`"2026-05-06T14:23:45Z"`) in UTC.
*Always UTC, never local.* They're set in the API layer at create
/ update / soft-delete time — `datetime.now(UTC).isoformat()` —
and never trusted from the client. 

**The shape isn't strict.** Some entities don't have a natural
human name and don't need a slug — `message` is the obvious case
(text content, no title; transient, addressed by id when at
all). For those, drop the `name` and `slug` columns. The shape
is the default for *named* entities, not a hard rule.

**Exceptional dedicated columns.** Most extra fields go in
`details` (JSON) until you have a reason to promote them. A
*third* category exists, though: known, named, often-large text
fields that you always read but never query by content. The
canonical example is `user.persona` — a markdown blob describing
a user's voice/role, loaded into the agent's prompt every time
the user speaks. It's not "indexed" (we don't search by persona
content), it's not in `details` (it's a known field with known
shape and known users of it), so it gets its own dedicated
column. Reach for this category sparingly; *most* fields belong
in `details`.

---

## 3. One rels table for everything

A single relationships table holds *all* links between entities:


| Column                     | Purpose                                       |
| -------------------------- | --------------------------------------------- |
| `id`                       | Primary key                                   |
| `src_id`                   | Source entity ID                              |
| `src_type`                 | Source table name (`user`, `conversation`, …) |
| `tgt_id`                   | Target entity ID                              |
| `tgt_type`                 | Target table name                             |
| `rel_type`                 | `in_topic`, `participates_in`, `belongs_to`, `sent_by`, … (`member_of` is reserved for future private topics; not written by v0.1) |
| `details`                  | JSON (e.g., role, joined_at metadata)         |
| `created_at`, `deleted_at` | same soft-delete semantics                    |


**Why one rels table? (initially)**

- One mental model for every link.
- New relationship types cost zero schema changes — just a new
`rel_type` string.
- Cost: every traversal is a join, and you can't enforce FK integrity
at the DB level (the `(src_type, src_id)` polymorphism breaks that).
You *can*, however, constrain `src_type` and `tgt_type` to a known
list of entity names via `CHECK` — that's the cheap defense against
typos like `'mesage'` or `'usr'` that would otherwise be silent
data corruption (the api/ layer has no way to tell `'mesage'` from
`'message'` without scanning the schema). It doesn't restore FK
integrity, but it bounds the damage.
Acceptable for small apps and teaching; production hot paths often
promote frequent rels to dedicated indexed columns.

For this teaching example we keep the design pure: **every link lives
in `rels*`*, including `message → conversation`. We pay the join cost
in exchange for one rule to remember.

Later on as we mature, we will promote some relationships as own table.

---

## 4. Pick a deletion strategy *before* you write code

Three choices to make explicit:

1. **Soft is default.** All `DELETE` calls set `deleted_at`. Reads
  filter it out. This is non-negotiable for the teaching version.
2. **Hard delete is admin-only.** A separate endpoint, gated, off the
  normal API path. 
3. **Cascade rule.** When you soft-delete an entity, you soft-delete
  the rels touching it. Implement this in **one place** (a `delete()`
   helper) — never scatter cascade logic across routes.

For each entity, write down the cascade you want. Examples:

- Delete a `conversation` → cascade to its `message`s and to all rels
pointing at it or them.
- Delete a `topic` → cascade to its default conversation (the one
linked via `in_topic`), which then recursively cascades to its
messages and their rels per the conversation rule. Without this
extra step, the conversation would survive the topic and become a
ghost — a user-facing topic the user can't reach but whose
messages and rels still occupy storage.
- Delete a `user` → product decision: do you nuke their messages, keep
them and anonymize the author, or refuse with 409? Pick one. Write
it down. The hardest deletion bug is the one nobody documented.

**The shape that holds up.** A single `cascade_delete(table, id, hard)`
function in `api/deletion.py` is the only place that knows about
cascade rules. Every entity's public `delete()` is a 4-line
funnel:

```python
def delete(db: Connection, id: int, hard: bool = False) -> None:
    from wazzup.api.deletion import cascade_delete   # late import: cycle
    report = cascade_delete(db, table="user", id=id, hard=hard)
    if report.primary == 0:
        raise NotFound(f"user id={id} not found")
```

Three things this gets right. **`cascade_delete` returns a small
report** (`primary`, `rels`, `messages` — extend as needed) so
callers can verify what actually happened, and tests can assert on
it. **Hard/soft is uniform** — the `hard` flag propagates to
every dependent; mixed modes are confusing and easy to get wrong.
**Cascade is idempotent** — a second call on an already-deleted
entity returns `primary=0` rather than raising; the public
`delete()` wrapper translates that to `NotFound`. Two contracts,
one machine: the wrapper preserves the friendly raise-on-missing
behavior, the helper stays composable for tests and admin tools
that want the report.

Each entity's `_delete_primary(db, id, hard) -> bool` does the
single-row write and returns whether it affected a row. Cascade
calls it last (after sweeping rels and recursing into nested
entities). The split means cascade can keep its own contract
clean while the wrapper enforces the route-friendly one.

---

## 5. Folder structure

Before we build any layer, here's the target tree the recipe
produces. Everything from section 6 onward references files in
this layout — keep this open while you read the rest.

```
wazzup/
├── wazzup/
│   ├── __init__.py
│   ├── db.py                  # connection, schema, migrations
│   ├── models.py              # Pydantic XCreate / XRead / XUpdate
│   ├── api/                   # internal Python API — only layer that touches SQL
│   │   ├── __init__.py
│   │   ├── users.py
│   │   ├── conversations.py
│   │   ├── messages.py
│   │   ├── topics.py
│   │   ├── rels.py            # the single rels-table API
│   │   ├── deletion.py        # cascade rules — one file, one source of truth
│   │   └── slugs.py           # slugify + uniqueness for `name` → `slug`
│   ├── logging_setup.py
│   ├── llm.py                 # thin LLM wrapper (openai/azure/openrouter) — section 14
│   └── http/                  # HTTP exposure — FastAPI routers, thin layer over api/
│       ├── __init__.py
│       ├── main.py            # FastAPI app, middleware, request-id
│       ├── dependencies.py    # get_db, require_auth, current_user, request_id
│       ├── users.py           # routers — one per entity
│       ├── conversations.py
│       ├── messages.py
│       ├── topics.py
│       └── rels.py
├── ui/                        # browser UI — separate from the backend (section 13)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── tests/
│   ├── tests.md               # behavior spec — written before code
│   ├── conftest.py            # in-memory SQLite + TestClient fixtures
│   ├── test_users.py
│   ├── test_conversations.py
│   ├── test_messages.py
│   ├── test_topics.py
│   ├── test_rels.py
│   └── test_e2e.py            # happy-path end-to-end
├── examples/
│   ├── add_user.py            # uses the internal Python API directly
│   ├── remove_user.py         # shows soft-delete + cascade
│   └── seed.py                # populates a few canonical AI users — section 10
├── docs/
│   ├── MODEL.md               # entity model + invariants (spec form) — section 15
│   └── DEMO.md                # demo data + walkthrough spec — section 10
├── .env.example               # template — copy to .env and fill in (section 14)
├── .gitignore                 # see section 14
├── CLAUDE.md                  # project memory for AI coding tools — section 15
├── README.md                  # quickstart for humans — section 15
└── pyproject.toml
```

*This tree is the target, not a suggestion. If an AI is scaffolding
the project, ask it to produce exactly this layout — same names, same
nesting — so the rest of the recipe lines up.*

---

## 6. Build a small internal Python API, and make it CRUD

Same five operations on every entity:

```python
users.create(db, data)                    # → UserRead
users.get(db, id)                         # → UserRead | None
users.update(db, id, patch)               # → UserRead
users.delete(db, id, hard=False)
users.query(db, filters, limit, offset)   # the "+Q"
```

Plus rels:

```python
rels.add(db, src, tgt, rel_type, details=None)
rels.remove(db, rel_id, hard=False)
rels.list(db, src=None, tgt=None, rel_type=None)
```

This is the **only** layer that talks to the DB. Everything else  
(FastAPI, scripts, tests) calls these functions. If you ever find  
SQL outside this layer, fix it. 

If Claude tries to access DB directly - it can only do that to test, never to do stuff.

**Why does every function take `db` as the first argument instead
of opening its own connection?** Because the *caller* knows what
unit of work this call belongs to, and the API layer doesn't. A
single HTTP request usually makes several API calls — create user
→ add rel → write message — that must share one transaction; if
each opened its own connection, you couldn't commit or roll them
back together. So whoever owns the unit of work owns the connection:
for an HTTP request, that's the FastAPI dependency in section 8;
for a test, the fixture; for a script, `main()`. Same API
signatures, three callers — that's what makes this layer reusable.

*Why raw SQL and not SQLAlchemy?* So you can see exactly what SQL
runs and where. Once that's clear, SQLAlchemy Core is a fine next
step that keeps the same mental model — you're still writing
queries, just with a portable layer over dialect differences and
connection pooling. The ORM is a separate decision; this recipe
stays out of that debate.

**Lookup by `id` *and* by `slug`.** Section 2 made `slug` part of
every named entity. Reflect that in the API surface — every
named entity gets a sibling lookup:

```python
users.get(db, id)              # → UserRead | None
users.get_by_slug(db, slug)    # → UserRead | None
```

`id` is what internal callers use (FK joins, references from
other tables). `slug` is what HTTP routes and agent prompts use
— URLs read `/users/alice` instead of `/users/42`, and an LLM
asked *"look up the daily-standup conversation"* can construct
the call without an extra translation step.

**Who creates the slug, and how?** The API layer, at create-time.
`UserCreate` makes `slug` *optional* — if the client provides
one, we use it (after validating uniqueness); if not, we derive
it from `name`. A small helper in `api/slugs.py` handles both:

```python
# in api/slugs.py
import re
from sqlite3 import Connection

def slugify(name: str) -> str:
    """'Alice Smith' → 'alice-smith'. Lowercase, hyphens,
    alphanumerics only. Falls back to 'item' for empty input."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "item"

def make_slug(db: Connection, table: str, name: str,
              override: str | None = None) -> str:
    """Pick a unique slug for the given table. Override wins if
    provided. On collision, append -2, -3, ... until unique."""
    base = slugify(override) if override else slugify(name)
    candidate, n = base, 1
    while db.execute(
        f"SELECT 1 FROM {table} WHERE slug = ? AND deleted_at IS NULL",
        (candidate,),
    ).fetchone():
        n += 1
        candidate = f"{base}-{n}"
    return candidate
```

Each entity's `create()` calls it once, before insert:

```python
def create(db: Connection, data: UserCreate) -> UserRead:
    slug = make_slug(db, "user", data.name, override=data.slug)
    # ... insert row with id, name, slug, ...
```

Treat slugs as **immutable once written** — or build a redirect
path for renames. `id` carries on as the immortal primary key
regardless.

Two practical notes:

- **Race safety.** The check-then-insert in `make_slug` can
race when two creates land at the same time and both see
`alice-smith` as free. The schema's `UNIQUE` constraint on
`slug` (section 2) is the safety net — the second insert
raises `IntegrityError`, and `create()` catches it,
increments the suffix, retries. The application check is for
*friendly UX* (the second user gets `alice-smith-2` instead
of a 409); the DB constraint is what makes uniqueness a real
guarantee.
- **Override scope.** Letting the client pick a slug matters
most for `user` (people want their handle) and named
containers like `conversation` and `topic` (channel names).
For purely auto-generated entities, drop the override field and
just derive from `name`.

*Does FastAPI take care of URL structure?* It provides the
machinery — path parameters, type coercion, optional regex
validation, and OpenAPI docs — but doesn't invent URLs or
generate slugs. You write `@router.get("/users/{slug}")` in
section 8; the slug came from this layer.

**Error conventions across the API.** A consistent error shape
across entities is what makes the HTTP layer (section 8) a
thin translator instead of a per-route case analysis:


| API call                                | Not found         | Conflict                             | Invalid input              | HTTP layer maps to                |
| --------------------------------------- | ----------------- | ------------------------------------ | -------------------------- | --------------------------------- |
| `get(db, id)` / `get_by_slug(db, slug)` | returns `None`    | n/a                                  | n/a                        | route returns 404 if `None`       |
| `query(db, ...)`                        | returns `[]`      | n/a                                  | n/a                        | route returns 200 with empty list |
| `create(db, data)`                      | n/a               | raises `IntegrityError` (slug or FK) | (Pydantic catches earlier) | 409                               |
| `update(db, id, patch)`                 | raises `NotFound` | raises `IntegrityError`              | (Pydantic catches earlier) | 404 / 409                         |
| `delete(db, id)`                        | raises `NotFound` | n/a                                  | n/a                        | 404                               |


`NotFound` is a tiny custom exception (`class NotFound(Exception)`)
declared once in `api/__init__.py` and raised by `update` and
`delete` when the row isn't there. The FastAPI layer catches it
in one place — a `@app.exception_handler(NotFound)` decorator
— and translates to `HTTPException(404)`. `IntegrityError`
(SQLite's built-in) is caught the same way for slug collisions
and FK violations, translated to 409. Pydantic `ValidationError`
on the request body is handled automatically by FastAPI as 422
— that one's free.

The convention matters because it lets every route look the
same: *call the API, return what it returned, let exceptions
flow up to the registered handlers.* Routes that don't follow
this shape are the routes that drift toward business logic in
the wrong layer.

---

## 7. Pydantic models — why bother?

Two concrete payoffs:

1. **Validation at the boundary.** Pydantic rejects bad input at the
  HTTP edge with a useful 422. By the time data reaches your DB
   layer, types are guaranteed — your API code stops checking
   `isinstance(...)` everywhere.
2. **Serialization for free.** `model.model_dump_json()` writes the
  `details` column; `Model(**row["details"])` parses it back. No
   hand-rolled `json.dumps` / `json.loads`.

For each entity, define a triple:

- `UserCreate` — input shape (no `id`, no timestamps).
- `UserRead`   — output shape (has `id`, `created_at`, etc.).
- `UserUpdate` — patch shape (every field optional).

What this looks like for `user`:

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class UserDetails(BaseModel):              # lives in the JSON `details` column
    bio: str | None = None
    timezone: str = "UTC"

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    slug: str | None = None                # optional; server derives if absent
    type: Literal["human", "agent"]        # indexed column
    persona: str | None = None             # markdown; dedicated TEXT column
    details: UserDetails = Field(default_factory=UserDetails)

class UserRead(UserCreate):                # adds the DB-only fields
    id: int
    slug: str                              # populated by server
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

class UserUpdate(BaseModel):               # every field optional → safe PATCH
    name: str | None = Field(default=None, min_length=1, max_length=80)
    type: Literal["human", "agent"] | None = None
    persona: str | None = None
    details: UserDetails | None = None
```

`UserCreate` is what FastAPI validates from a `POST /users` body —
it rejects with 422 if `name` is empty or `type` is `"robot"`, before
your route ever runs. `UserRead` is what the API layer returns and
what the route serializes back to JSON; the `details` blob is parsed
into a typed `UserDetails` on the way in and dumped back to JSON on
the way out. `UserUpdate`'s all-optional shape is what makes PATCH
safe: only the fields the client actually sent get touched.

Read ≠ Create. Don't be tempted to share one model — you'll either
leak DB-only fields or accept fields you shouldn't.

---

## 8. FastAPI — why, and how to keep it lean

**Why FastAPI:**

- Routes pull request/response types from Pydantic models →
automatic validation and a free OpenAPI doc.
- **Dependency injection** for DB connections, auth, request IDs — see below.
- `TestClient` runs the whole app in-process, synchronously, in tests.

**Dependency injection: how routes declare what they need.**

DI is how a route declares what it needs — DB connection,
authenticated caller, log context — instead of fetching it
itself. The idiom that's easiest, most consistent, and
hardest-to-misuse is to **set authentication on the router, not
on each route**:

```python
# in http/users.py — authenticated router
from fastapi import APIRouter, Depends
from .dependencies import require_auth, get_db, current_user

router = APIRouter(
    prefix="/users",
    dependencies=[Depends(require_auth)],   # every route below is gated
)

@router.post("")
def create_user(
    body: UserCreate,
    db: Connection = Depends(get_db),
) -> UserRead: ...
```

A subtler case: when the *wire contract* and the *api contract*
disagree, the route defines its own request shape. The canonical
example is `POST /messages`. The api function `messages.create`
takes a `MessageCreate` with `sender_id` (so api-level tests can
write any sender they want), but on the wire the client must
*not* supply `sender_id` — the route fills it from
`current_user`. If the route consumed `MessageCreate` directly,
FastAPI would 422 a request that omitted `sender_id`, even
though the server is about to overwrite it. So:

```python
# in http/messages.py — route-local request shape

class MessageCreateRequest(BaseModel):
    """HTTP body for POST /messages. ``sender_id`` is intentionally
    absent — the route fills it from ``current_user``."""
    conversation_id: int
    text: str = Field(min_length=1)
    details: MessageDetails = Field(default_factory=MessageDetails)


@router.post("", status_code=201, response_model=MessageRead)
def create_message(
    body: MessageCreateRequest,
    db: Connection = Depends(get_db),
    me: UserRead = Depends(current_user),
) -> MessageRead:
    data = MessageCreate(
        conversation_id=body.conversation_id, sender_id=me.id,
        text=body.text, details=body.details,
    )
    return messages_api.create(db, data)
```

The route-local class lives in `http/messages.py` (HTTP-layer
concern, not api). This is the symmetric pattern to
`MessageRead` being stored-columns-only — both say *"when the
HTTP shape and the api shape diverge, the route is where the
divergence lives"*. Routes are still thin translators; they're
just translating between two clearly-named shapes instead of one.

And the public counterpart, for routes that *can't* require auth
(login is the obvious one — you can't authenticate to log in):

```python
# in http/auth.py — public router
from fastapi import APIRouter, Depends
from .dependencies import get_db

router = APIRouter(prefix="/auth")   # no dependencies= → public by design

@router.post("/login")
def login(
    body: LoginRequest,
    db: Connection = Depends(get_db),
) -> Token: ...
```

Two files, one difference: the *presence* of
`dependencies=[Depends(require_auth)]` on the `APIRouter` line.
Every endpoint registered on the protected router runs
`require_auth` before its body — you literally cannot add an
unauthenticated route to `messages.py`, because the gate isn't on
the endpoint at all. The public router deliberately has no
`dependencies=` argument; that absence *is* the opt-out, and it
lives in exactly one small file (`http/auth.py`) that's easy to
eyeball.

Auditing auth coverage means scanning the half-dozen
`APIRouter(...)` calls in `http/`, not every `@router.post(...)`
line in the codebase. New endpoint file? Copy the protected
router declaration and you're authenticated by default. The route
author can't forget.

**Two other `Depends` patterns worth knowing.**

`db: Connection = Depends(get_db)` — *resource as parameter*.
`get_db` is a generator that yields a fresh SQLite connection per
request and closes it after the route returns; commit / rollback /
close live in the code *after* the `yield`. We're not pooling on
purpose — SQLite is in-process, opening a connection is
microseconds, pooling solves a cost that doesn't exist here. The
same DI shape works with Postgres: `get_db` would check one out
of a `psycopg_pool.ConnectionPool` (or `asyncpg.Pool` for async),
and the route signature above doesn't change.

`user: UserRead = Depends(current_user)` — *lookup*, added per
route when the body actually needs the authenticated user as an
object (say, to set `sender_id` on a message). It rides on top of
the router-level gate: `require_auth` already answered "is the
caller allowed in?"; `current_user` just answers "who are they?".
Two distinct questions, two distinct dependencies.

`Depends(...)` itself is a *marker*, not a call. You pass the
function reference (`Depends(get_db)`, not `Depends(get_db())`),
and FastAPI calls it for you once per request, before the route
body runs. Shared deps are cached within a single request — so
the route and `current_user` see the *same* `Connection`, and
multiple API calls in one request share one transaction by
default.

**So why use `Depends` at all?** Two reasons.

First, the route's contract is *visible* and the default is
secure. The router declares `dependencies=[Depends(require_auth)]`
once; every endpoint underneath inherits the gate. To make a
route public you have to put it on a different router — opt-out
is a file move, not a forgotten line. Mistakes scale with how
many *routers* you have, not how many *routes*.

Second, every cross-cutting concern lives in exactly one
function: connection lifecycle in `get_db`, token check in
`require_auth`, user lookup in `current_user`, log correlation
in `request_id`. Without `Depends`, every route would have to
open/commit/close its own connection, parse its own token, and
stamp its own request-id. Change the rule once, every route
picks it up.

Two more payoffs fall out of the same machinery. **No defensive
checks in handlers:** `require_auth` raises 401 before any route
on a protected router runs, so handlers never have to ask "is
this user logged in?". **Tests substitute dependencies in one
line:** `app.dependency_overrides[get_db] = fake_db` swaps the
function FastAPI calls without touching any route. That's how
section 9 gives every test a fresh in-memory SQLite, and how an
integration test can pretend to be any user it wants.

**Dev-mode auth bypass.** Until you implement real token
issuance (see *"What we haven't built"*), set `AUTH_DISABLED=1`
in your environment. With this flag, `require_auth` skips the
token check entirely; `current_user` reads an `X-User-Slug`
header from the request and looks the user up. The caller
*declares* who they are, no token required. Trivially insecure
— fine for dev, tests, and demos; never enable in production.
Same shape as section 11's `STRICT_MODE`: one env var, two
behaviors:

```python
# in http/dependencies.py
import os
AUTH_DISABLED = os.environ.get("AUTH_DISABLED", "0") == "1"

def require_auth(authorization: str | None = Header(None),
                 x_user_slug: str | None = Header(None)) -> None:
    if AUTH_DISABLED:
        if not x_user_slug:
            raise HTTPException(401, "X-User-Slug header required in dev mode")
        return                              # pass through; user resolved by current_user
    # ... real token check below
```

`current_user` follows the same split: in bypass mode, look up
the user by the header's slug; in production mode, decode the
token. One flag, one source of truth, easy to flip. When you
add real auth later, you don't change any route — only the
bodies of `require_auth` and `current_user`.

**Sync handlers, and when async would pay off.** Every route
example in this section uses `def`, not `async def`. That's a
deliberate choice, not a default — and it's worth understanding
when you'd flip it.

`async def` is only a win if everything inside the handler is also
async-aware (uses `await`). The moment you put a *blocking* call
inside an `async def`, you've blocked the event loop — every other
in-flight request waits behind you. That's strictly worse than
writing `def` in the first place, where FastAPI's threadpool
absorbs the blocking and the loop stays free.

`sqlite3` is sync. There's no `await db.execute(...)`. So `def` is
correct for every route in this recipe — the threadpool model
gives you concurrency (≈40 worker threads by default), and the
code reads top-to-bottom without `await` punctuation.

**Can you migrate later?** Yes, incrementally — but the unit is
the call site, not the route. You can't half-async one function:
once it's `async def`, every blocking call inside has to be either
`await`-able or wrapped in `run_in_threadpool`. The meaningful
migrations:

- **External network I/O (LLMs, third-party APIs).** This is where
  async pays off most, and you can adopt it without touching the DB
  layer. Make `llm.call_async` using `httpx.AsyncClient`. Convert
  routes that fan out N parallel calls to `async def`; the DB calls
  inside can stay sync via `run_in_threadpool` (DB hits are
  microseconds, the wrap cost is invisible).
- **The database — only when you migrate off SQLite.** Async
  wrappers over `sqlite3` (like `aiosqlite`) buy nothing; they run
  the same blocking calls in their own internal threadpool, which
  is what FastAPI does for you already. The migration that *matters*
  is to a real async driver (`asyncpg` for Postgres). At that point
  `get_db` becomes `async def`, the `api/` layer becomes async, and
  routes follow.

Mixed-mode apps are fine indefinitely. FastAPI runs `def` and
`async def` handlers side by side; the router doesn't care. Convert
only the routes that benefit. The `api/` layer's *contract* — the
function signatures, the error conventions table above, the rule
that `api/` is the only layer touching the DB — survives unchanged
through a sync-to-async migration. It's a syntactic refactor, not a
redesign.

For wazzup, sync is correct. Don't pre-design for async; you'd
just have to back it out.

**The lean rule:** a route does three things and no more.

1. Accept validated input (Pydantic already did the work).
2. Call the internal Python API.
3. Return the result.

No business logic in routes. If a handler grows past ~10 lines, the
logic belongs in `api/` or a service module. The FastAPI layer is a
thin translator between HTTP and your real API.

**Listing routes follow the same shape.** Every entity gets a
`GET /<entity>` that wraps the api's `query()` function. Filters
and pagination are query params; `?type=`, `?conversation_id=`,
`?limit=`, `?offset=` translate directly to keyword arguments on
the api function. Use FastAPI's `Query(...)` to **validate at
the HTTP boundary**, not just supply defaults — bare `int`
defaults with no bounds let SQLite silently misinterpret negative
values:

```python
from fastapi import Query

@router.get("", response_model=list[UserRead])
def list_users(
    type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Connection = Depends(get_db),
) -> list[UserRead]:
    return users_api.query(db, type=type, limit=limit, offset=offset)
```

Without the `ge`/`le` bounds, `?limit=-1` returns *all* rows
(SQLite treats `LIMIT -1` as "no limit") and `?offset=-1` is
silently treated as zero. The page cap your callers think they
have just disappears. With the bounds, an out-of-range value
returns `422` at the route — a clear contract failure rather
than a silent regression. The same `Query(ge=...)` discipline
applies to any numeric query param the api converts directly to
SQL.

Three other things to notice. First, the route returns `[]` on
no match (never 404) — empty results are normal, not
exceptional. Second, soft-deleted rows are excluded by default;
there's no `?include_deleted=` flag. If you ever need an "audit
deleted users" view, that's a different endpoint with different
auth, not a query-string knob — collapsing them invites
accidental disclosure. Third, the same shape extends to nested
listings like `GET /conversations/{slug}/messages`: resolve the
slug first (404 on miss), then call `query()` with the resolved
id and the same validated `limit`/`offset`.

This is **"exposing by hand"** — one HTTP route per operation, callable
by humans (curl, the OpenAPI page) and by other services. It's the
right starting point and is enough for most apps. Other ways to expose
the same internal API to other consumers (LLM agents as MCP tools,
background jobs, CLIs) come in later lessons; they all sit *on top of*
section 6, not in place of it. That's the payoff of keeping section 6
as the only thing that touches SQL.

**Authorize at the route boundary, not in `api/`.** Authentication
(*who is the caller?*) and authorization (*may they do this?*) sit on
the http layer; the api/ layer takes ids and trusts them. The split
keeps the api callable from places without an http request — tests,
CLIs, background jobs, future MCP tool surfaces — without dragging
auth-aware logic into the data path.

But the *rule* that authorizes ("only DM participants may read this
DM") is a structural fact about the model, not about HTTP. Encode it
once, in `api.conversations.is_accessible_by(db, *, conversation_id,
user_id)`, and call it from every route that reads or writes the
conversation. Pseudocode for `GET /conversations/{slug}/messages`:

```python
@router.get("/{slug}/messages")
def list_messages(slug, db, me=Depends(current_user)):
    conv = conversations.get_by_slug(db, slug) or raise NotFound(...)
    if not conversations.is_accessible_by(
        db, conversation_id=conv.id, user_id=me.id
    ):
        raise HTTPException(403, "not a participant")
    return messages.query(db, conversation_id=conv.id)
```

Two things this gets right. **The rule lives in one place** — four
routes (the messages-list, the by-id read, the flat messages query,
and the message POST) all call the same helper. Drift is impossible:
add a fifth route tomorrow and you can't *forget* the check, because
the helper exists for exactly that reason. **The api layer stays auth-
agnostic** — `is_accessible_by` takes a `user_id`, not a request, so
you can call it from a test without a TestClient or from a future MCP
tool without a session. The http layer is what reads the
`X-User-Slug` header (via `current_user`), passes the resolved id in,
and translates a `False` to a 403.

A subtle note on **403 vs 404 on deny**: returning 404 hides the
existence of the conversation from non-participants. That's stricter
but inconsistent — a non-participant can already enumerate users via
`GET /users`, and DM slugs are a deterministic function of those user
slugs (`dm-{min}-{max}`), so existence isn't really secret. We return
403, which is honest about what happened. If you ever decide existence
*is* secret (e.g. a "blocked users" feature), flip the helper's deny
path to 404.

Before you write a single `test_*.py`, write `tests/tests.md`. One
section per endpoint, then one happy-path end-to-end at the bottom.

Per endpoint, document:

- **Endpoint** — verb + path.
- **Request** — a valid example body.
- **Expected** — status code, response body shape, DB side effects.
- **Errors** — what counts as 400 / 404 / 409 / 422; one example each.
- **Soft-delete behavior** — does the deleted entity show up in `get`?
in `query`? in `rels.list`? Be explicit.

Then translate each entry into a pytest function. Use FastAPI's
`TestClient` and a fresh in-memory SQLite (`":memory:"`) per test for
isolation. The happy-path E2E exercises a realistic flow: create users
→ create a topic (which auto-creates its default conversation) →
exchange messages on that topic → open a DM between two users →
exchange messages there → soft-delete one user → confirm cascade.

**TestClient + SQLite threading gotcha — name it before students hit
it cold.** FastAPI runs *sync* route handlers in `anyio`'s threadpool,
even under `TestClient`. SQLite's Python binding refuses cross-thread
reuse by default — so a connection created on the test thread (via
the `db` fixture) raises `sqlite3.ProgrammingError` the first time
the handler tries to use it from a worker thread. The fix is one
keyword in the connection call inside the test fixture:

```python
# tests/conftest.py
conn = sqlite3.connect(":memory:", check_same_thread=False)
```

The failure looks like magic on first encounter — your test code is
single-threaded, you didn't spawn anything, why is SQLite complaining
about a worker thread? Two design decisions are colliding:

1. **FastAPI offloads sync handlers to a worker thread.** A `def`
   handler can't run on the event loop — it would block every other
   in-flight request until it returned. So FastAPI hands it to
   `anyio`'s threadpool: the event loop awaits the offload, a worker
   thread runs the handler, the result comes back. This is true under
   `uvicorn` *and* under `TestClient` (which is `httpx` driving the
   ASGI app in-process — same threading model, no socket).
2. **`sqlite3.Connection` is thread-bound by default.** A connection
   "belongs to" the thread that created it; touch it from another
   thread and the binding raises `ProgrammingError`. The engine
   itself is fine with multi-threading (`SQLITE_THREADSAFE=1`); the
   *Python binding* is conservative for historical reasons that
   were never relaxed for backwards-compat.

Trace what happens when the test calls `client.post("/users", ...)`:

```
test code (main thread)
  → TestClient drives ASGI (main thread)
    → FastAPI offloads sync handler to a WORKER thread
      → handler resolves Depends(get_db)
        → override returns the conn opened on MAIN thread
      → handler calls db.execute(...)
        → binding: "you're on the worker, but I was opened on main"
        → ProgrammingError
```

**Production needs the same flag** — for a related but different
reason. FastAPI's `anyio` threadpool doesn't guarantee that the
`get_db` dep and the route handler land on the *same* worker
thread within one request. The dep runs in worker A, opens the
connection; the handler runs in worker B, calls `db.execute(...)`;
the binding's per-thread guard fires. Different cause from the
test case (where the connection is shared from the main thread
into a worker), same fix:

```python
# wazzup/db.py
def connect() -> Connection:
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    ...
```

Why doesn't the test override mirror the production shape — open a
fresh connection per call, inside the worker? Because `:memory:`
databases are per-connection. A fresh-per-call override would give
each request a different empty DB, and the assertions on the test
thread couldn't see what the handler wrote. The whole point of the
override is to share *one* DB across the test setup, the handler,
and the assertions. That sharing is what crosses threads.

`check_same_thread=False` turns the binding's check off. SQLite
itself handles the access pattern fine in both setups — uvicorn /
`TestClient` serialize the requests through one connection at a
time; we're not introducing real concurrency, just letting the
connection cross thread boundaries between consecutive calls.

The flag belongs in **both** the production `connect()` and the
test fixtures. A subtle teaching trap is to add it only to the
fixture, ship a passing test suite, and discover the
`ProgrammingError` the first time you run `uvicorn`. Keep them
aligned: same flag, same justification, same line of defense.

The failure message ("SQLite objects created in a thread can only
be used in that same thread") is clear about the *what* but hides
the *why*: FastAPI is silently spawning a worker thread for you,
two layers below your code. Once a student knows the sync-handler
offload exists, the entire failure makes sense.

**Test-altered schemas — when a test needs more (or less) than the
production shape.** Every test gets a fresh DB by default; that's
the *isolation* axis. The second axis is *schema variation*: some
tests need an extra audit trigger, an extra index for query-plan
verification, a denormalized snapshot table, or even a relaxed
constraint to exercise a collision path. Don't put any of that in
the production schema — keep `init_schema()` canonical and let
tests compose on top via a fixture factory:

```python
# in tests/conftest.py
import pytest, sqlite3
from sqlite3 import Connection
from wazzup.db import init_schema

@pytest.fixture
def db_factory():
    """Build a fresh DB; optionally layer extra SQL on top of the production schema."""
    def _make(extra_sql: list[str] | None = None) -> Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_schema(conn)                  # production schema, unchanged
        if extra_sql:
            for stmt in extra_sql:
                conn.execute(stmt)
        return conn
    return _make
```

A test that needs schema-level instrumentation:

```python
def test_cascade_writes_audit(db_factory):
    db = db_factory(extra_sql=[
        "CREATE TABLE _audit (op TEXT, tbl TEXT, row_id INTEGER, ts TEXT)",
        "CREATE TRIGGER user_audit AFTER UPDATE ON user "
        "BEGIN INSERT INTO _audit VALUES ('update', 'user', NEW.id, datetime('now')); END",
    ])
    # ... exercise code that should trigger audits, then assert
    # against _audit rows ...
```

The base `db` fixture (production schema only) stays the default
for most tests; reach for `db_factory` only when a test genuinely
needs schema-level instrumentation. The principle: production code
shouldn't know that tests want extra tables; tests compose what
they need on top.

**SQLite's `ALTER TABLE` limitation, worth naming up front.** You
can `ADD` a column, but you can't easily drop one or change a
constraint without a table rebuild. If a test needs to relax a
constraint (e.g., to exercise what happens when a `UNIQUE` is
violated mid-transaction), the recipe is `DROP TABLE x;` followed
by `CREATE TABLE x (...);` with the alternative shape — also
something `extra_sql` handles. Just know the limitation exists so
you don't spend an afternoon trying to `ALTER` your way around it.

---

## 10. Examples that double as smoke tests

Three scripts in `examples/` that import the internal API directly
(no HTTP). They're the first thing a learner runs and they sanity-
check the install. Each owns its DB lifecycle (open via
`wazzup.db.connect()`, run `init_schema()` first), and each prints
what it did so the smoke output is human-readable:

- **`seed.py`** — populates a fresh DB with the canonical demo
state described in `docs/DEMO.md`: humans + agents with personas,
public topics (each one auto-creating its default conversation
in the same transaction), one seeded DM (`alice` ↔ `curie`) so
the DM path is exercised, and a handful of seeded messages
exercising each agent's voice. Idempotent — every step is
`get_by_slug`-then-skip, so re-runs are safe (and *will* happen
during debug); the seed also self-heals if a topic exists
without its default conversation, calling `deviation()` so the
drift is loud.
- **`add_user.py`** — single-purpose CLI: take a name (and optional
`--type`, `--persona`, `--slug`), call `users.create`, print the
resulting `UserRead` as JSON. The smallest possible "is the install
working?" smoke.
- **`remove_user.py`** — cascade-demo CLI: take a slug, call
`cascade_delete(table="user", id=...)` (not the public
`users.delete` — we want the report), print the `CascadeReport`
showing how many rels were swept up. `--hard` for physical removal.

If all three run clean, the foundation works. Run them like this:

```bash
# from the project root, after `pip install -e '.[dev]'`
python -m examples.seed                              # produce DEMO.md state
python -m examples.add_user "Charlie Wong"           # smallest smoke
python -m examples.add_user "Tesla" --type agent --persona "Cryptic and electric."
python -m examples.remove_user alice                 # soft-delete + cascade
python -m examples.remove_user alice --hard          # then physically remove

# re-run seed to confirm idempotency — every line should say "(exists, …)"
python -m examples.seed
```

`seed.py`'s output reads like a build log:

```
seeding wazzup demo state…
  user: Alice Smith           created (slug=alice, id=1)
  user: Bob Jones             created (slug=bob, id=2)
  user: Donald Trump          created (slug=trump, id=3)
  user: Marie Curie           created (slug=curie, id=4)
  user: Yoda                  created (slug=yoda, id=5)
  topic: Engineering          created (slug=engineering, id=1, default_conv=engineering)
  topic: Random               created (slug=random, id=2, default_conv=random)
  topic: Daily Standup        created (slug=daily-standup, id=3, default_conv=daily-standup)
  dm: alice ↔ curie           created (slug=dm-alice-curie, id=4)
  messages: 4 in daily-standup, 2 in dm-alice-curie
done.
```

`remove_user.py`'s output makes the cascade visible — that's the
whole point of having a script for it:

```
$ python -m examples.remove_user alice
user 'alice' (id=1) has 4 src rels + 1 tgt rels
{
  "operation": "soft delete",
  "slug": "alice",
  "id": 1,
  "report": {"primary": 1, "rels": 5, "messages": 0}
}
```

**The seed agents.** A small fixture set keeps demos and tests
realistic without inventing characters every time. The personas
are markdown blobs in the `user.persona` column (section 2);
`seed.py` writes them in via `UserCreate(name=..., persona=..., slug=...)`:

```python
# in examples/seed.py — the canonical persona triple
SEED_AGENTS = [
    {
        "name": "Donald Trump", "slug": "trump", "type": "agent",
        "persona": (
            "You are Donald J. Trump. You speak with tremendous "
            "confidence — the greatest confidence, frankly. Use "
            "hyperbole liberally: the best, the worst, tremendous, "
            "fake news. Short sentences. Many of them."
        ),
    },
    {
        "name": "Marie Curie", "slug": "curie", "type": "agent",
        "persona": (
            "You are Marie Curie. You speak with quiet rigor and "
            "measured curiosity. Favor precise observations over "
            "speculation; be patient with people working out an "
            "idea, even when it's wrong."
        ),
    },
    {
        "name": "Yoda", "slug": "yoda", "type": "agent",
        "persona": (
            "Yoda, you are. Speak you do, with inverted syntax. "
            "Wisdom you offer, in short pronouncements. Toward the "
            "deeper truth, others you guide — by asking questions, "
            "not by answering them."
        ),
    },
]
```

The script then opens a connection via `wazzup.db.connect()`,
calls `init_schema()` (which is idempotent and includes the
schema-drift check from section 5), and walks the seed data
calling `users.create`, `topics.create`, `rels.add`,
`conversations.create`, and `messages.create` — all the same
api functions an HTTP route would call, just driven by a Python
script instead of a request.

Three or four distinct voices is enough — too many and the demo
gets noisy. Pick personas with *recognizably different* speech
patterns; subtle differences are wasted on a teaching app.

**Pair `seed.py` with `docs/DEMO.md`.** `seed.py` is the
*executable* mechanism — what populates the database. `docs/DEMO.md`
is the *spec* — what the seeded state looks like, what the demo
walkthrough should produce, and what each persona's voice sounds
like in a real conversation. Same shape as `tests.md` (behavior
spec for tests) or `docs/MODEL.md` (spec for the schema): a
human-readable reference that anyone — engineer, PM, teaching
assistant — can read without running the code. When you change
the seeded data, you update `DEMO.md` first.

A starter `docs/DEMO.md` lists: the seeded users (humans + agents
with their personas), the topics with their auto-created default
conversations, the seeded DM, sample messages that exercise each
persona's voice, and a step-by-step demo walkthrough (*"open the
UI, identify as alice, open the daily-standup topic, post 'what's
everyone working on?', watch each agent reply with its own voice;
then click curie in the People sidebar to open the DM"*). When
demoing live, follow the script; when extending the seed, update
the script.

---

## 11. Logging

Stdlib `logging`, configured once in `logging_setup.py`. One JSON-ish
line per record (`{"ts", "level", "logger", "msg", ...kwargs}`).
Level via env (`LOG_LEVEL=DEBUG python -m wazzup`). Each module:
`log = logging.getLogger(__name__)` — never use the root logger
directly. FastAPI middleware injects a `request_id` into every log
line for one request's worth of tracing; the cheapest observability
win there is.

**No silent failures — the most important rule.** Every path that
deviates from your expectation gets logged at WARNING or above, with
structured context. The cheapest place to lose a bug is `except: pass`
or a `None` return value that the caller quietly ignored. Make
deviations *loud*. Concretely:

- **Never `except: pass`, and never bare `except:`.** If you catch
an exception, you log it (`log.exception(...)` or `exc_info=True`
to preserve the stack trace) *before* deciding whether to swallow,
re-raise, or transform. The traceback is the one thing you cannot
reconstruct later.
- **Catch only what you intend to handle.** `except Exception:` is
almost always wrong — name the specific exception. A broad catch
that hides a programming bug as a "user error" is a silent failure
with extra steps.
- **Log every branch that means "this didn't go as expected".**
These are *deviations* — use the `deviation()` helper from
the next block, which is built for exactly this. Soft-delete
that matched no rows: `deviation("delete: no row matched", id=user_id)`. Retry exhausted:
`deviation("retry exhausted", attempts=3)`. Config value
falling back to a default:
`deviation("config X missing, defaulting to Y")`. Expected
events that aren't deviations get plain INFO logs with
`extra={...}` — for example a retry attempt that's known to
happen: `log.info("retry", extra={"attempt": 2, "of": 3})`.
- **Log the WHAT *and* the WHY, with structured fields.**
`log.warning("failed")` is useless.
`deviation("delete failed: no row matched", id=user_id, table="user")` is greppable and aggregable; the same applies
to `log.info("...", extra={...})` for non-deviation events.
Treat the structured fields as columns in a future debugging
query — consistent names matter, so settle on `id` vs
`user_id`, `count` vs `n`, etc., once and stick to it.
- **stdlib quirk worth knowing.** `logging.Logger.warning(msg, *args, **kwargs)` doesn't accept arbitrary kwargs — only a
fixed set including `extra={...}`. So `log.warning("...", id=user_id)` raises `TypeError`. The `deviation()` helper
hides this by translating its `**kwargs` to `extra=kwargs`
internally. If you call stdlib directly (for INFO-level
events, say), use `extra={...}` explicitly.

**When `except Exception:` is actually OK — and how to tell.** The
"almost always wrong" rule above is doing real work in that
"almost" — a few shapes are legitimate. They share a specific
structure that separates them from the anti-pattern, and being
able to articulate that structure is what keeps you honest the
next time you reach for a broad catch.

*Why "Exception" is the wrong target by default.* Python's
exception hierarchy collapses categories you actually want to
distinguish into one bucket: `ValueError` (user-error),
`IntegrityError` (conflict), `ConnectionError` (transient), and
`TypeError` / `KeyError` / `AttributeError` / `OperationalError`
(programmer-error — typos, missed `None`s, bad SQL). The first
three are recoverable in different ways with different responses;
the fourth is a *bug in your code* that should crash so you fix
it. `except Exception:` treats them all the same — and once
they're in the same bucket, you can't recover them differently.
The typo lives.

*Four shapes where a broad catch is justified:*

1. **The outermost boundary of a process that must not die.** A
   long-running worker (queue consumer, daemon, Celery task) that
   processes one message at a time. If one message blows up, you
   log loudly and move to the next instead of killing the worker:

   ```python
   while True:
       msg = queue.get()
       try:
           handle(msg)
       except Exception:
           log.exception("handler failed", extra={"msg_id": msg.id})
           queue.dead_letter(msg)
   ```

   The catch is at the *outermost* layer — nothing below it
   should run if `handle` failed. FastAPI does the equivalent of
   this for you per-request, which is why you don't need to write
   it inside route handlers.

2. **Log-and-re-raise (annotate, don't handle).** You're not
   actually handling the exception — you're attaching context,
   then re-raising so it propagates as normal:

   ```python
   try:
       cascade_delete(db, "user", user_id)
   except Exception:
       log.exception("cascade failed",
                     extra={"user_id": user_id, "table": "user"})
       raise
   ```

   The `raise` is the load-bearing line. The catch isn't
   *handling*; it's *annotating*. Callers still see the failure.

3. **Plugin or user-supplied code boundaries.** Your code calls
   into something you don't control — a plugin, a callback, an
   LLM-generated tool dispatch. You can't enumerate what it
   raises; the boundary is real:

   ```python
   try:
       result = plugin.run(data)
   except Exception as e:
       log.exception("plugin failed", extra={"plugin": plugin.name})
       return PluginError(name=plugin.name, error=str(e))
   ```

4. **Reporters and last-ditch cleanup.** Code that emits errors
   to another system (Sentry shim, metrics flusher, audit log)
   wraps its own work broadly because *the reporter must not be
   the thing that crashes*. Same for cleanup paths in `finally`
   blocks where a cleanup failure shouldn't mask the original
   error.

*The structural pattern that makes them OK.* All four share the
same shape:

- **The catch is at a meaningful boundary** — a process edge, a
  plugin boundary, a reporter — not in the middle of business
  logic.
- **The "recovery" is explicit and loud** — `log.exception(...)`
  (which includes the stack trace) at ERROR level, plus a
  deliberate next step (dead-letter, re-raise, return a sentinel
  the caller actually checks).
- **The catch doesn't make a bug look like a normal outcome.** A
  `KeyError` from a typo never gets converted into a
  `return None` that looks like "not found."

The anti-pattern fails all three. It's in the middle of business
logic, the recovery is `return None` or `log.warning(...)` (too
quiet, no traceback), and the bug-vs-recoverable-condition
distinction is lost.

*A sharper rule of thumb:* use `except Exception:` only when (a)
you're at a boundary where the alternative is the whole process
dying, and (b) you can articulate, in one sentence, why every
exception under it is recoverable in the same way. If either is
hard to answer, the catch is too broad.

For wazzup, this means almost nowhere in `api/` or `http/`. The
error conventions table in section 6 covers the cases with
specific recovery (`IntegrityError` → 409, `NotFound` → 404);
everything else propagates to FastAPI's default handler → 500
with the stack trace logged. The one place a broad catch might
appear legitimately as wazzup grows is an LLM tool-call
dispatcher (lessons 2–3), where the contract with the called
function is opaque — that fits shape 3. Until then, every
`except Exception:` in this codebase is a code smell.

**Make strictness a flag.** A helper that wraps "log a warning"
turns the warning-vs-crash decision into a runtime choice — same
code, different posture per environment:

```python
# in logging_setup.py
import os, logging

log = logging.getLogger(__name__)

class UnexpectedDeviation(RuntimeError):
    """Raised by deviation() when STRICT_MODE=1."""

STRICT = os.getenv("STRICT_MODE", "0") == "1"

def deviation(msg: str, **kwargs) -> None:
    """Mark an unexpected path. Logs WARNING normally; raises in strict mode."""
    if STRICT:
        raise UnexpectedDeviation(f"{msg} | {kwargs}")
    log.warning(msg, extra=kwargs)
```

Every "this shouldn't normally happen" branch calls `deviation(...)`
instead of `log.warning(...)`. Run `STRICT_MODE=1 pytest` (or in CI)
and any unexpected branch crashes loudly at the source line. Unset
or `STRICT_MODE=0` in production and the same call logs and keeps
going — you don't want a latent deviation taking down a live
service. Two payoffs: `grep deviation` is now the audit of every
place your code admits surprise, and CI is what enforces it. Lazy
contributors who'd rather slip a quiet `log.warning(...)` past
review have to write `deviation(...)` instead, and CI does the
review for them.

**Testing deviation paths in strict mode.** When a test
*deliberately* exercises a deviation — to verify error
handling, for example — it should `pytest.raises` on
`UnexpectedDeviation`, not just rely on a log line:

```python
def test_delete_unknown_id_logs_deviation(db):
    with pytest.raises(UnexpectedDeviation, match="no row matched"):
        users.delete(db, 99999)
```

Run that test under `STRICT_MODE=1` (the CI matrix's strict
leg) and the `pytest.raises` succeeds because `deviation()`
raises. Under `STRICT_MODE=0`, `deviation()` only logs — the
test would silently pass without exercising the assertion,
which is the wrong outcome. CI runs *both* legs (section 12);
this kind of test only meaningfully passes in the strict one.
The non-strict leg is for catching tests that *accidentally*
trigger deviations (which would now crash) — different
purpose, same machinery.

**Levels with deliberate semantics:**

- `DEBUG` — only useful when actively debugging. Off in production.
- `INFO` — normal operational events worth a record ("login",
"message posted", "cascaded soft-delete to 7 messages"). Rule of
thumb: *would I want to see this in the logs of a healthy system?*
- `WARNING` — something deviated from expectation but the system
kept going. **This is the "no silent failures" level.** Be liberal
here; over-warning is recoverable, under-warning is not.
- `ERROR` — a user-visible operation failed. The thing the user
asked for didn't happen.
- `CRITICAL` — the process is degraded or shutting down.

**Where to log:**

- **At the HTTP boundary**, log the call and the outcome —
`log.info("create_user", extra={"name": ..., "type": ...})` on
entry, `deviation(...)` on validation rejection or other
unexpected branches, `log.error("create_user_failed", exc_info=True, extra={...})` if the underlying call raises.
The `request_id` middleware handles the per-request
correlation; you handle the per-call story.
- **Inside the API layer**, log only deviations and decisions
(cascade counts, fallbacks, retries). Successes go at DEBUG — too
noisy at INFO in production, useful when reproducing a bug with
`LOG_LEVEL=DEBUG`.
- **Don't log on both sides of a re-raise.** If you log and re-raise,
the caller logs again, and you double-count. Log at the layer that
*handles* (or decides not to handle) the exception, not at every
layer it passes through.

---

## 12. Make mistakes loud, early, and unmergeable

Strict-mode logging (section 11) catches the deviations you *thought*
about. The other half of "lazy-programmer-proof" is preventing the
*unannotated* ones from reaching `main` at all. Four cheap project-
config decisions do most of the work, in increasing order of
friction:

1. **Lint with ruff.** Enable rules that ban the canonical bad
  patterns: `S110` (try-except-pass), `BLE001` (broad
   `except Exception`), `T201` (`print` statements), and the
   standard pyflakes set. Configure once in `pyproject.toml`. CI
   runs `ruff check .` on every PR; sloppy code can't merge — not
   "shouldn't", *can't*.
2. `**pytest -W error`.** Set `filterwarnings = ["error"]` in the
  `[tool.pytest.ini_options]` table of `pyproject.toml`. Python's
   own `DeprecationWarning`, `ResourceWarning`, and any warning a
   library emits become test failures. Combined with strict-mode
   logging, both the "we know about it" and "we don't know about
   it" failure modes surface during tests.
3. **Branch coverage**, not line coverage. `coverage.py` with
  `branch = True` in `pyproject.toml` forces tests to exercise
   *both* sides of every `if` and the `except` of every `try`. Line
   coverage reports green on the happy path; branch coverage hits
   the path lazy programmers skip.
4. **Type-check with mypy strict (or pyright).** Functions returning
  `Optional[T]` force every caller to handle `None` at static-check
   time. The "I forgot to handle the failure case" bug class
   disappears before the code runs. Higher friction than the
   previous three — but it pays back fast if you're already writing
   typed Python.

**Continuous integration: half discipline, half mechanics.** The
discipline is *"every change to the main branch should run the test
suite on a clean machine before it gets accepted."* The mechanics
are how you automate that. GitHub Actions is the standard answer
for projects on GitHub — a way to tell the platform *"every time
someone pushes, do the following on a fresh Linux box."*

The flow is straightforward. Push a branch (or open a PR). GitHub
sees `.github/workflows/ci.yml` and reads it. The file says *"on
push, run a job; the job consists of these steps."* GitHub spins
up a virtual machine, runs the steps, captures the output, reports
the exit status. Green checkmark on success, red X on failure with
a clickable log. PRs can be configured to require the green check
before they can be merged — that's *branch protection*, a separate
setting in the repo config.

**The runner is ephemeral.** Every job runs on a fresh, ephemeral
VM that GitHub provisions on demand. `runs-on: ubuntu-latest` is
the standard ask (currently Ubuntu 24.04). You don't own this VM;
it boots with a base image, runs your steps, and gets destroyed.
The "clean machine" part is what catches environmental drift: if
the suite passes on this fresh box but fails on your Mac, your
Mac has something installed it shouldn't. CI's job is finding
exactly that.

**Workflow → jobs → steps.** A workflow is one YAML file under
`.github/workflows/`. It contains one or more jobs, each running
on its own runner. A job is a sequence of steps; each step is
either a *shell command* (`run: pytest -v`) or an *action*
(`uses: actions/checkout@v4`). Actions are reusable bundles
maintained by GitHub or third parties — pinned by tag, like
`actions/checkout@v4`. The first step of any job is almost always
`actions/checkout@v4`, which clones your repo into the runner's
filesystem; after that you do whatever you want.

**Triggers.** The `on:` key declares when the workflow fires.
Common ones: `push` (every push to any branch), `pull_request`
(when a PR opens or updates), `schedule` (cron-style; useful for
nightly tests), `workflow_dispatch` (a manual "Run" button in the
GitHub UI). A `paths:` filter under `push`/`pull_request` keeps
the workflow from running on irrelevant changes — for a repo where
the app lives in a subdirectory next to other content (like a
lesson `.md`), filter to the subdirectory so doc-only edits don't
chew through CI minutes.

**The matrix: the same test suite, two postures.** A single job
can fan out into multiple parallel runs by declaring
`strategy.matrix`. This is exactly the shape we want for the
two-leg STRICT_MODE story: one matrix entry runs the suite with
`STRICT_MODE=0` (proves production behavior, no surprises in
prod), another with `STRICT_MODE=1` (forces every annotated
deviation in the exercised code paths to crash). Both have to
pass for the workflow to be green. Both run simultaneously on
independent runners, so wall-clock time is roughly one run, not
two.

**The CI in full.** Around 35 lines of YAML, well-commented.
Step 1: checkout. Step 2: install `uv`. Step 3: pin Python.
Step 4: `uv sync --extra dev` to install everything from
`pyproject.toml`. Step 5: `uv run ruff check .` (fail-fast — no
point running tests against unlinted code). Step 6: `uv run
pytest -v` with `STRICT_MODE` from the matrix. ~60–90 seconds
end-to-end on standard runners.

```yaml
# .github/workflows/ci.yml
name: ci

on:
  push:
    paths: ['wazzup/**', '.github/workflows/ci.yml']
  pull_request:
    paths: ['wazzup/**', '.github/workflows/ci.yml']

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: wazzup       # app lives in this subdir
    strategy:
      fail-fast: false                  # show both legs; don't kill leg B when A fails
      matrix:
        strict: ["0", "1"]              # lax + strict, both must pass

    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: install
        run: uv sync --extra dev

      - name: lint
        run: uv run ruff check .

      - name: test
        run: uv run pytest -v
        env:
          STRICT_MODE: ${{ matrix.strict }}
```

Two design notes worth naming. **`fail-fast: false`** keeps the
strict leg running even when the lax leg fails — you want to see
both signals, not just the first failure. **`working-directory`**
at the job-defaults level tells every `run:` step to `cd wazzup`
first, which matters because `pyproject.toml` lives in the
subdirectory, not the repo root.

**The PR experience.** Once CI is wired up, opening a PR shows
the run inline with checkmarks per matrix leg. Branch protection
rules (in repo settings, not in the YAML) can mandate the green
check before the merge button is enabled — that's the thing that
converts CI from "nice to have" to "actually enforces the rule."
For a single-developer teaching repo it's optional; for any team,
it's the difference between *"we discussed merging only on green"*
and *"the platform enforces merging only on green."*

**Cost.** Public repos: free, no minute cap. Private repos:
2,000 free CI-minutes per month on the Free plan. macOS minutes
count 10x; Windows 2x; Linux 1x — we're firmly Linux. For a
project of this size, public-repo CI is effectively unlimited.

**A status badge for the README.** Once CI is set up, GitHub
gives you a Markdown snippet that renders as a green/red badge:

```markdown
![CI](https://github.com/<org>/<repo>/actions/workflows/ci.yml/badge.svg)
```

Drop it at the top of `README.md` and visitors see build status
without clicking. It's the public-facing version of the
per-commit checkmark.

**Footguns worth knowing.**

- *Action versions drift.* `actions/checkout@v4` is current;
  older majors still work but won't get security fixes. Pin
  majors, bump when they're deprecated.
- *Caching is a separate concern.* Without it, every run
  downloads dependencies fresh (~10 seconds for our deps).
  `actions/cache` or `uv`'s cache directory speeds this up. Skip
  until it matters; for a 60-second job, premature.
- *Secrets.* Anything sensitive (API keys, tokens) goes in
  *Settings → Secrets*, never the YAML. wazzup's CI doesn't need
  any — the LLM tests don't make live calls.
- *Workflow file path is exact.* It has to be
  `.github/workflows/<name>.yml`. A typo in the directory
  (`workflow/` without `s`) silently does nothing — GitHub
  doesn't warn you.

The principle behind the whole stack: **a mistake that fails
loudly in dev or CI is free; a mistake that fails silently in
production is expensive.** Push every deviation as far left as
you can. Lint catches it before tests run. Types catch it before
lint. Strict mode catches what the others missed. CI is the
forcing function: production gets the cleaned-up code, with the
tools doing the review that lazy contributors won't.

---

## 13. A simple UI: HTML and JavaScript over the HTTP surface

You have an HTTP API (section 8). To make it usable from a
browser, the simplest thing that works is **plain HTML, vanilla
JavaScript, and CSS**, in a folder *separate from the Python
package*, served independently. The API and the UI are two
different things. The UI consumes the API like any other client
— the same shape as the agent clients in lessons 2–3.

That separation is deliberate. Mixing static-file serving into
FastAPI works (one line in `http/main.py` and you're done), but
it conflates two jobs — *answering API requests* and *hosting a
web app* — into one process. For a teaching app where the
architectural lesson is *"each surface has a clear purpose"*, the
clean separation is worth the small extra setup.

**Folder layout.** The `ui/` folder lives at the repo root, *not*
inside the `wazzup/` Python package:

```
wazzup/                    # repo root
├── wazzup/                # Python backend package
│   ├── api/
│   ├── http/
│   └── …
├── ui/                    # browser UI — its own thing
│   ├── index.html
│   ├── app.js
│   └── style.css
├── tests/
├── examples/
└── pyproject.toml
```

**Running locally — two processes:**

- The API: `uvicorn wazzup.http.main:app --port 8000`
- The UI: `python -m http.server 8001 -d ui/` (built-in, no
install needed) — or any other static server.

Open `http://localhost:8001` in a browser. The page loads from
the static server; its JavaScript calls the API at
`http://localhost:8000`. Two URLs, one app.

**CORS.** Because the UI and the API are on different origins
(`:8001` vs. `:8000`), the browser blocks API calls by default.
Add FastAPI's CORS middleware in `http/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8001"],   # the UI's dev origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

In production, replace the dev origin with whatever URL the UI
deploys to. Keep the list explicit; never `["*"]` if the API
requires auth.

**The interaction pattern.** Every UI interaction is the same shape:

1. User does something (clicks, types, submits).
2. JS calls a `/...` endpoint with `fetch()`, including
  `Authorization: Bearer <token>`.
3. JS reads the JSON response.
4. JS updates the DOM — replaces a list, appends a message,
  shows an error.

Rendering the conversations list, in full:

```html
<!-- in ui/index.html -->
<aside>
  <h2>Conversations</h2>
  <ul id="conversations-list"></ul>
</aside>
<script src="app.js"></script>
```

```javascript
// in ui/app.js
const API = "http://localhost:8000";

async function loadConversations() {
  const r = await fetch(`${API}/conversations`, {
    headers: { Authorization: `Bearer ${getToken()}` }
  });
  if (!r.ok) {
    showError(`load failed: ${r.status}`);
    return;
  }
  const conversations = await r.json();
  const ul = document.getElementById("conversations-list");
  ul.innerHTML = "";
  for (const c of conversations) {
    const li = document.createElement("li");
    li.textContent = c.name;
    li.onclick = () => loadMessages(c.slug);
    ul.appendChild(li);
  }
}
```

The pattern repeats: `loadMessages(slug)`, `postMessage(text)`,
`login(name, password)`. Each one is *fetch → check status →
parse JSON → update DOM*. Maybe 50–100 lines of JS for the whole
UI.

**Where the auth token lives.** The token from `/auth/login` is
what the UI carries on every subsequent request. For the
teaching app, `localStorage`:

```javascript
function getToken() { return localStorage.getItem("wazzup_token"); }
function setToken(t) { localStorage.setItem("wazzup_token", t); }
```

Simple, persists across reloads, easy to inspect for debugging.
Vulnerable to XSS in production — the production answer is
`HttpOnly` cookies with server-side issuance and CSRF
protection. Out of scope here.

**Until real auth lands: the dev-mode shortcut.** Real
`/auth/login` doesn't exist yet (see *"What we haven't built"*),
so the UI in this lesson runs against `AUTH_DISABLED=1` on the
server. In that mode, the *header* is the identity:

```javascript
async function fetchAPI(path, options = {}) {
  return fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      "X-User-Slug": localStorage.getItem("wazzup.user_slug") || "alice",
      "Content-Type": "application/json",
    },
  });
}
```

A two-line "switch user" form (prompt the user for a slug, write
to `localStorage`, reload) is enough to demo multi-user flows.
When real auth lands, the same `fetchAPI` wrapper switches from
`X-User-Slug` to `Authorization: Bearer <token>` and the routes
that consume `current_user` don't change.

**What this UI doesn't try to be:**

- **Real-time updates.** No WebSockets, no Server-Sent Events.
The UI re-fetches when you click. Push updates are their own
topic.
- **Component reuse.** Without a framework, list-rendering code
is written by hand each time. Fine for ~5 interactions.
- **Loading and error states.** Production UIs show spinners,
retries, friendly errors. This recipe just calls
`showError("...")` as a placeholder.

**Deployment note.** In production, you have two reasonable
shapes:

- *Keep them separate* — UI on a static host (S3, Vercel,
Netlify, nginx), API on its own service. Different
deployments, different scaling, different teams can own them.
This is the production form of the dev setup above.
- *Colocate* — serve the UI from FastAPI itself with
`app.mount("/", StaticFiles(directory="ui", html=True))` after
all API routes. Same origin, no CORS needed, single
deployment. Practical for small apps; less clean
architecturally.

The choice is a *deployment* decision, not an architectural one.
The dev setup keeps them separate so the boundary is visible;
how you deploy is yours.

**When to graduate**, in roughly increasing toolchain weight:

- **htmx** (~14KB script) — server returns HTML *fragments*,
the browser swaps them into the DOM via attributes like
`hx-get="/messages" hx-target="#list"`. No build step, no npm.
The "rich interactivity without leaving Python" answer if you
later decide co-locating UI and server is worth it.
- **Alpine.js** (~16KB) — reactive sprinkles for component
state (`x-data`, `x-show`) without a build step.
- **A real SPA framework** (React, Svelte, Vue) when you have
enough state and reuse to justify the build tooling.

For wazzup, none of these are needed. Plain HTML + JS reaches
the same FastAPI surface as any of them; what changes is the
language you use to drive it.

---

## 14. Talking to LLMs: the `LLM` helper

For AI users (`type="agent"`) to compose messages — and for any
other place wazzup needs to call a language model — there's one
small wrapper at `wazzup/llm.py`. It reads provider, model, and
API key from environment variables and dispatches to the right
SDK.

```python
# in wazzup/llm.py
import os

def _client():
    """Build the right OpenAI-compatible client based on LLM_PROVIDER."""
    from openai import OpenAI, AzureOpenAI
    provider = os.environ.get("LLM_PROVIDER", "openai")
    api_key = os.environ["LLM_API_KEY"]
    if provider == "openai":
        return OpenAI(api_key=api_key)
    if provider == "openrouter":
        return OpenAI(api_key=api_key,
                      base_url="https://openrouter.ai/api/v1")
    if provider == "azure":
        return AzureOpenAI(
            api_key=api_key,
            azure_endpoint=os.environ["AZURE_ENDPOINT"],
            api_version=os.environ.get("AZURE_API_VERSION",
                                       "2024-02-15-preview"),
        )
    raise ValueError(f"unknown provider: {provider}")

def call(messages: list[dict], **kwargs) -> str:
    """OpenAI-style messages in, assistant reply (text) out."""
    model = os.environ["LLM_MODEL"]
    r = _client().chat.completions.create(
        model=model, messages=messages, **kwargs,
    )
    return r.choices[0].message.content
```

The wrapper is intentionally thin. All three providers expose
OpenAI-compatible chat APIs (Azure via `AzureOpenAI`,
OpenRouter via `OpenAI` with a different `base_url`), so the
dispatch is just *"build the right client, call the same
method."* When you need streaming, function-calling, or
provider-specific features, add functions alongside `call()` —
or graduate to LiteLLM (lesson 4) for a proper gateway with
routing, fallback, and cost tracking.

**Configuration via `.env`.** The class reads from environment
variables. Check a `.env.example` into git as the template;
never check in the actual `.env`:

```bash
# .env.example — copy to .env and fill in
LLM_PROVIDER=openai            # one of: openai, azure, openrouter
LLM_MODEL=gpt-4o-mini          # provider-specific model name
LLM_API_KEY=sk-...             # your key

# Azure-only (ignored for other providers)
AZURE_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2024-02-15-preview

# Section 11 / 12 flags (also part of the env)
LOG_LEVEL=INFO
STRICT_MODE=0                  # set to 1 in CI
AUTH_DISABLED=1                # dev-mode auth bypass; never enable in prod
```

Load it at process startup with `python-dotenv` or a similar
library, or have your shell source it before running uvicorn.

**Where `.env` lives — exactly once, at the repo root.** Same
level as `pyproject.toml` and `.env.example`. *Not* inside the
inner `wazzup/` package — packaging tools ship the package's
contents, and you don't want secrets accidentally riding along
in a `pip install`.

```
wazzup/                    # repo root
├── .env                   # never committed; real secrets
├── .env.example           # committed; template only
├── pyproject.toml
└── wazzup/                # Python package — no .env in here
```

`python-dotenv` walks up from the current working directory to
find it; running `uvicorn` from the repo root picks it up
automatically.

**.gitignore** at the repo root, with the `.env` rule defensive
enough to catch any `.env` at any depth:

```gitignore
# Environment / secrets
.env
.env.local
*.env.local

# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/

# Virtual environments
.venv/
venv/

# Testing / tooling caches
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# SQLite databases
*.db
*.db-journal

# IDE
.vscode/
.idea/
```

The `.env` rule (no leading slash) matches any file named
`.env` at any depth — belt-and-suspenders for the *"don't put
.env inside the package"* rule above.

**Usage.** Anywhere in wazzup you need to call a model:

```python
from wazzup import llm

reply = llm.call([
    {"role": "system", "content": user.persona},   # the agent's persona
    {"role": "user", "content": "What's on your mind?"},
])
```

The `system` prompt is the agent's `persona` markdown from
section 2 — that's the whole point of having `persona` as a
dedicated column. Each agent user becomes a different "voice"
just by changing what gets passed as the system message.

**Two consumers, today and tomorrow.** Lesson 1 uses
`llm.call()` inside agents that compose their own messages (an
agent reads recent conversation, generates a reply via
`llm.call(...)`, posts the message back through the API).
Lesson 2 will use the *same* function for the agent client's
own LLM calls when running the tool-calling loop. One wrapper,
two consumers — the right
shape because *"talking to a language model"* is a primitive
that shows up at multiple layers.

---

## 15. Documentation that lives in the repo

Four documentation files belong alongside the code, each with
a distinct audience and a distinct job:

- `**README.md`** (root) — for humans landing on the repo:
what wazzup is, how to clone-install-run-test, where the
lesson docs live. ~50 lines, scannable. *Quickstart.*
- `**docs/MODEL.md*`* — the conceptual model frozen as a
*spec* rather than a narrative. Section 1 of this lesson is
the narrative; `docs/MODEL.md` is the column-by-column
reference, the invariants list, the cascade rules, the
relationship-types list (including the conversation↔topic
auto-creation rule and the DM-detection rule). When you
change the schema or the model, you update this doc *first*,
then the SQL or the Python — it's the place engineers look
when reasoning about the model. *Schema spec.*
- `**docs/DEMO.md*`* — the demo data + walkthrough spec. What
users, topics (each with their default conversation), and
DMs the seed produces; what each agent's voice sounds like;
a step-by-step script for showing the app to someone. Pairs
with `examples/seed.py` (section 10): `seed.py` is the
*executable*, `DEMO.md` is the *readable*. Update `DEMO.md`
first when you change what's seeded. *Demo spec.*
- `**CLAUDE.md*`* (root) — project memory for AI coding tools
(Claude Code, Cursor, others read it). Lists the
architectural rules, the conventions, the run commands.
~30 lines. Lets every AI conversation start from the same
conventions instead of re-inferring them every session.
*Enforcement.*

Four audiences (humans-arriving, the model, the demo, AI tools),
four documents. None of them duplicates the others.

A starter `CLAUDE.md` for wazzup:

```markdown
# wazzup

Small chat app where humans and AI users share one model.
FastAPI + SQLite + Pydantic + pytest.

## Architectural rules

- `api/` is the only layer that touches SQL. SQL outside
  `api/` is a bug.
- Every named entity has `id`, `name`, `slug`. `slug` is
  `UNIQUE` per table; server-derived from `name` via
  `make_slug()` with collision suffix.
- Timestamps: UTC, ISO-8601 strings, server-set in `api/`.
  Never trust timestamps from the client.
- Use `deviation(msg, **kwargs)` for unexpected paths, NOT
  `log.warning(msg, id=...)` (raises `TypeError` — stdlib
  doesn't accept arbitrary kwargs; it needs `extra={...}`).
- Auth: `AUTH_DISABLED=1` in dev mode reads `X-User-Slug`
  header. Production auth lives in `require_auth` /
  `current_user`; not implemented yet.
- Soft-delete is the default; `delete(db, id, hard=True)` is
  admin-only.

## Run

- `uvicorn wazzup.http.main:app --port 8000` — API
- `python -m http.server 8001 -d ui/` — UI (separate process)
- `pytest` — tests; `STRICT_MODE=1 pytest` for the strict CI leg
- `ruff check .` — lint
- `python -m examples.seed` — seed canonical AI users

## See also

- `private/1-how to build simple applications.md` — full
  recipe
- `docs/MODEL.md` — entity model + invariants
- `.env.example` — required environment variables
```

`docs/MODEL.md` is the thinnest of the three — basically
section 2's table reproduced verbatim, plus a line per entity
listing its concrete columns, plus the cascade rules from
section 4 in list form. ~40 lines. Treat it as the contract;
when reality drifts from the doc, fix one or the other.

`README.md` is mostly about getting unstuck — quickstart,
how to install dependencies, how to run, how to test, what
env vars are required, where to read more. The `CLAUDE.md`
above is *not* a substitute (different audience, different
content); the README does not need architectural rules.

Update all four when the architecture changes. They're load-
bearing, not nice-to-have — and small enough that keeping them
in sync is cheap.

---

## What we haven't built (yet)

This recipe builds a small, working app. Several capabilities are
deliberately out of scope here, but become load-bearing the moment
lessons 2, 3, or the framework survey kick in. A punch list to keep
in your peripheral vision:

- **Real token issuance and password handling.** Section 8
establishes `require_auth` as a *pattern*; the JWT minting,
password hashing, and session/refresh flow it depends on aren't
implemented. Lesson 2 assumes the agent client already has a
token; lesson 3 assumes the MCP client does. Before either can
authenticate, you need a `/login` endpoint and the auth-token
plumbing.
- **Migrations / schema evolution.** `db.py` creates the schema
once, on startup. Any post-launch app needs Alembic (or
equivalent) for adding columns, evolving the `details` JSON
shape, running backfills. The default entity shape from
section 2 makes evolution easy; you still need a tool to drive
it. *Teaching-grade workaround in the meantime:* a small
`verify_schema()` step inside `init_schema()` that introspects
existing tables and raises a clear `SchemaMismatch` if columns
drifted from the expected set. It doesn't *migrate* — it just
catches the *"old DB on disk, new code"* failure loudly at
startup instead of letting `CREATE TABLE IF NOT EXISTS` silently
keep the wrong shape. Same *"no silent failures"* principle
from section 11, applied at the schema layer.
- **Health-check and readiness endpoints.** Required by every
load balancer, container orchestrator, and monitoring tool. A
two-line `GET /healthz` is enough — but you do need it before
the deployment story is real.
- **Rate limiting at the HTTP edge.** Mentioned in passing but
not implemented. Lesson 4's governance section treats it as a
deployment requirement, not an option.
- **Production observability.** Section 11 has stdout logging
via `deviation()`. Lesson 4 names the trace platforms
(Langfuse, LangSmith, etc.) you'd plug in. Until you do, you
are operating blind in production.
- **Async + connection pooling for non-SQLite databases.**
Section 8 describes the pattern (`get_db` checks out from a
pool); the recipe stays sync because SQLite is in-process.
Swap in Postgres and the pool, the async story, and the
transaction semantics all matter.
- **Background jobs / queues.** Anything heavier than a
synchronous request needs a worker (Celery, RQ, Arq). Out of
scope here; the moment the agent triggers a long-running
operation in lessons 2–3, it's on the table.

On top of the operational gaps above, the recipe doesn't yet
know about *agents*. Lessons 2–4 fill in two distinct roles
this app needs to play in an AI ecosystem — **provider** (your
API exposed to AI agents) and **consumer** (your code calling
other agents' tools):

- **Exposing the API to AI agents.** Lesson 1 gives you HTTP
endpoints humans and services can call. Agents need a
*curated* tool surface — a subset of operations, described in
plain English, with input schemas an LLM can fill. Lesson 2
builds this by hand (markdown catalog + custom client);
lesson 3 formalizes it via MCP.
- **The tool-calling loop.** Even with a curated surface in
place, you need the loop: ask the LLM, parse its tool calls,
dispatch them, feed results back, repeat until plain text.
Lesson 2 writes ~30 lines of it by hand; lesson 3 delegates
the loop to MCP-aware clients (Claude Desktop, LLM SDKs).
- **Agent observability and control tower.** What did the
agent actually do, where did it loop, how much did it cost,
and how do you turn it off in seconds? Section 11's
`deviation()` plus stdout logs aren't enough at agent scale —
you need trace platforms (Langfuse, LangSmith, Phoenix) and a
gateway-level kill switch. Lesson 4 surveys the landscape.
- **Reliable tool calling as a *consumer* of AI.** Calling
another agent's tools from inside your own workflow needs
retries with backoff, provider fallback, schema validation,
cost tracking, and a structured way to surface errors back to
the caller. Lesson 4's framework survey covers the
abstractions; lesson 3's MCP client is the wire-protocol layer
underneath.

None of these change the architecture lesson 1 teaches. The
operational items are the difference between *"this works on my
machine"* and *"this is hardened for users"*. The agent items
are the difference between *"a service for humans"* and *"a
service that participates in an AI ecosystem."* Both layers sit
on top of the recipe; neither requires changing it.

---

## Suggested order of work

1. Schema + `db.py`. Run a migration; eyeball with the `sqlite3` CLI.
2. The API layer for **one** entity (`user`) — the five operations
  plus query. Test it from a Python REPL.
3. Pydantic models + one FastAPI route. Hit it with `curl`.
4. Repeat for the other entities — copy-paste, then refactor.
5. The rels table + `rels.py`.
6. Cascade deletion, in `deletion.py` only.
7. Logging — including `deviation()` and `STRICT_MODE` (section 11).
8. `tests.md` → `pytest`.
9. `examples/`.
10. Tooling: ruff, `pytest -W error`, branch coverage, optional mypy
  (section 12). Wire all of them into CI before the first PR
    merges, so they protect every change after this one.

Stop at any step that feels unclear and tighten it before moving on.
The whole point of this recipe is that each layer hides the one below
— if a layer leaks, fix that before adding the next.

**If an AI is building this for you**, the natural review pauses are
after step 2 (eyeball the schema with `sqlite3` before any code
depends on it) and after step 5 (drive the rels API from a REPL and
make sure it feels right). Everything above those two layers gets
cheap once they're solid; everything above them gets expensive if
they're wrong.

---

## Where this leads

You now have a small app with one durable internal Python API
(section 6) and one surface exposed by hand over HTTP (section 8).
The next lesson keeps every file in this recipe and adds *one more
file* — an MCP server — that re-exposes the same internal API to LLM
agents as typed tools. You won't rewrite any business logic; you'll
just publish it through a second door. That only works because of
the discipline of section 6.