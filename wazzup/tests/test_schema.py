"""Schema regression tests.

These tests encode the constraints the schema is supposed to enforce.
If something drifts (a CHECK is removed, a UNIQUE becomes too lax,
a column is added under the wrong name), one of these tests fails.

Pairs with `wazzup/db.py` (the schema source) and `docs/MODEL.md`
(the spec). When you change either, update the corresponding test
here too.
"""

import sqlite3

import pytest

from wazzup.db import (
    EXPECTED_COLUMNS,
    SchemaMismatch,
    init_schema,
)

NOW = "2026-05-06T14:00:00Z"


# ---------- shape ----------

def test_init_schema_creates_all_expected_tables(db):
    """Every table named in EXPECTED_COLUMNS exists with the right column set."""
    for table, expected in EXPECTED_COLUMNS.items():
        rows = list(db.execute(f"PRAGMA table_info({table})"))
        assert rows, f"table {table!r} not created"
        actual = {r["name"] for r in rows}
        assert actual == expected, f"{table}: missing={expected-actual} extra={actual-expected}"


def test_init_schema_is_idempotent(db):
    """Running init_schema twice on the same DB does not error."""
    init_schema(db)   # second call; first happened in the fixture


def test_init_schema_detects_drift_on_existing_db():
    """An existing table with the wrong shape raises SchemaMismatch.

    This is the regression test for the friend's catch — the
    pre-rels-only `message` table with `conversation_id` and
    `sender_id` columns must be detected, not silently kept.
    """
    drifted = sqlite3.connect(":memory:")
    drifted.executescript("""
        CREATE TABLE message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_id       INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT,
            details TEXT
        );
    """)
    with pytest.raises(SchemaMismatch, match="message"):
        init_schema(drifted)


def test_init_schema_detects_missing_columns():
    drifted = sqlite3.connect(":memory:")
    drifted.executescript("""
        CREATE TABLE user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    with pytest.raises(SchemaMismatch, match="user"):
        init_schema(drifted)


# ---------- user constraints ----------

def test_user_slug_unique_among_live_rows(db):
    """Two live users can't share a slug."""
    db.execute(
        "INSERT INTO user (name, slug, type, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("Alice", "alice", "human", NOW, NOW),
    )
    with pytest.raises(sqlite3.IntegrityError, match="user.slug"):
        db.execute(
            "INSERT INTO user (name, slug, type, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("Other", "alice", "human", NOW, NOW),
        )


def test_user_slug_reusable_after_soft_delete(db):
    """A soft-deleted slug can be reused by a new live row."""
    db.execute(
        "INSERT INTO user (name, slug, type, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("Alice 1", "alice", "human", NOW, NOW),
    )
    db.execute("UPDATE user SET deleted_at = ? WHERE slug = 'alice'", (NOW,))
    db.execute(
        "INSERT INTO user (name, slug, type, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("Alice 2", "alice", "human", NOW, NOW),
    )
    rows = list(db.execute("SELECT id, deleted_at FROM user WHERE slug = 'alice'"))
    assert len(rows) == 2
    live = [r for r in rows if r["deleted_at"] is None]
    dead = [r for r in rows if r["deleted_at"] is not None]
    assert len(live) == 1 and len(dead) == 1


def test_user_type_check_rejects_unknown(db):
    """`type` must be 'human' or 'agent'."""
    with pytest.raises(sqlite3.IntegrityError, match="type"):
        db.execute(
            "INSERT INTO user (name, slug, type, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("Bender", "bender", "robot", NOW, NOW),
        )


def test_user_created_at_required(db):
    """Missing `created_at` is a NOT NULL violation, not a silent NULL."""
    with pytest.raises(sqlite3.IntegrityError, match="created_at"):
        db.execute(
            "INSERT INTO user (name, slug, type) VALUES (?, ?, ?)",
            ("Bob", "bob", "human"),
        )


# ---------- rels constraints ----------

def test_rels_src_type_check_rejects_typo(db):
    """`src_type` must be one of the named entities."""
    with pytest.raises(sqlite3.IntegrityError, match="src_type"):
        db.execute(
            "INSERT INTO rels (src_id, src_type, tgt_id, tgt_type, rel_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (1, "mesage", 1, "user", "sent_by", NOW),
        )


def test_rels_tgt_type_check_rejects_typo(db):
    """`tgt_type` must be one of the named entities."""
    with pytest.raises(sqlite3.IntegrityError, match="tgt_type"):
        db.execute(
            "INSERT INTO rels (src_id, src_type, tgt_id, tgt_type, rel_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (1, "user", 1, "usr", "has", NOW),
        )


def test_rels_dedupe_among_live(db):
    """Can't insert two live rows with the same (src, tgt, rel_type) tuple."""
    db.execute(
        "INSERT INTO rels (src_id, src_type, tgt_id, tgt_type, rel_type, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (1, "user", 1, "topic", "member_of", NOW),
    )
    with pytest.raises(sqlite3.IntegrityError, match="rels"):
        db.execute(
            "INSERT INTO rels (src_id, src_type, tgt_id, tgt_type, rel_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (1, "user", 1, "topic", "member_of", NOW),
        )


# ---------- db_factory pattern ----------

def test_db_factory_layers_extra_sql(db_factory):
    """`db_factory(extra_sql=...)` applies SQL on top of the production schema."""
    db = db_factory(extra_sql=[
        "CREATE TABLE _audit (op TEXT, tbl TEXT, row_id INTEGER, ts TEXT)",
    ])
    rows = list(db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='_audit'"))
    assert len(rows) == 1
    # And the production tables are still there
    rows = list(db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'"))
    assert len(rows) == 1
