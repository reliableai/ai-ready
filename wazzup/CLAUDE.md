# wazzup

Small chat app where humans and AI users share one model. FastAPI + SQLite + Pydantic + pytest. Reference implementation of `private/1-how to build simple applications.md`.

## Architectural rules

- `api/` is the only layer that touches SQL. SQL outside `api/` is a bug.
- Every named entity has `id`, `name`, `slug`. `slug` is `UNIQUE` per table; server-derived from `name` via `make_slug()` with collision suffix. `id` is the internal FK target; `slug` is the public address.
- `message` is the named exception: it has no `name` or `slug` (transient, addressed by id).
- Timestamps: UTC, ISO-8601 strings (`datetime.now(UTC).isoformat()`), server-set in `api/`. Never trust timestamps from the client.
- Use `deviation(msg, **kwargs)` (from `wazzup/logging_setup.py`) for unexpected paths, NOT `log.warning(msg, id=...)` — stdlib doesn't accept arbitrary kwargs (raises `TypeError`); it needs `extra={...}`. The `deviation()` helper translates kwargs to `extra` internally.
- Auth: `AUTH_DISABLED=1` in dev mode; `require_auth` reads `X-User-Slug` header instead of a token. Real token issuance is intentionally not implemented yet.
- Soft-delete is the default (`deleted_at` set; reads filter it out). `delete(db, id, hard=True)` is admin-only.
- Cascade rules for soft-delete live in `api/deletion.py`, one source of truth.
- Two types of `user`: `'human'` and `'agent'`. Same table, same auth, same conversations. `agent` users have a `persona` field (markdown) loaded as the system prompt when they compose messages via `llm.call()`.
- **Every link lives in `rels`** — including `message → conversation` and `message → user`. `message` has no direct FK columns. This is the teaching-grade choice (section 3 of the lesson); production hot paths sometimes promote frequent rels to dedicated FK columns, but that's an explicit denormalization, not the default.
- **Two user-facing concepts: `user` and `topic`.** `conversation` is internal plumbing — never user-visible. Each topic owns exactly one default conversation auto-created by `topics.create()` (linked via `rel_type='in_topic'`). DMs are conversations with exactly two `participates_in` user rels and no `in_topic` rel. The only public entry points that produce conversations are `topics.create()` and `conversations.get_or_create_dm()`; `conversations._create()` is module-private. Don't add a public `conversations.create()` route or expose a "create-conversation" UI.
- **Topics are public for v0.1.** No membership enforcement. The `member_of` rel is reserved for future private/group topics. Every topic read/write path goes through `topics.can_access(db, *, user_id, topic_id)` (returns `True` today); future enforcement = single function-body change.
- **`TopicRead.default_conversation_slug` is non-Optional.** Every topic has a default conversation by construction. If the rel is missing at read time, that's an invariant violation — call `deviation()`, don't soften the type to `str | None`.
- **Authorize at the route boundary, not in api/.** Every HTTP route that reads or writes messages of a conversation must call `conversations.is_accessible_by(db, *, conversation_id=..., user_id=current_user.id)` after resolving the conversation, and return 403 on deny. Topic-default conversations gate through `topics.can_access` (today: always True); DMs require a live `participates_in` rel. The api-layer helper answers the *structural* question (is this user a participant / member); the http layer ties it to the authenticated caller. Don't push the auth check into `api/` — but don't duplicate the structural query at every route either; one helper, called at every entry point.
- **Agent replies dispatch from one place.** `api/agents.respond_to_human_message()` is the *only* public entry that produces agent reply messages, called from `POST /messages` after the human's message commits. Loop guard: only `type='human'` posts trigger; agent posts never. The dispatcher is the single edit point for any future scoping (private topics, @mentions, per-topic agent rosters). Don't scatter "agent should respond here" logic across routes.
- **`POST /messages` explicitly commits the human's message before dispatching agent replies.** This is a *deliberate* exception to the "caller owns transaction" rule. Without it, a strict-mode `deviation()` in the agent loop would unwind the human's message via `get_db`'s rollback path. Each successful agent reply also commits before the next agent runs, so prior successes survive a downstream failure. If you add another multi-step write that needs the same durability shape, follow the same pattern and document it; otherwise leave the wrapper to handle commits.
- **`mcp/` is a thin adapter over `api/`, parallel to `http/`.** Each `@mcp.tool()` is a wrapper that opens a fresh DB connection (the `_db()` context manager mirrors `http/dependencies.py:get_db`), calls one or two `wazzup.api.*` functions, and returns the result. The api layer doesn't know MCP exists; the MCP layer doesn't reimplement business logic. Curation is by *which functions get a `@mcp.tool()` decorator* — destructive ops (clear chat, hard delete, anything irreversible) deliberately stay off the surface. Auth is intentionally absent in v0.3 (binds to 127.0.0.1, write tools take `as_user_slug` so the caller picks identity); production swaps that for OAuth at the transport.

## Testing conventions

- Default fixture is `db` (fresh in-memory SQLite, production schema). Use `client` for HTTP-level tests.
- For schema-level instrumentation (audit triggers, extra indexes, relaxed constraints), use `db_factory(extra_sql=[...])`. Don't modify `init_schema` for test-only needs — production code shouldn't know about test variations.
- Tests that deliberately exercise a `deviation()` use `pytest.raises(UnexpectedDeviation)` and only meaningfully pass under `STRICT_MODE=1`. CI runs both legs.

## Error conventions

| Operation | Not found | Conflict | HTTP layer maps to |
|---|---|---|---|
| `get` / `get_by_slug` | returns `None` | n/a | 404 if `None` |
| `query` | returns `[]` | n/a | 200 with empty list |
| `create` | n/a | raises `IntegrityError` | 409 |
| `update` | raises `NotFound` | raises `IntegrityError` | 404 / 409 |
| `delete` | raises `NotFound` | n/a | 404 |

`NotFound` is a custom exception declared in `wazzup/api/__init__.py`. FastAPI catches both `NotFound` and `IntegrityError` once via `@app.exception_handler` and translates to `HTTPException(404)` / `(409)`.

## Run

- `uvicorn wazzup.http.main:app --port 8000` — API
- `python -m http.server 8001 -d ui/` — UI (separate process)
- `pytest` — tests
- `STRICT_MODE=1 pytest` — strict CI leg; tests that deliberately exercise deviations should `pytest.raises(UnexpectedDeviation)`
- `ruff check .` — lint
- `python -m examples.seed` — seed canonical AI users

## See also

- `../private/1-how to build simple applications.md` — the full recipe
- `docs/MODEL.md` — entity model + invariants (schema spec)
- `docs/DEMO.md` — seeded demo data + walkthrough (demo spec)
- `TODO.md` — current progress and next implementation step
- `.env.example` — required environment variables
