"""Database connection, schema, and migrations.

Section 5 of the lesson and ``docs/MODEL.md`` are the source of
truth. This file is the *only* place that creates the schema;
section 6 establishes the rule that ``api/`` is the only layer
that *queries* it.

The schema reflects two important teaching choices:

- **Every link lives in `rels`.** ``message`` has no
  ``conversation_id`` or ``sender_id`` columns; ``messages.create``
  writes one ``message`` row plus two ``rels`` rows
  (``belongs_to``, ``sent_by``). Production hot paths sometimes
  promote frequent rels to dedicated FK columns, but that's
  explicitly *not* what the teaching version does.
- **Slug uniqueness is enforced via a partial unique index**
  scoped to live rows (``WHERE deleted_at IS NULL``). Soft-deleted
  slugs are reusable. The application-level ``make_slug`` helper
  does the friendly suffix-on-collision; this index is the
  race-safety net.

Timestamps are not given SQL ``DEFAULT`` values on purpose. The
api/ layer must always set them explicitly with
``datetime.now(UTC).isoformat()``; a missing timestamp becomes a
``NOT NULL`` violation, which is loud (per section 11).

Schema-drift safety: ``init_schema()`` calls ``verify_schema()``
first. If an existing DB has any of the expected tables in the
*wrong* shape (e.g., an old ``message`` table that still has
``conversation_id`` from before the rels-only design was settled),
``CREATE TABLE IF NOT EXISTS`` would silently leave it alone and
the rest of the code would later fail mysteriously. Verifying
column shape at startup catches that drift loudly. Real
migrations (Alembic) are listed in *"What we haven't built
(yet)"*; this is the teaching-grade equivalent.
"""

import os
import sqlite3
from sqlite3 import Connection

# The set of valid (src_type, tgt_type) values for rels rows. Used
# in the schema's CHECK constraint and (by intent) kept as a single
# source of truth for what counts as a "named entity" link target.
NAMED_ENTITIES = ("user", "conversation", "topic", "message")
_ENTITY_LIST = ", ".join(f"'{e}'" for e in NAMED_ENTITIES)


SCHEMA_SQL = f"""
-- ============================================================
-- user
-- ============================================================
CREATE TABLE IF NOT EXISTS user (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    slug        TEXT    NOT NULL,
    type        TEXT    NOT NULL CHECK (type IN ('human', 'agent')),
    persona     TEXT,                                       -- markdown; nullable
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    deleted_at  TEXT,
    details     TEXT                                        -- JSON
);

-- slug is unique among LIVE rows; soft-deleted slugs are reusable
CREATE UNIQUE INDEX IF NOT EXISTS user_slug_alive
    ON user(slug)
    WHERE deleted_at IS NULL;

-- ============================================================
-- conversation
-- ============================================================
CREATE TABLE IF NOT EXISTS conversation (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    slug        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    deleted_at  TEXT,
    details     TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS conversation_slug_alive
    ON conversation(slug)
    WHERE deleted_at IS NULL;

-- ============================================================
-- topic
-- ============================================================
CREATE TABLE IF NOT EXISTS topic (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    slug        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    deleted_at  TEXT,
    details     TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS topic_slug_alive
    ON topic(slug)
    WHERE deleted_at IS NULL;

-- ============================================================
-- message — exception to the named-entity shape
-- ============================================================
-- No name, no slug, no conversation_id, no sender_id.
-- The conversation→message and user→message links live in `rels`
-- as `belongs_to` and `sent_by` rows.
CREATE TABLE IF NOT EXISTS message (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    deleted_at  TEXT,
    details     TEXT
);

-- ============================================================
-- rels — polymorphic links table
-- ============================================================
-- Every relationship between entities lives here. No FK integrity
-- at the DB level (the (src_type, src_id) polymorphism breaks
-- that), BUT src_type and tgt_type are constrained to the known
-- entity names — a typo like 'mesage' or 'usr' would otherwise
-- become silent data corruption (the api/ layer can't tell
-- 'mesage' from 'message' without scanning the schema).
CREATE TABLE IF NOT EXISTS rels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    src_id      INTEGER NOT NULL,
    src_type    TEXT    NOT NULL CHECK (src_type IN ({_ENTITY_LIST})),
    tgt_id      INTEGER NOT NULL,
    tgt_type    TEXT    NOT NULL CHECK (tgt_type IN ({_ENTITY_LIST})),
    rel_type    TEXT    NOT NULL,
    details     TEXT,
    created_at  TEXT    NOT NULL,
    deleted_at  TEXT
);

CREATE INDEX IF NOT EXISTS rels_src
    ON rels(src_type, src_id);

CREATE INDEX IF NOT EXISTS rels_tgt
    ON rels(tgt_type, tgt_id);

CREATE INDEX IF NOT EXISTS rels_type
    ON rels(rel_type);

-- prevent duplicate live rels (e.g., user 4 member_of topic 5 twice)
CREATE UNIQUE INDEX IF NOT EXISTS rels_dedupe_alive
    ON rels(src_type, src_id, tgt_type, tgt_id, rel_type)
    WHERE deleted_at IS NULL;
"""


# Expected column set per table — the canonical shape ``init_schema``
# would produce on a fresh DB. ``verify_schema`` checks any existing
# tables against this and raises if they drift (e.g., an old
# ``message`` table with leftover FK columns from before the
# rels-only design was settled).
EXPECTED_COLUMNS = {
    "user": {
        "id", "name", "slug", "type", "persona",
        "created_at", "updated_at", "deleted_at", "details",
    },
    "conversation": {
        "id", "name", "slug",
        "created_at", "updated_at", "deleted_at", "details",
    },
    "topic": {
        "id", "name", "slug",
        "created_at", "updated_at", "deleted_at", "details",
    },
    "message": {
        "id", "text",
        "created_at", "updated_at", "deleted_at", "details",
    },
    "rels": {
        "id", "src_id", "src_type", "tgt_id", "tgt_type", "rel_type",
        "details", "created_at", "deleted_at",
    },
}


class SchemaMismatch(RuntimeError):
    """Raised when an existing table's column set drifts from EXPECTED_COLUMNS."""


def verify_schema(db: Connection) -> None:
    """Check existing tables against ``EXPECTED_COLUMNS``.

    Tables that don't exist yet are fine — ``init_schema`` will
    create them. Tables that exist but have a different column
    set raise ``SchemaMismatch`` with a diagnostic message.

    This catches the case where a DB was created under an older
    schema version and the new ``CREATE TABLE IF NOT EXISTS`` would
    silently leave the wrong shape in place. It does *not* catch
    constraint-level drift (e.g., a missing CHECK constraint on a
    column that exists with the right name); that's migration
    territory and explicitly out of scope here.
    """
    for table, expected in EXPECTED_COLUMNS.items():
        rows = list(db.execute(f"PRAGMA table_info({table})"))
        if not rows:
            continue   # table doesn't exist yet — init_schema will create it
        actual = {row[1] for row in rows}   # row[1] = column name
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise SchemaMismatch(
                f"table {table!r} has unexpected column shape:\n"
                f"  missing columns: {missing or '(none)'}\n"
                f"  extra columns:   {extra or '(none)'}\n"
                f"This usually means the DB was created under an older schema. "
                f"For dev: delete the DB file and re-init. "
                f"For data you care about: write a real migration (out of scope here)."
            )


def get_db_path() -> str:
    """Resolve the SQLite file path from env (default ``./wazzup.db``)."""
    return os.environ.get("WAZZUP_DB_PATH", "./wazzup.db")


def init_schema(db: Connection) -> None:
    """Create all tables and indexes. Idempotent on fresh / matching DBs.

    Existing tables are validated first (``verify_schema``); if any
    table has the wrong column shape, ``SchemaMismatch`` is raised
    *before* any ``CREATE TABLE IF NOT EXISTS`` runs. This is the
    teaching-grade substitute for real migrations.
    """
    verify_schema(db)
    db.executescript(SCHEMA_SQL)


def connect() -> Connection:
    """Open a connection with row_factory and FK enforcement turned on.

    ``check_same_thread=False`` is required because FastAPI runs sync
    deps (``get_db``) and sync route handlers via ``anyio.to_thread``,
    which doesn't guarantee they land on the same worker thread within
    one request. Without this flag, sqlite3's Python binding refuses
    cross-thread reuse and raises ``ProgrammingError`` on the first
    DB call in the route. We're not using the connection
    *concurrently* — each request gets its own connection, used
    sequentially across whatever workers anyio dispatches to — so
    disabling the per-thread guard is safe.

    Same flag is set on the test fixtures in ``tests/conftest.py``;
    keeping both sides aligned is what makes the test suite a real
    regression detector for this code path.
    """
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
