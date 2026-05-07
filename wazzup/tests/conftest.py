"""Test fixtures.

Section 9 of the lesson. Two axes:

- *Isolation*: every test gets a fresh in-memory SQLite. That's the
  ``db`` and ``client`` fixtures.
- *Schema variation*: some tests need extra SQL on top of the
  production schema (audit triggers, instrumentation indexes,
  relaxed constraints to exercise collision paths). That's what
  ``db_factory`` is for.

A note on SQLite's ALTER TABLE: limited. You can ADD a column, but
you can't drop one or change a constraint without a table rebuild.
If a test needs to relax a constraint, ``DROP TABLE x; CREATE TABLE
x (...)`` with the alternative shape — ``extra_sql`` supports it.
"""

import sqlite3
from sqlite3 import Connection

import pytest

from wazzup.db import init_schema


@pytest.fixture
def db():
    """Per-test in-memory DB with the production schema.

    ``check_same_thread=False``: pytest creates this connection on
    the main test thread, but FastAPI's TestClient runs sync route
    handlers in a worker thread (via ``anyio.to_thread.run_sync``).
    SQLite's Python binding refuses cross-thread reuse by default;
    disabling the check is the standard workaround for shared test
    fixtures. Production isn't affected — each request opens its
    own connection inside the worker thread via ``get_db``.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def db_factory():
    """Build a fresh DB; optionally layer extra SQL on top of the production schema.

    Usage::

        def test_something(db_factory):
            db = db_factory(extra_sql=[
                "CREATE TABLE _audit (op TEXT, tbl TEXT, row_id INTEGER, ts TEXT)",
                "CREATE TRIGGER ... ",
            ])
            # ...

    Default behavior (no ``extra_sql``) is identical to the ``db``
    fixture — fresh in-memory SQLite, production schema only.
    """
    created: list[Connection] = []

    def _make(extra_sql: list[str] | None = None) -> Connection:
        # Same check_same_thread=False rationale as the `db` fixture
        # above — see its docstring.
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        init_schema(conn)
        if extra_sql:
            for stmt in extra_sql:
                conn.execute(stmt)
        created.append(conn)
        return conn

    yield _make
    for c in created:
        c.close()


@pytest.fixture
def client(db, monkeypatch):
    """FastAPI TestClient with get_db overridden to point at the per-test in-memory DB.

    Two things this fixture does:

    1. **Force AUTH_DISABLED=1** for the duration of the test, via
       monkeypatch of *both* the env var and the module-level constant
       in ``http.dependencies``. ``AUTH_DISABLED`` is read at module
       import time, so flipping the env var alone wouldn't affect
       ``require_auth`` — we patch the constant directly.

    2. **Override get_db** to yield the per-test ``db`` fixture instead
       of opening a fresh sqlite3 connection. Sharing the connection
       across requests within one test is intentional: SQLite
       ``:memory:`` databases are per-connection, so a fresh connection
       would see an empty schema.
    """
    from fastapi.testclient import TestClient

    from wazzup.http import dependencies as deps_module
    from wazzup.http.dependencies import get_db
    from wazzup.http.main import app

    monkeypatch.setenv("AUTH_DISABLED", "1")
    monkeypatch.setattr(deps_module, "AUTH_DISABLED", True)

    def _override_get_db():
        # Mirror the production ``get_db`` wrapper: commit on clean
        # return, rollback on exception. Without this, a strict-mode
        # ``deviation()`` raised inside a route would *not* unwind the
        # connection's pending writes — the test would see persisted
        # rows that production would have rolled back, masking real
        # rollback bugs (the agent-reply v0.3 work surfaced this).
        #
        # The pre-yield ``db.commit()`` is the test-only shim. In
        # production, every request opens its own connection, so
        # nothing committed-elsewhere can be rolled back here. Tests
        # share *one* connection across the test body and all the
        # requests it makes, so any uncommitted setup state (e.g.
        # ``users.create()`` called from the test code) sits on the
        # same connection as the route. Without this commit, a route
        # that raises rolls back everything since the last commit,
        # including the test's setup. Committing here makes prior
        # state durable so per-request rollback only affects per-
        # request writes — matching production semantics.
        # The outer `db` fixture handles close.
        db.commit()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[get_db] = _override_get_db
    try:
        # ``raise_server_exceptions=False`` means an unhandled exception
        # inside a route returns the 500 response the production server
        # would emit, instead of being re-raised at the test boundary.
        # Tests can then assert ``resp.status_code == 500`` for
        # error-path coverage (notably the agent-reply strict-mode
        # durability test). Tests that don't expect 500 still see their
        # specific status codes — the flag only affects unhandled
        # exceptions, not normal responses.
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
