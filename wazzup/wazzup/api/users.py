"""User CRUD — section 6 of the lesson.

The pattern this module establishes (slug-on-create with bounded
retry, ``_row_to_userread`` helper, NotFound on update/delete,
caller-owns-transaction) is mirrored by ``conversations.py``,
``topics.py``, and ``messages.py`` (TODO #11). Touch this file
carefully; downstream entity modules will copy its shape.

Error conventions (see ``CLAUDE.md``):
    create  → returns UserRead; on slug-collision race after retry, propagates IntegrityError
    get / get_by_slug → returns UserRead | None
    update  → returns UserRead; raises NotFound if missing
    delete  → returns None;     raises NotFound if missing
    query   → returns list[UserRead]; empty list on no match

Caller owns the transaction. None of these call ``db.commit()``.
"""

import json
from datetime import UTC, datetime
from sqlite3 import Connection, IntegrityError, Row

from wazzup.api import NotFound
from wazzup.api.slugs import make_slug
from wazzup.models import UserCreate, UserRead, UserUpdate

# Whitelist of fields the api layer will write to on UPDATE.
# Anything else in a UserUpdate.model_dump() is a programming error.
# (slug is intentionally absent — slugs are stable once assigned.)
_UPDATABLE_FIELDS = {"name", "type", "persona", "details"}

# Subset of _UPDATABLE_FIELDS whose columns are NOT NULL in the schema.
# An explicit None in the patch dict for these fields would otherwise
# generate `SET name = NULL`, which the schema would reject — but with
# a much less helpful error than this one. See the "Nullability rule"
# in wazzup/models.py module docstring.
_NOT_NULL_FIELDS = {"name", "type"}

# Bounded retry on slug-collision race. The application-level
# make_slug() check normally avoids collisions, but a concurrent
# insert can race past it; the schema's partial UNIQUE on
# (slug WHERE deleted_at IS NULL) is the safety net. After this
# many retries we give up and let IntegrityError propagate.
_MAX_SLUG_RETRIES = 5


def _row_to_userread(row: Row) -> UserRead:
    """Convert a sqlite3.Row to a UserRead.

    Pydantic v2's ``model_validate`` does NOT auto-``json.loads`` a
    string into a nested Pydantic model field; ``details`` must be
    parsed explicitly here. ISO-8601 timestamps are coerced to
    ``datetime`` automatically.
    """
    raw = dict(row)
    raw["details"] = json.loads(raw["details"]) if raw["details"] else {}
    return UserRead.model_validate(raw)


def create(db: Connection, data: UserCreate) -> UserRead:
    """Insert one user row. Caller owns the transaction (no db.commit() here).

    Slug is server-derived from ``data.name`` via ``make_slug``. If
    ``data.slug`` is provided as an override, collisions still get
    suffixed silently — this is consistent with ``make_slug`` and is
    locked in by ``test_create_explicit_override_collision``. A
    follow-up TODO captures distinguishing explicit-override
    collisions (which probably should be 409) from auto-derived
    ones (which should suffix); not in scope for #8.
    """
    now = datetime.now(UTC).isoformat()
    details_json = json.dumps(data.details.model_dump())

    last_error: IntegrityError | None = None
    for _ in range(_MAX_SLUG_RETRIES):
        slug = make_slug(db, "user", data.name, override=data.slug)
        try:
            cursor = db.execute(
                "INSERT INTO user (name, slug, type, persona, "
                "                  created_at, updated_at, details) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (data.name, slug, data.type, data.persona, now, now, details_json),
            )
            row = db.execute(
                "SELECT * FROM user WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return _row_to_userread(row)
        except IntegrityError as e:
            # Almost always the partial UNIQUE on slug — a concurrent
            # insert raced past make_slug's check. Loop and try again
            # with a freshly-derived slug.
            last_error = e
            continue
    # If we got here, _MAX_SLUG_RETRIES racing inserts happened in
    # a row. That's almost certainly a real bug, not a race; let the
    # caller see it.
    raise last_error if last_error else IntegrityError("create user: exhausted retries")


def get(db: Connection, id: int) -> UserRead | None:
    """Fetch a live user by id. Returns None if absent or soft-deleted."""
    row = db.execute(
        "SELECT * FROM user WHERE id = ? AND deleted_at IS NULL", (id,)
    ).fetchone()
    return _row_to_userread(row) if row else None


def get_by_slug(db: Connection, slug: str) -> UserRead | None:
    """Fetch a live user by slug. Returns None if absent or soft-deleted."""
    row = db.execute(
        "SELECT * FROM user WHERE slug = ? AND deleted_at IS NULL", (slug,)
    ).fetchone()
    return _row_to_userread(row) if row else None


def update(db: Connection, id: int, patch: UserUpdate) -> UserRead:
    """PATCH an existing user. Raises NotFound if id doesn't match a live row.

    Only fields present in ``patch`` (model_dump exclude_unset=True)
    are touched. ``details`` is *replaced*, not merged — that's
    standard PATCH semantics for nested objects. ``slug`` cannot be
    patched: it's stable once assigned (UserUpdate has no slug field).

    Caller owns the transaction.
    """
    fields = patch.model_dump(exclude_unset=True)

    # Defensive: every key must be in our writable set. A stray key
    # would otherwise silently NOT update; better to make it loud.
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValueError(f"users.update: unknown fields in patch: {sorted(unknown)}")

    # NOT NULL defense: explicit None for a NOT NULL field would
    # otherwise generate `SET name = NULL` and surface as a much
    # less helpful IntegrityError. See nullability rule in models.py.
    null_violations = [f for f in _NOT_NULL_FIELDS if f in fields and fields[f] is None]
    if null_violations:
        raise ValueError(
            f"users.update: cannot set NOT NULL field(s) to None: {null_violations}. "
            f"To leave them unchanged, omit them from the patch."
        )

    # JSON-encode details if present
    if "details" in fields:
        fields["details"] = json.dumps(fields["details"])

    # Always advance updated_at, even on an empty patch (the row
    # was touched, that's a real event).
    fields["updated_at"] = datetime.now(UTC).isoformat()

    set_clause = ", ".join(f"{col} = ?" for col in fields)
    params = list(fields.values()) + [id]

    cursor = db.execute(
        f"UPDATE user SET {set_clause} WHERE id = ? AND deleted_at IS NULL",
        params,
    )
    if cursor.rowcount == 0:
        raise NotFound(f"user id={id} not found")

    return get(db, id)   # re-read to pick up DB-side state if any


def _delete_primary(db: Connection, id: int, hard: bool = False) -> bool:
    """Delete just the user row. Returns True iff a row was affected.

    Used by ``api/deletion.cascade_delete``; do not call this directly
    from outside the api package — use the public ``delete()`` so
    cascade through rels happens. The split exists so cascade can be
    idempotent (returns CascadeReport(primary=0) on already-deleted)
    while the public ``delete()`` keeps the raise-NotFound contract.
    """
    if hard:
        cursor = db.execute("DELETE FROM user WHERE id = ?", (id,))
    else:
        now = datetime.now(UTC).isoformat()
        cursor = db.execute(
            "UPDATE user SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (now, id),
        )
    return cursor.rowcount > 0


def delete(db: Connection, id: int, hard: bool = False) -> None:
    """Soft-delete by default. Raises NotFound if id doesn't match a live row.

    Cascades through rels via ``api/deletion.cascade_delete`` (#13):
    soft-deleting a user also soft-deletes every rel they appear in
    (sent_by, member_of, etc.). Hard cascade is symmetric — the
    ``hard`` flag propagates uniformly.

    Caller owns the transaction.
    """
    # Late import: api/deletion.py imports each entity at module top,
    # so importing it from here at module top would be a cycle.
    # Importing inside the function body delays the resolution until
    # call time, by which point both modules are fully loaded.
    from wazzup.api.deletion import cascade_delete

    report = cascade_delete(db, table="user", id=id, hard=hard)
    if report.primary == 0:
        raise NotFound(f"user id={id} not found")


def query(
    db: Connection,
    *,
    type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[UserRead]:
    """List live users, optionally filtered by ``type``.

    Soft-deleted rows are excluded. Returns an empty list on no
    match (no exception).
    """
    sql = "SELECT * FROM user WHERE deleted_at IS NULL"
    params: list = []
    if type is not None:
        sql += " AND type = ?"
        params.append(type)
    sql += " ORDER BY id LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = db.execute(sql, params).fetchall()
    return [_row_to_userread(r) for r in rows]
