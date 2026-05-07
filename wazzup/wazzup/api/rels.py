"""Single rels-table API — section 3 of the lesson.

Three operations only (no name/slug; rels aren't named):

    add(db, *, src_type, src_id, tgt_type, tgt_id, rel_type, details=None) -> RelRead
    remove(db, id, hard=False) -> None
    list(db, *, src_type=None, src_id=None, tgt_type=None, tgt_id=None,
         rel_type=None, limit=50, offset=0) -> list[RelRead]

**Why keyword-only signatures?** A bare positional 5-arg call
(`add(db, "user", 1, "topic", 2, "member_of")`) is unreadable and
trivially misorderable. Keyword-only forces self-documenting call
sites:

    rels.add(db, src_type="user", src_id=4,
                 tgt_type="topic", tgt_id=2,
                 rel_type="member_of")

**Why no ``update``?** A rel either exists or is soft-deleted; it
doesn't get edited. ``RelRead`` has no ``updated_at`` for the same
reason (per ``docs/MODEL.md`` and ``models.py``).

**FK-existence validation.** rels is polymorphic — there's no
schema-level FK from ``src_id`` / ``tgt_id`` to the entity tables,
because the (src_type, src_id) pair could point at any of them.
The schema's CHECK on src_type/tgt_type catches *type* typos; this
module's ``add`` validates *id existence* against the right entity
table by dispatch on src_type / tgt_type. Without this check, a
typo or stale id would silently create a dangling rel.

**Caller owns the transaction** (no ``db.commit()`` here), same as
every other api module.

**Note on the ``list`` name.** ``def list`` shadows Python's
built-in ``list`` inside this module. Annotations on the function
signature (e.g. ``-> list[RelRead]``) would normally fail to
evaluate because they'd resolve to *this function* rather than the
built-in type. ``from __future__ import annotations`` defers all
annotation evaluation to string form, sidestepping the issue —
type checkers still resolve names correctly. The cost is one
import line; the win is a public name that matches what the
lesson, ``docs/MODEL.md``, and ``api/__init__.py`` all advertise.

**Note on the ``messages`` import.** ``api/messages.py`` imports
``rels`` (it calls ``rels.add`` to write its two rels per message).
If we imported ``messages`` at module top here, we'd have a
circular import: messages → rels → messages, and the second leg
would see a half-initialized ``messages`` module without ``get``
defined yet. We defer the ``messages`` import to inside ``add()``;
Python caches the import after first call, so the cost is a one-
time lookup. The other entity modules (users, conversations,
topics) don't depend on rels at module scope, so they import
normally.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from sqlite3 import Connection, Row

from wazzup.api import NotFound
from wazzup.models import RelDetails, RelRead


def _row_to_relread(row: Row) -> RelRead:
    """sqlite3.Row → RelRead. Same json.loads(details) pattern as everywhere else."""
    raw = dict(row)
    raw["details"] = json.loads(raw["details"]) if raw["details"] else {}
    return RelRead.model_validate(raw)


_ALLOWED_TYPES = {"user", "conversation", "topic", "message"}


def _row_exists(db: Connection, table: str, id: int) -> bool:
    """Lightweight existence check for FK validation in ``add()``.

    Uses raw SQL rather than ``<entity>.get()`` so we don't trigger any
    invariant-checking machinery (e.g., ``topics.get()`` fires a
    ``deviation`` if a topic lacks its default conversation). FK checks
    only need to know "is the row alive"; full reads do more than that.
    """
    row = db.execute(
        f"SELECT 1 FROM {table} WHERE id = ? AND deleted_at IS NULL",
        (id,),
    ).fetchone()
    return row is not None


def add(
    db: Connection,
    *,
    src_type: str,
    src_id: int,
    tgt_type: str,
    tgt_id: int,
    rel_type: str,
    details: RelDetails | None = None,
) -> RelRead:
    """Insert one rels row. Caller owns the transaction.

    Validates that src and tgt entities exist (live, not soft-deleted)
    before insert. The schema CHECK validates the *type* strings; the
    api validates the *ids* via a lightweight ``SELECT 1`` (not a full
    entity read — see ``_row_exists`` for why).

    Duplicate live (src_type, src_id, tgt_type, tgt_id, rel_type)
    raises ``IntegrityError`` (the schema's ``rels_dedupe_alive``
    partial UNIQUE catches it). Caller decides what to do.

    Soft-delete reuse: re-adding a previously soft-deleted rel works
    automatically — the partial UNIQUE filters live rows only.
    """
    if src_type not in _ALLOWED_TYPES:
        raise ValueError(f"rels.add: unknown src_type {src_type!r}")
    if tgt_type not in _ALLOWED_TYPES:
        raise ValueError(f"rels.add: unknown tgt_type {tgt_type!r}")
    if not _row_exists(db, src_type, src_id):
        raise NotFound(f"rels.add: src ({src_type}, {src_id}) not found")
    if not _row_exists(db, tgt_type, tgt_id):
        raise NotFound(f"rels.add: tgt ({tgt_type}, {tgt_id}) not found")

    now = datetime.now(UTC).isoformat()
    details_obj = details if details is not None else RelDetails()
    details_json = json.dumps(details_obj.model_dump())

    cursor = db.execute(
        "INSERT INTO rels (src_type, src_id, tgt_type, tgt_id, rel_type, "
        "                  created_at, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (src_type, src_id, tgt_type, tgt_id, rel_type, now, details_json),
    )
    row = db.execute("SELECT * FROM rels WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_relread(row)


def remove(db: Connection, id: int, hard: bool = False) -> None:
    """Soft-delete a rel by id. Raises NotFound on missing live row.

    Same shape as the entity ``delete()`` functions (uniform error
    convention). ``hard=True`` physically removes the row.

    Caller owns the transaction.
    """
    if hard:
        cursor = db.execute("DELETE FROM rels WHERE id = ?", (id,))
    else:
        now = datetime.now(UTC).isoformat()
        cursor = db.execute(
            "UPDATE rels SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (now, id),
        )

    if cursor.rowcount == 0:
        raise NotFound(f"rels id={id} not found")


def list(
    db: Connection,
    *,
    src_type: str | None = None,
    src_id: int | None = None,
    tgt_type: str | None = None,
    tgt_id: int | None = None,
    rel_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[RelRead]:
    """List live rels matching all provided filters. None = "any".

    Returns an empty list on no match (no exception). Soft-deleted
    rels are excluded.

    Common patterns:
        list(db, src_type="user", src_id=42)        # all rels FROM alice
        list(db, tgt_type="topic", tgt_id=5)        # all rels TO topic 5
        list(db, rel_type="member_of",
             tgt_type="topic", tgt_id=5)            # all members of topic 5
    """
    sql = "SELECT * FROM rels WHERE deleted_at IS NULL"
    params: list = []
    for col, val in (
        ("src_type", src_type),
        ("src_id", src_id),
        ("tgt_type", tgt_type),
        ("tgt_id", tgt_id),
        ("rel_type", rel_type),
    ):
        if val is not None:
            sql += f" AND {col} = ?"
            params.append(val)
    sql += " ORDER BY id LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = db.execute(sql, params).fetchall()
    return [_row_to_relread(r) for r in rows]
