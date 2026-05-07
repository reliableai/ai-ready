# wazzup — entity model and invariants

The conceptual model as a spec. Section 1 of the lesson is the narrative; this is the column-by-column reference. When you change the schema, you update this doc *first*, then the SQL.

## Entities

Four named entities + one rels table. Every named entity has the same default shape (section 2 of the lesson): `id`, `name`, `slug`, `created_at`, `updated_at`, `deleted_at`, *indexed cols*, `details` (JSON).

### `user`

Anyone who talks. Humans and AI agents both live here.

| Column       | Type         | Notes                                                              |
| ------------ | ------------ | ------------------------------------------------------------------ |
| `id`         | INTEGER PK   | auto-increment                                                     |
| `name`       | TEXT NOT NULL| display name; not unique                                           |
| `slug`       | TEXT NOT NULL| unique among LIVE rows (partial unique index `WHERE deleted_at IS NULL`); `alice-smith`, `trump` |
| `type`       | TEXT NOT NULL| `'human'` or `'agent'`                                             |
| `persona`    | TEXT         | markdown; agent voice; loaded as system prompt for `llm.call()`    |
| `created_at` | TEXT NOT NULL| ISO-8601 UTC                                                       |
| `updated_at` | TEXT NOT NULL| ISO-8601 UTC                                                       |
| `deleted_at` | TEXT         | NULL = alive; non-NULL = soft-deleted                              |
| `details`    | TEXT         | JSON blob (`UserDetails` shape: `bio`, `timezone`, etc.)           |

### `topic`

A public chat room. The user-facing surface of the app: users either DM each other or post on a topic — those are the only two ways to talk.

Each topic owns exactly one default `conversation`, auto-created by `topics.create()` in the same transaction. Posting "on a topic" means writing into that conversation. Topics are public for v0.1 — anyone reads, anyone writes. See *Deliberate gaps* below for the access-control plan.

| Column       | Type         | Notes                                                              |
| ------------ | ------------ | ------------------------------------------------------------------ |
| `id`         | INTEGER PK   |                                                                    |
| `name`       | TEXT NOT NULL|                                                                    |
| `slug`       | TEXT NOT NULL| unique among LIVE rows (partial unique index); `engineering`, `random` |
| `created_at` | TEXT NOT NULL| ISO-8601 UTC                                                       |
| `updated_at` | TEXT NOT NULL| ISO-8601 UTC                                                       |
| `deleted_at` | TEXT         |                                                                    |
| `details`    | TEXT         | JSON                                                               |

### `conversation`

Internal plumbing for messages. **Not user-facing** — the UI never shows the word "conversation". Two valid shapes, enforced by *boundary*: the only public entry points that create conversations are `topics.create()` (creates a topic-default) and `conversations.get_or_create_dm()` (creates a DM). The low-level `conversations._create()` is module-private.

- **Topic-default**: linked to one topic via a `rel_type='in_topic'` rel. Auto-created when the topic is created. Cascades when its topic is soft-deleted.
- **DM**: a conversation with exactly two distinct `user participates_in conversation` rels and **no** `in_topic` rel. Found-or-created by `get_or_create_dm(user_a_id, user_b_id)` — idempotent regardless of argument order.

| Column       | Type         | Notes                                                              |
| ------------ | ------------ | ------------------------------------------------------------------ |
| `id`         | INTEGER PK   |                                                                    |
| `name`       | TEXT NOT NULL| display name (`"Daily Standup"`, `"Alice Smith ↔ Marie Curie"`)    |
| `slug`       | TEXT NOT NULL| unique among LIVE rows (partial unique index); `daily-standup`, `dm-alice-curie` |
| `created_at` | TEXT NOT NULL| ISO-8601 UTC                                                       |
| `updated_at` | TEXT NOT NULL| ISO-8601 UTC                                                       |
| `deleted_at` | TEXT         |                                                                    |
| `details`    | TEXT         | JSON                                                               |

### `message`

A single utterance in a conversation. *Exception to the named-entity shape — no `name`, no `slug`.*

| Column       | Type          | Notes        |
| ------------ | ------------- | ------------ |
| `id`         | INTEGER PK    |              |
| `text`       | TEXT NOT NULL | message body |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC |
| `updated_at` | TEXT NOT NULL | ISO-8601 UTC |
| `deleted_at` | TEXT          |              |
| `details`    | TEXT          | JSON         |

**No direct `conversation_id` / `sender_id` FK columns.** Per the teaching design (section 3 of the lesson), *every* link between entities lives in the `rels` table, including `message → conversation` and `message → user`. Creating a message writes one row in `message` plus two rows in `rels` (one `belongs_to` rel, one `sent_by` rel). Reading a conversation's messages joins through `rels`. We pay the join cost in exchange for one rule to remember: *all links live in rels*.

This is the *teaching* choice. Production hot paths often promote frequent rels to dedicated indexed FK columns to avoid the join — that's a deliberate denormalization, not the default. If you make that change later, update this doc *first* so the invariant *"all links in rels"* doesn't silently break.

### `rels`

Single polymorphic relationships table for everything that links entities together (section 3 of the lesson).

| Column       | Type         | Notes                                                              |
| ------------ | ------------ | ------------------------------------------------------------------ |
| `id`         | INTEGER PK   |                                                                    |
| `src_id`     | INTEGER NOT NULL | source entity id                                               |
| `src_type`   | TEXT NOT NULL| source table name (`'user'`, `'conversation'`, …)                  |
| `tgt_id`     | INTEGER NOT NULL| target entity id                                                |
| `tgt_type`   | TEXT NOT NULL| target table name                                                  |
| `rel_type`   | TEXT NOT NULL| `'member_of'`, `'participates_in'`, …                              |
| `details`    | TEXT         | JSON (e.g., role, joined_at metadata)                              |
| `created_at` | TEXT NOT NULL| ISO-8601 UTC                                                       |
| `deleted_at` | TEXT         |                                                                    |

Indexes on `(src_type, src_id)`, `(tgt_type, tgt_id)`, `(rel_type)` for traversal.

## Relationship types

- `conversation in_topic topic` — conversation is the default conversation for a topic. Written by `topics.create()` alongside the conversation row. Exactly one per topic. Topic-default detection rule.
- `user participates_in conversation` — user is in a conversation. For DMs: exactly two distinct rels per conversation, with no `in_topic` rel — that pair is the DM-detection rule.
- `message belongs_to conversation` — message is part of a conversation. Written by `messages.create()` alongside the message row.
- `message sent_by user` — message was authored by a user. Written by `messages.create()` alongside the message row.
- `user member_of topic` — *reserved for future private/group topics*; not written or checked today. v0.1 topics are public.

(Add new `rel_type` values as the product grows; no schema change required.)

## Invariants

1. **`slug` is unique among live rows, per table.** DB-enforced via a partial unique index (`CREATE UNIQUE INDEX … WHERE deleted_at IS NULL`). Soft-deleted slugs are reusable — when alice is soft-deleted, a new alice can be created. The `make_slug` helper handles friendly suffix-on-collision; the partial unique index is the race-safety net.
2. **Timestamps are UTC, ISO-8601, server-set.** Never trust timestamps from the client. Set in `api/` at create / update / soft-delete time.
3. **Soft-delete is the default.** `deleted_at` is set; reads filter `WHERE deleted_at IS NULL`. `delete(db, id, hard=True)` is admin-only and bypasses the soft path.
4. **`api/` is the only layer that touches SQL.** Both `http/` and `mcp/` (lesson 3) sit on top of it. SQL anywhere else is a bug.
5. **`user.type` is exactly `'human'` or `'agent'`.** Enforced at the Pydantic layer (`Literal["human", "agent"]`) and ideally with a `CHECK` constraint at the schema level.
6. **Every conversation is either a topic-default or a DM.** Topic-default = exactly one `in_topic` rel pointing at a topic. DM = exactly two distinct `participates_in` rels with no third participant and no `in_topic` rel. There are no free-floating conversations. Enforced by *boundary*: `conversations._create()` is module-private; only `topics.create()` and `conversations.get_or_create_dm()` can produce a conversation. No runtime read-time validator — the boundary is the contract.
7. **Every topic has a default conversation.** `TopicRead.default_conversation_slug` is non-Optional. If the rel is missing at read time, `topics.get*()` calls `deviation("topic missing default conversation", topic_id=...)`; in strict mode this raises, in lax mode it surfaces a `<missing>` sentinel so the UI looks broken loudly.
8. **Conversation access is structural.** A user may read or write a conversation iff:
   - the conversation is a **topic-default** (has an `in_topic` rel) AND `topics.can_access(db, user_id=..., topic_id=...)` returns `True`. v0.1 topics are public, so the gate is open today; the hook is the single edit point for future private/group topics.
   - the conversation is a **DM** AND the user has a live `participates_in` rel pointing at it.
   Any other shape (no `in_topic`, no participation) is denied. The rule is encoded in `api.conversations.is_accessible_by(db, *, conversation_id, user_id)` and called from every HTTP route that addresses a conversation (read or write). The api layer answers the *structural* question; the http layer ties it to the authenticated caller. Returns **403** on deny — the conversation's existence is not concealed (the slug is enumerable via other surfaces), but its contents are.

## Cascade rules

When an entity is soft-deleted, the rels touching it are soft-deleted too. Implemented in `api/deletion.py` (one source of truth).

| Soft-delete on | Cascades to |
| -------------- | ----------- |
| `user`         | rels where `src='user' OR tgt='user'`. *Product decision pending: whether to also nuke / anonymize their `message` rows.* |
| `conversation` | all `message` rows for that conversation; all rels touching the conversation. |
| `topic`        | rels where `src='topic' OR tgt='topic'`, **plus** the topic's default conversation linked via `in_topic` (which then recursively cascades to its messages and their rels per the conversation rule). |
| `message`      | rels touching the message (rare). |

Hard-delete cascades follow the same shape but actually remove the rows.

## Identifiers

- `id`: internal, integer, FK target, opaque, stable.
- `slug`: public, string, URL-friendly, derived from `name` at create time, immutable once written.

URLs and agent prompts use slugs (`/users/alice`, `/topics/daily-standup`); internal joins use ids.

## Deliberate gaps

Things the v0.1 model knowingly omits, with the bridge for when they're needed:

- **Topic visibility.** All topics are public. Future work: add a `topic.visibility` column (`'public' | 'group' | 'private'`) and gate read/write through `topics.can_access(db, *, user_id, topic_id) -> bool`. The hook exists today as a `True`-returning stub so call sites are already wired; flipping it on means one function-body change. The `member_of` rel_type is reserved for the per-user membership rows that private/group topics will write.
- **Group DMs.** The DM-detection rule is exactly-2-users. A 3+ user conversation with no `in_topic` rel is currently undefined. Bridge: when group DMs ship, either relax the rule (any-N-users, no-topic) or introduce a `kind` column. Don't decide pre-emptively.
- **Real auth.** `AUTH_DISABLED=1` + `X-User-Slug` is the dev shortcut. Real token issuance is intentionally not wired yet.
