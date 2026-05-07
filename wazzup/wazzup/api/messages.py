"""Message CRUD — exception to the named-entity shape.

Messages have NO ``name`` and NO ``slug`` (see docs/MODEL.md).
They're addressed by id; reads typically go by conversation.

**The rels-only design (section 3 of the lesson).** ``message`` has
no direct ``conversation_id`` or ``sender_id`` FK columns. The links
live in the ``rels`` table:

    create(db, MessageCreate(conversation_id=..., sender_id=..., text=...)):
        1. validate sender + conversation are live (NotFound if not)
        2. INSERT INTO message (text, created_at, ...) VALUES (...)
        3. INSERT a 'belongs_to' rel: message → conversation
        4. INSERT a 'sent_by' rel: message → user

    query(db, conversation_id=...):
        SELECT m.* FROM message m
        JOIN rels r ON r.src_id = m.id AND r.src_type = 'message'
                  AND r.rel_type = 'belongs_to' AND r.deleted_at IS NULL
        WHERE r.tgt_id = ? AND r.tgt_type = 'conversation'
          AND m.deleted_at IS NULL

The function *signatures* below take ``conversation_id`` and
``sender_id`` (via ``MessageCreate``) because that's how callers
think; the *implementation* writes them as rels. Don't be tempted
to add FK columns to ``message`` — that's the production-pragmatic
shortcut the lesson explicitly defers.

**Update scope.** ``MessageUpdate`` only touches ``text`` and
``details`` — no slug, no link patches. Changing the conversation
a message belongs to means deleting and re-creating, not patching.
"""

import json
from datetime import UTC, datetime
from sqlite3 import Connection, Row

from wazzup.api import NotFound, conversations, rels, users
from wazzup.models import MessageCreate, MessageRead, MessageUpdate

_UPDATABLE_FIELDS = {"text", "details"}

# Same NOT NULL defense as users / conversations / topics — see
# nullability rule in models.py. MessageUpdate.text is `str | None = None`,
# so Pydantic accepts None at construction; the schema column is NOT NULL.
_NOT_NULL_FIELDS = {"text"}


def _row_to_messageread(row: Row) -> MessageRead:
    """sqlite3.Row → MessageRead. Stored columns only — no rel-derived ids."""
    raw = dict(row)
    raw["details"] = json.loads(raw["details"]) if raw["details"] else {}
    return MessageRead.model_validate(raw)


def create(db: Connection, data: MessageCreate) -> MessageRead:
    """Insert one message + two rels (belongs_to, sent_by) atomically.

    Caller owns the transaction — if any of the three INSERTs fails,
    the caller's rollback covers all three. This is the *one* api-layer
    function that writes to multiple tables in one call; that asymmetry
    is the price of the rels-only design.

    Validates that sender and conversation exist (live, not soft-deleted)
    before inserting. Otherwise a typo silently creates an orphan
    message + dangling rels (no schema-level FK to catch it, since
    rels is polymorphic).
    """
    # 1. Validate links exist and are live.
    if users.get(db, data.sender_id) is None:
        raise NotFound(f"sender_id={data.sender_id} not found")
    if conversations.get(db, data.conversation_id) is None:
        raise NotFound(f"conversation_id={data.conversation_id} not found")

    now = datetime.now(UTC).isoformat()
    details_json = json.dumps(data.details.model_dump())

    # 2. Insert message row.
    cursor = db.execute(
        "INSERT INTO message (text, created_at, updated_at, details) "
        "VALUES (?, ?, ?, ?)",
        (data.text, now, now, details_json),
    )
    msg_id = cursor.lastrowid

    # 3. Insert the two rels via the rels api (closes TODO #22 — was an
    # inlined helper before api/rels.py landed in #12).
    rels.add(
        db,
        src_type="message", src_id=msg_id,
        tgt_type="conversation", tgt_id=data.conversation_id,
        rel_type="belongs_to",
    )
    rels.add(
        db,
        src_type="message", src_id=msg_id,
        tgt_type="user", tgt_id=data.sender_id,
        rel_type="sent_by",
    )

    # 4. Re-read & return.
    row = db.execute("SELECT * FROM message WHERE id = ?", (msg_id,)).fetchone()
    return _row_to_messageread(row)


def get(db: Connection, id: int) -> MessageRead | None:
    """Fetch a live message by id. Returns None if absent or soft-deleted.

    No ``get_by_slug`` — messages don't have slugs.
    """
    row = db.execute(
        "SELECT * FROM message WHERE id = ? AND deleted_at IS NULL", (id,)
    ).fetchone()
    return _row_to_messageread(row) if row else None


def update(db: Connection, id: int, patch: MessageUpdate) -> MessageRead:
    """PATCH semantics. Only ``text`` and ``details`` editable.

    Caller owns the transaction. Raises NotFound if id doesn't match
    a live row. Edits to message links (which conversation it belongs
    to, who sent it) are not supported — delete and re-create.
    """
    fields = patch.model_dump(exclude_unset=True)

    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValueError(f"messages.update: unknown fields in patch: {sorted(unknown)}")

    null_violations = [f for f in _NOT_NULL_FIELDS if f in fields and fields[f] is None]
    if null_violations:
        raise ValueError(
            f"messages.update: cannot set NOT NULL field(s) to None: {null_violations}. "
            f"To leave them unchanged, omit them from the patch."
        )

    if "details" in fields:
        fields["details"] = json.dumps(fields["details"])

    fields["updated_at"] = datetime.now(UTC).isoformat()

    set_clause = ", ".join(f"{col} = ?" for col in fields)
    params = list(fields.values()) + [id]

    cursor = db.execute(
        f"UPDATE message SET {set_clause} WHERE id = ? AND deleted_at IS NULL",
        params,
    )
    if cursor.rowcount == 0:
        raise NotFound(f"message id={id} not found")

    return get(db, id)


def _delete_primary(db: Connection, id: int, hard: bool = False) -> bool:
    """Delete just the message row. Returns True iff a row was affected."""
    if hard:
        cursor = db.execute("DELETE FROM message WHERE id = ?", (id,))
    else:
        now = datetime.now(UTC).isoformat()
        cursor = db.execute(
            "UPDATE message SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (now, id),
        )
    return cursor.rowcount > 0


def delete(db: Connection, id: int, hard: bool = False) -> None:
    """Soft-delete by default. Cascades via ``api/deletion.cascade_delete``.

    Cascades the message's two rels (`belongs_to` conversation,
    `sent_by` user). No nested entities. Caller owns the transaction.
    """
    from wazzup.api.deletion import cascade_delete

    report = cascade_delete(db, table="message", id=id, hard=hard)
    if report.primary == 0:
        raise NotFound(f"message id={id} not found")


def query(
    db: Connection,
    *,
    conversation_id: int,
    sender_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[MessageRead]:
    """List live messages in a conversation, optionally filtered by sender.

    JOINs through rels because there's no conversation_id / sender_id
    column on ``message``. Soft-deleted rels and messages are both
    excluded.

    Note ``conversation_id`` is required (positional via kw-only) — there's
    no global "all messages" listing in the smoke slice. If you want one,
    add an explicit code path; don't fall through to ``conversation_id IS
    NULL`` semantics, which would surprise callers.
    """
    sql = """
        SELECT m.* FROM message m
        JOIN rels r_conv
            ON r_conv.src_id = m.id
           AND r_conv.src_type = 'message'
           AND r_conv.rel_type = 'belongs_to'
           AND r_conv.deleted_at IS NULL
        WHERE r_conv.tgt_id = ?
          AND r_conv.tgt_type = 'conversation'
          AND m.deleted_at IS NULL
    """
    params: list = [conversation_id]

    if sender_id is not None:
        sql += """
            AND EXISTS (
                SELECT 1 FROM rels r_send
                WHERE r_send.src_id = m.id
                  AND r_send.src_type = 'message'
                  AND r_send.rel_type = 'sent_by'
                  AND r_send.tgt_id = ?
                  AND r_send.tgt_type = 'user'
                  AND r_send.deleted_at IS NULL
            )
        """
        params.append(sender_id)

    sql += " ORDER BY m.id LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = db.execute(sql, params).fetchall()
    return [_row_to_messageread(r) for r in rows]
