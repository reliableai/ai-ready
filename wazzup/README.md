# wazzup

<!--
Once this repo is pushed to GitHub, replace <org>/<repo> with the actual
path and uncomment the badge below. The workflow file at
../.github/workflows/ci.yml is already wired up.

![CI](https://github.com/<org>/<repo>/actions/workflows/ci.yml/badge.svg)
-->

Small chat app where humans and AI users share one model. The same `user` table holds both; a `type` field (`'human'` or `'agent'`) and a markdown `persona` field are what set them apart. AI users compose their replies via an LLM call; everything else is the same code path.

This repo is the reference implementation of the recipe in [`private/1-how to build simple applications.md`](../private/1-how%20to%20build%20simple%20applications.md). The lesson is the source of truth for *why*; this repo is the source of truth for *how*.

## Quickstart

We use [`uv`](https://docs.astral.sh/uv/) for venv + dependency management. Install it first if you haven't (`brew install uv` on macOS, see uv docs otherwise).

```bash
# 1. create the venv (in .venv/)
uv venv

# 2. activate it — REQUIRED in every new terminal you run wazzup from
source .venv/bin/activate
# (zsh/bash on macOS or Linux. On Windows: .venv\Scripts\activate)

# 3. install wazzup + dev tools (pytest, ruff, …)
uv pip install -e '.[dev]'

# 4. configure
cp .env.example .env
# ... edit .env, fill in LLM_API_KEY at minimum
```

**Reactivate in every new terminal.** The `source .venv/bin/activate` line above is per-shell — if you open a second terminal to run the UI alongside the API, you have to activate again there. Forgetting this is the most common "command not found" / "module not found" pitfall. Alternative: prefix any one-shot command with `uv run` (e.g. `uv run pytest`), which auto-uses the venv without activation.

Run the API and UI as two long-running processes (each in its own activated terminal):

```bash
# API on :8000 (terminal 1)
WAZZUP_INIT_SCHEMA=1 AUTH_DISABLED=1 uvicorn wazzup.http.main:app --reload --port 8000

# UI on :8001 (terminal 2 — re-activate the venv first)
python -m http.server 8001 -d ui/

# Browser: http://localhost:8001
```

`WAZZUP_INIT_SCHEMA=1` makes the API run `init_schema()` at startup so a fresh database is set up automatically. `AUTH_DISABLED=1` enables the dev-mode `X-User-Slug` header (no real login). Both are dev-only knobs; production sets neither.

## Tasks

All assume the venv is activated (or prefix with `uv run`).

```bash
pytest                     # tests
STRICT_MODE=1 pytest       # tests in strict mode (deviations crash)
ruff check .               # lint
ruff check --fix .         # lint + autofix
```

## Demo workflow

Three scripts in `examples/` that import the internal API directly (no HTTP). All idempotent — re-runs are safe. See [`docs/DEMO.md`](docs/DEMO.md) for what `seed` produces.

Activate the venv first (`source .venv/bin/activate`), then:

```bash
# 1. populate the DB with the canonical demo state
#    (5 users, 3 public topics each with their auto-default conversation,
#     1 DM (alice ↔ curie), and seeded messages)
python -m examples.seed

# 2. create one more user (smallest "is it working?" smoke)
python -m examples.add_user "Charlie Wong"
python -m examples.add_user "Tesla" --type agent --persona "Cryptic and electric."

# 3. cascade demo — soft-delete a user and watch the rels go with them
python -m examples.remove_user alice
# → prints CascadeReport(primary=1, rels=5)

# 4. re-run seed to verify idempotency — every line should say "(exists, …)"
python -m examples.seed
```

After step 1, you can also exercise the HTTP layer (start the API per the Quickstart, then in a third activated terminal):

```bash
curl -H "X-User-Slug: alice" http://localhost:8000/users/alice
curl -H "X-User-Slug: alice" http://localhost:8000/topics/daily-standup
# → topic + its `default_conversation_slug` field, which the UI uses to load messages
curl -X POST -H "X-User-Slug: alice" http://localhost:8000/dms/curie
# → the alice ↔ curie DM conversation; idempotent on repeat call
```

## Layout

- `wazzup/api/` — internal Python API; only layer that touches SQL.
- `wazzup/http/` — FastAPI routers; thin layer over `api/`.
- `wazzup/llm.py` — single function `llm.call(messages)` for OpenAI / Azure / OpenRouter.
- `wazzup/db.py` — SQLite connection, schema, migrations.
- `ui/` — plain HTML + JS + CSS. Served separately from the API.
- `tests/` — pytest, in-memory SQLite fixtures.
- `examples/` — smoke-test scripts that import the internal API directly.
- `docs/MODEL.md` — entity model + invariants in spec form.
- `docs/DEMO.md` — seeded demo data + walkthrough.
- `CLAUDE.md` — project memory for AI coding tools.

## See also

- [`../private/1-how to build simple applications.md`](../private/1-how%20to%20build%20simple%20applications.md) — full lesson.
- [`docs/MODEL.md`](docs/MODEL.md) — the model as a spec.
- [`docs/DEMO.md`](docs/DEMO.md) — seeded demo data + walkthrough.
- [`TODO.md`](TODO.md) — implementation progress and next step.
- [`CLAUDE.md`](CLAUDE.md) — architectural rules and run commands for AI tools.
