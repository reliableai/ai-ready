# tests.md — behavior spec

Per section 9 of the lesson: write the behavior spec *before* the test code. One section per endpoint, then one happy-path E2E at the bottom.

For each endpoint document:

- **Endpoint** — verb + path
- **Request** — a valid example body
- **Expected** — status code, response body shape, DB side effects
- **Errors** — what counts as 400 / 404 / 409 / 422; one example each
- **Soft-delete behavior** — does the deleted entity show up in `get`? in `query`? in `rels.list`?

Then translate each entry into a `pytest` function in `test_<entity>.py`.

## Conventions

- **Default fixture is `db`** — fresh in-memory SQLite, production schema. Use `client` for HTTP-level tests (FastAPI `TestClient` with `dependency_overrides[get_db]` set).
- **Schema-level instrumentation** — for tests that need an audit trigger, extra index, or relaxed constraint, use `db_factory(extra_sql=[...])`. Pattern documented in the section below; never modify `wazzup/db.py:init_schema` for test-only needs.
- **Tests that deliberately exercise a deviation** (`deviation()` in `wazzup/logging_setup.py`) should use `pytest.raises(UnexpectedDeviation, match="...")` and only meaningfully pass under `STRICT_MODE=1`. CI runs both legs (strict and non-strict); tests of this shape pass in the strict leg, no-op in the other.
- **SQLite `ALTER TABLE` is limited** — you can `ADD` columns but can't drop or change constraints without rebuilding. If a test needs to relax a constraint, `DROP TABLE x; CREATE TABLE x (...)` with the alternative shape; `db_factory(extra_sql=...)` supports it.

## Schema-level instrumentation

Most tests use the default `db` fixture — a fresh in-memory connection with the production schema, nothing extra. But some tests need *more*: an audit trigger to verify a side effect happened, an additional index to verify a query plan, or a relaxed constraint to set up a state the production schema would forbid.

The wrong move is adding a `test_mode=True` knob to `wazzup/db.py:init_schema`. Production code shouldn't know that tests exist. The right move is `db_factory(extra_sql=[...])`: it builds a fresh connection, runs the production schema unchanged, then layers your extra SQL on top — your test gets prod-shape *plus* whatever it needs.

Three canonical use cases:

1. **Audit trigger — verify a side effect happened.** Cascade deletion should soft-delete every rel touching a deleted user. Asserting that by `SELECT`ing on `rels` directly means your test and the production code both read the same column the same way — a regression that flips both at once would slip by. An audit-table side channel catches it:

   ```python
   def test_user_delete_cascades_to_rels(db_factory):
       db = db_factory(extra_sql=[
           "CREATE TABLE _audit (op TEXT, tbl TEXT, row_id INTEGER, ts TEXT)",
           "CREATE TRIGGER rels_audit AFTER UPDATE ON rels "
           "BEGIN INSERT INTO _audit VALUES "
           "  ('update', 'rels', NEW.id, datetime('now')); END",
       ])
       # ... create user, add two rels, users.delete(db, user_id) ...
       touched = db.execute(
           "SELECT row_id FROM _audit WHERE op='update'"
       ).fetchall()
       assert len(touched) == 2
   ```

2. **Extra index — verify a query plan.** Hot read paths should hit an index, not a table scan. Asserting that requires `EXPLAIN QUERY PLAN`. If you're considering adding an index to production, compose it in via `extra_sql` first and check the plan changes; promote to `init_schema` only once the test confirms the effect.

3. **Relaxed constraint — exercise a forbidden state.** What does `users.get_by_slug` do if two live rows somehow share a slug? In production this can't happen — the partial UNIQUE index forbids it — but you want to confirm your read code degrades gracefully if it ever does. SQLite has no `DROP CONSTRAINT`, so the recipe is `DROP TABLE user; CREATE TABLE user (...)` without the UNIQUE; `db_factory(extra_sql=[...])` takes that pair as a test-only schema reset (see the SQLite `ALTER TABLE` note above).

The principle: production code doesn't know that tests want extra tables, indexes, or relaxed constraints. Tests compose what they need on top of the canonical schema. The day an audit trigger or extra index becomes valuable in prod, you promote it to `init_schema` — until then it lives in the test that needs it.

## users (POST/GET/list — PATCH/DELETE pending)

### `POST /users`
- **Auth**: required (router-level `Depends(require_auth)`).
- **Request**: `UserCreate` JSON.
  ```json
  {"name": "Bob", "type": "human"}
  ```
- **Success**: `201 Created` + `UserRead` JSON. Side effect: one new row in `user`. `slug` is server-derived (`make_slug(name)`); collisions silently suffix (`-2`, `-3`, …) — see TODO #19.
- **Errors**:
  - `422` — invalid body (Pydantic). E.g., missing `name`, `type` not in `{human, agent}`, `name` empty (min_length=1).
  - `401` — missing `X-User-Slug` header in dev mode.
  - `409` — slug-collision race after retry exhaustion (rare; surfaces via `IntegrityError` exception handler).
- **Soft-delete behavior**: N/A (creation only).

### `GET /users/{slug}`
- **Auth**: required.
- **Path param**: `slug` — any string; not regex-validated at the route level.
- **Success**: `200 OK` + `UserRead` JSON.
- **Errors**:
  - `404` — no live user with that slug. Body: `{"detail": "user slug='nope' not found"}`. Soft-deleted users are 404 too.
  - `401` — missing `X-User-Slug` in dev mode.
- **Soft-delete behavior**: soft-deleted users return 404, same as never-existed. The row is still in the DB (`deleted_at IS NOT NULL`), just hidden from reads.

### `GET /users` (#21)
- **Auth**: required.
- **Query params**: `type` (optional, `human` or `agent`), `limit` (1..200, default 50), `offset` (≥0, default 0). Pagination bounds enforced via `Query(ge=…, le=…)` — out-of-range values return `422`.
- **Success**: `200 OK` + JSON array of `UserRead`. Empty array when nothing matches; never `404`.
- **Errors**: `401` — missing `X-User-Slug`. (Invalid `type` values fall through silently — the api layer accepts any string and returns no rows; tightening this is a follow-up if it bites.)
- **Soft-delete behavior**: soft-deleted users are excluded. There's no `include_deleted` flag — a separate audit endpoint would be the right place if that's ever needed.

## conversations (one route only — internal plumbing)

In v0.2, conversations are not user-facing. The only HTTP route is the messages-list endpoint the UI's chat view hits. `POST /conversations`, `GET /conversations`, and `GET /conversations/{slug}` were deleted with the boundary refactor — `topics.create()` and `conversations.get_or_create_dm()` are the only public producers of conversations.

### `GET /conversations/{slug}/messages` (#21)
- **Auth**: required.
- **Path param**: `slug` — the conversation's slug. Resolves to a `conversation_id` via `conversations.get_by_slug` before querying messages.
- **Query params**: `limit` (1..200, default 20 — smaller than entity-list 50; messages are higher-volume), `offset` (≥0, default 0). Same `Query(ge=…, le=…)` bounds as the other list routes.
- **Access control**: after slug resolution, the route calls `conversations.is_accessible_by(db, conversation_id=conv.id, user_id=current_user.id)`. Topic-default conversations gate through `topics.can_access` (today: always True, since v0.1 topics are public). DMs require the caller to be one of the two `participates_in` users. Non-participant on a DM → **403** (not 404 — the conversation's existence isn't secret; its contents are).
- **Success**: `200 OK` + JSON array of `MessageRead`, ordered by id (oldest first).
- **Errors**:
  - `404` — no live conversation with that slug. Body: `{"detail": "conversation slug='nope' not found"}`.
  - `403` — caller is not a participant in the DM (or, when private topics ship, not a member of the topic). Body: `{"detail": "not a participant of this conversation"}`.
  - `401` — missing `X-User-Slug`.
- **Soft-delete behavior**: soft-deleted messages are excluded; soft-deleted conversation → 404 (looks the same as a typo). The query JOINs through rels filtering `deleted_at IS NULL` on both sides, so a soft-deleted `belongs_to` rel also hides its message from this view. **This is the route the UI's chat view hits.**

## topics (POST/GET/list — PATCH/DELETE pending)

### `POST /topics`
- **Auth**: required.
- **Request**: `TopicCreate` JSON.
  ```json
  {"name": "Engineering"}
  ```
- **Success**: `201 Created` + `TopicRead` JSON. Slug derived from `name`. Response includes `default_conversation_id` and `default_conversation_slug` — `topics.create()` writes the topic, the conversation, and the `in_topic` rel in the same transaction.
- **Errors**:
  - `422` — invalid body (`name` missing or empty).
  - `401` — missing `X-User-Slug` in dev mode.
  - `409` — slug-collision race after retry exhaustion.
- **Soft-delete behavior**: N/A (creation only).

### `GET /topics/{slug}`
- **Auth**: required.
- **Success**: `200 OK` + `TopicRead` JSON, including `default_conversation_id` + `default_conversation_slug`.
- **Errors**: `404` on miss, `401` on missing auth header.
- **Soft-delete behavior**: 404 for soft-deleted topics. Topic cascade (per `api/deletion.py`) soft-deletes the `in_topic` and `member_of` rels AND recursively cascades to the topic's default conversation (which itself cascades to its messages and rels).

### `GET /topics` (#21)
- **Auth**: required.
- **Query params**: `limit` (1..200, default 50), `offset` (≥0, default 0). Bounds enforced via `Query(ge=…, le=…)` — out-of-range values return `422`.
- **Success**: `200 OK` + JSON array of `TopicRead`. Each row carries its `default_conversation_id` and `default_conversation_slug`.
- **Errors**: `401` — missing `X-User-Slug`.
- **Soft-delete behavior**: soft-deleted topics excluded.

## DMs

### `POST /dms/{peer_slug}`
- **Auth**: required.
- **Path param**: `peer_slug` — the slug of the user the caller wants to DM.
- **Success**: `200 OK` + `ConversationRead` JSON. Idempotent: same caller + same peer = same conversation. The slug uses alphabetical user-slug ordering (`dm-alice-curie`, never `dm-curie-alice`); the helper finds the existing conversation regardless of argument order.
- **Errors**:
  - `404` — no live user with that slug. Body: `{"detail": "user slug='nope' not found"}`.
  - `400` — `peer_slug` matches the authenticated caller's slug. Body: `{"detail": "cannot DM yourself"}`.
  - `401` — missing `X-User-Slug` in dev mode.
- **Soft-delete behavior**: a soft-deleted DM is treated as not-found by the lookup; a subsequent call creates a fresh DM (with new id and rels). This matches the rest of the soft-delete + reuse pattern.

## messages (POST/GET-by-id; list lives at `GET /conversations/{slug}/messages`; PATCH/DELETE pending)

### `POST /messages`
- **Auth**: required.
- **Request body**: **`MessageCreateRequest`** (NOT `MessageCreate`). The HTTP body shape is route-local in `http/messages.py` and intentionally OMITS `sender_id` — the route fills it from `current_user`. See the docstring in `http/messages.py` for the rationale (and `models.py` MessageRead decision for the symmetric pattern).
  ```json
  {"conversation_id": 1, "text": "shipping the auth fix today"}
  ```
- **Access control**: after validating `conversation_id` exists, the route calls `conversations.is_accessible_by(...)` with the caller's id. Non-participant on a DM → **403**. (Without this check, any authenticated user could *write* into anyone's DM by guessing the conversation id — symmetric to the read break.)
- **Success**: `201 Created` + `MessageRead` JSON. Side effects: one row in `message`, two rows in `rels` (`belongs_to → conversation`, `sent_by → user`). `MessageRead` is stored-columns-only — no `conversation_id` / `sender_id` (those live in rels). Routes that need to surface them in their response shape should JOIN.
- **Errors**:
  - `422` — invalid body (missing `conversation_id`, missing `text`, empty `text`).
  - `401` — missing `X-User-Slug`.
  - `403` — caller is not a participant in the DM identified by `conversation_id`.
  - `404` — `conversation_id` doesn't match a live conversation. Body: `{"detail": "conversation_id=999 not found"}`. The api validates FK existence before insert (no DB-level FK because rels is polymorphic).
- **Soft-delete behavior**: N/A (creation only).

### `GET /messages/{id}`
- **Auth**: required.
- **Path param**: `id` typed as `int` — non-numeric returns `422` (FastAPI path parsing).
- **Access control**: after resolving the message, the route looks up its `belongs_to` conversation via the rel, then calls `conversations.is_accessible_by(...)` with the caller's id. Non-participant on a DM → **403**.
- **Success**: `200 OK` + `MessageRead` JSON.
- **Errors**:
  - `404` — no live message with that id.
  - `403` — caller is not a participant in the message's conversation (DM).
  - `401` — missing `X-User-Slug`.
- **Soft-delete behavior**: soft-deleted messages return 404. Cascade via conversation deletion (or direct `messages.delete`) soft-deletes the message and its two rels.

### `GET /messages` (#21)
- **Auth**: required.
- **Query params**:
  - `conversation_id` — **required**; integer. No "all messages" fallthrough — see `api/messages.query` docstring for the rationale.
  - `sender_id` — optional; integer. Filters within the conversation.
  - `limit` (1..200, default 20), `offset` (≥0, default 0). Same `Query(ge=…, le=…)` bounds as the other list routes.
- **Access control**: same rule as `GET /conversations/{slug}/messages` — caller must pass `conversations.is_accessible_by(...)`. Non-participant on a DM → **403**.
- **Success**: `200 OK` + JSON array of `MessageRead`. Empty array on no match.
- **Errors**:
  - `422` — `conversation_id` missing or non-integer; `limit`/`offset` out of bounds.
  - `403` — caller is not a participant.
  - `404` — `conversation_id` doesn't match a live conversation.
  - `401` — missing `X-User-Slug`.
- **Soft-delete behavior**: soft-deleted messages excluded; soft-deleted `belongs_to` rels also hide their message (cascade). Unlike previous behavior, a typo'd `conversation_id` now returns `404` rather than `[]` — the access check forces existence resolution. (The nested-route variant has always 404'd on miss; this aligns the two.)
- **Same data as** `GET /conversations/{slug}/messages` — both call `messages_api.query` after the same access check. The nested route resolves a slug; this one takes the id directly. Use the nested one when you have a slug, this one when you have an id.

## rels (no HTTP routes — api-only)

The api layer (`wazzup.api.rels`) has `add` / `remove` / `list` operations, but no HTTP routes are mounted in `http/main.py`. Membership and participation rels are written from inside other routes today (e.g., `messages.create` writes the `belongs_to` and `sent_by` rels via `rels.add`). #21's listing endpoints landed only for the named entities (users, conversations, topics, messages-in-conversation); dedicated rels routes (e.g., `POST /topics/{slug}/members`, `GET /topics/{slug}/members`) are deferred — when they land, they'll follow the same protected-router pattern with kw-only bodies mirroring the api signatures.

## auth (no HTTP routes yet — login is "what we haven't built")

The `http/auth.py` router exists and is mounted at `/auth`, but it has no routes — it's the *one* router declared without `dependencies=[Depends(require_auth)]` so future public routes (`POST /auth/login`, `POST /auth/refresh`) can live there without opting out of auth route-by-route. Real auth is explicitly out of scope; in dev mode (`AUTH_DISABLED=1`), the `X-User-Slug` header is the identity.

## e2e

End-to-end test in `tests/test_e2e.py` exercises the full critical path at the api layer. An HTTP-level variant is now possible (post-#21) but not yet written — it would seed via POST routes, list via the new GET-list routes, and verify cascade by re-listing after a soft-delete:

- seed 4 users (2 humans, 2 agents)
- create a topic, add all 4 users as members
- create a conversation in the topic, add all 4 as participants
- exchange 4 messages (one per user)
- soft-delete one human user

Assertions (all per the cascade rules in `api/deletion.py`):
- the deleted user's `get` / `get_by_slug` return None
- their `member_of`, `participates_in`, and `sent_by` rels are all soft-deleted
- the messages they sent **still exist** (cascade doesn't go user → message; only conversation → message)
- the other 3 users, the topic, and the conversation are unaffected

## TODO

- [x] users (#10)
- [x] conversations (#15)
- [x] topics (#15)
- [x] messages (#15)
- [x] rels — note added (no HTTP routes yet, see #21)
- [x] auth — note added (no real routes; login is OOS)
- [x] e2e — `test_e2e.py` covers the api-level flow; HTTP-level variant lands with #21
