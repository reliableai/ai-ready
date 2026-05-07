"""Topic CRUD — public chat rooms.

**Boundary rule (see ``docs/MODEL.md``).** A topic owns exactly one
default conversation, auto-created in the same transaction as
``topics.create()``. Posting "on a topic" means writing into that
conversation. Together with ``conversations.get_or_create_dm()``, this
is the only public path that creates a conversation; ``conversations``
exposes no public ``create`` (renamed to ``_create``).

Schema notes:
- topic rows: name + slug + details + timestamps + deleted_at.
- conversation→topic link: a single ``in_topic`` rel
  (src=conversation, tgt=topic).
- _UPDATABLE_FIELDS = {"name", "details"}.

``TopicRead.default_conversation_slug`` is non-Optional. Every read
helper looks it up via the ``in_topic`` rel and populates the field.
If the rel is missing — an architectural drift, not a normal state —
``deviation()`` fires (raises in strict mode; logs + ``"<missing>"``
sentinel in lax mode, so the UI breaks loudly rather than silently
defaulting).

Visibility / access control: topics are public for v0.1. The
``can_access(...)`` hook returns ``True`` unconditionally; future
private/group topics will tighten it without requiring call-site
changes.
"""

import json
from datetime import UTC, datetime
from sqlite3 import Connection, IntegrityError, Row

from wazzup.api import NotFound
from wazzup.api.slugs import make_slug
from wazzup.logging_setup import deviation
from wazzup.models import ConversationCreate, TopicCreate, TopicRead, TopicUpdate

_UPDATABLE_FIELDS = {"name", "details"}

# Same NOT NULL defense as users / conversations — see nullability
# rule in models.py. TopicUpdate.name is `str | None = None`, so Pydantic
# accepts None; the schema column is NOT NULL.
_NOT_NULL_FIELDS = {"name"}

_MAX_SLUG_RETRIES = 5


_MISSING_SENTINEL_ID = 0
_MISSING_SENTINEL_SLUG = "<missing>"


def _default_conversation_info(db: Connection, topic_id: int) -> tuple[int, str]:
    """Look up the default conversation's (id, slug) via the ``in_topic`` rel.

    Returns the pair, or fires ``deviation()`` and returns the sentinels
    ``(0, "<missing>")`` if the rel is missing. ``TopicRead.default_conversation_*``
    are non-Optional by invariant; this helper enforces the contract.

    Strict mode (``STRICT_MODE=1``) makes the ``deviation()`` raise, so
    the read fails loudly. Lax mode logs and surfaces the sentinels —
    the UI will break visibly (``GET /conversations/<missing>/messages``
    returns 404) which is the right outcome for an invariant violation.
    """
    row = db.execute(
        "SELECT c.id AS conv_id, c.slug AS conv_slug FROM rels r "
        "JOIN conversation c ON c.id = r.src_id "
        "WHERE r.rel_type = 'in_topic' "
        "  AND r.tgt_type = 'topic' AND r.tgt_id = ? "
        "  AND r.src_type = 'conversation' "
        "  AND r.deleted_at IS NULL "
        "  AND c.deleted_at IS NULL "
        "LIMIT 1",
        (topic_id,),
    ).fetchone()
    if row is None:
        deviation("topic missing default conversation", topic_id=topic_id)
        return (_MISSING_SENTINEL_ID, _MISSING_SENTINEL_SLUG)
    return (row["conv_id"], row["conv_slug"])


def get_default_conversation_id(db: Connection, topic_id: int) -> int | None:
    """Return the id of this topic's default conversation, or ``None`` if absent.

    Unlike ``_default_conversation_info``, this does NOT call ``deviation``;
    callers like ``examples/seed.py``'s repair path use the ``None`` return
    as the cue to heal a missing rel deliberately.
    """
    row = db.execute(
        "SELECT r.src_id FROM rels r "
        "JOIN conversation c ON c.id = r.src_id "
        "WHERE r.rel_type = 'in_topic' "
        "  AND r.tgt_type = 'topic' AND r.tgt_id = ? "
        "  AND r.src_type = 'conversation' "
        "  AND r.deleted_at IS NULL "
        "  AND c.deleted_at IS NULL "
        "LIMIT 1",
        (topic_id,),
    ).fetchone()
    return row["src_id"] if row else None


def can_access(db: Connection, *, user_id: int, topic_id: int) -> bool:
    """Future-private-topics hook. Returns ``True`` for v0.1 (all topics public).

    When private/group topics ship, this becomes a ``member_of`` rel check
    plus a ``topic.visibility`` lookup. Wire every topic read/write path
    through here so that single change propagates without scattering.
    """
    return True


def _row_to_topicread(db: Connection, row: Row) -> TopicRead:
    """Build TopicRead from a row, populating ``default_conversation_*``."""
    raw = dict(row)
    raw["details"] = json.loads(raw["details"]) if raw["details"] else {}
    conv_id, conv_slug = _default_conversation_info(db, raw["id"])
    raw["default_conversation_id"] = conv_id
    raw["default_conversation_slug"] = conv_slug
    return TopicRead.model_validate(raw)


def create(db: Connection, data: TopicCreate) -> TopicRead:
    """Insert one topic row + its auto-default conversation + the ``in_topic`` rel.

    All three writes happen in the caller's transaction (no commit here).
    Slug for the topic is derived from ``data.name``; the default
    conversation reuses ``data.name`` (its slug is independent — slug
    uniqueness is per-table).
    """
    # Lazy-imported to keep the api/ import order shallow; conversations
    # doesn't import topics so this isn't strictly cycle-breaking, but
    # the lazy pattern matches rels.py and seed.py.
    from wazzup.api import conversations, rels

    now = datetime.now(UTC).isoformat()
    details_json = json.dumps(data.details.model_dump())

    last_error: IntegrityError | None = None
    for _ in range(_MAX_SLUG_RETRIES):
        slug = make_slug(db, "topic", data.name, override=data.slug)
        try:
            cursor = db.execute(
                "INSERT INTO topic (name, slug, created_at, updated_at, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (data.name, slug, now, now, details_json),
            )
            topic_id = cursor.lastrowid
            break
        except IntegrityError as e:
            last_error = e
            continue
    else:
        raise last_error if last_error else IntegrityError("create topic: exhausted retries")

    # Auto-default conversation, same transaction.
    conv = conversations._create(db, ConversationCreate(name=data.name))
    rels.add(
        db,
        src_type="conversation", src_id=conv.id,
        tgt_type="topic", tgt_id=topic_id,
        rel_type="in_topic",
    )

    row = db.execute("SELECT * FROM topic WHERE id = ?", (topic_id,)).fetchone()
    return _row_to_topicread(db, row)


def get(db: Connection, id: int) -> TopicRead | None:
    row = db.execute(
        "SELECT * FROM topic WHERE id = ? AND deleted_at IS NULL", (id,)
    ).fetchone()
    return _row_to_topicread(db, row) if row else None


def get_by_slug(db: Connection, slug: str) -> TopicRead | None:
    row = db.execute(
        "SELECT * FROM topic WHERE slug = ? AND deleted_at IS NULL", (slug,)
    ).fetchone()
    return _row_to_topicread(db, row) if row else None


def update(db: Connection, id: int, patch: TopicUpdate) -> TopicRead:
    """PATCH semantics. Caller owns the transaction. Raises NotFound."""
    fields = patch.model_dump(exclude_unset=True)

    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValueError(f"topics.update: unknown fields in patch: {sorted(unknown)}")

    null_violations = [f for f in _NOT_NULL_FIELDS if f in fields and fields[f] is None]
    if null_violations:
        raise ValueError(
            f"topics.update: cannot set NOT NULL field(s) to None: {null_violations}. "
            f"To leave them unchanged, omit them from the patch."
        )

    if "details" in fields:
        fields["details"] = json.dumps(fields["details"])

    fields["updated_at"] = datetime.now(UTC).isoformat()

    set_clause = ", ".join(f"{col} = ?" for col in fields)
    params = list(fields.values()) + [id]

    cursor = db.execute(
        f"UPDATE topic SET {set_clause} WHERE id = ? AND deleted_at IS NULL",
        params,
    )
    if cursor.rowcount == 0:
        raise NotFound(f"topic id={id} not found")

    return get(db, id)


def _delete_primary(db: Connection, id: int, hard: bool = False) -> bool:
    """Delete just the topic row. Returns True iff a row was affected."""
    if hard:
        cursor = db.execute("DELETE FROM topic WHERE id = ?", (id,))
    else:
        now = datetime.now(UTC).isoformat()
        cursor = db.execute(
            "UPDATE topic SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (now, id),
        )
    return cursor.rowcount > 0


def delete(db: Connection, id: int, hard: bool = False) -> None:
    """Soft-delete by default. Cascades via ``api/deletion.cascade_delete``.

    Topic cascade soft-deletes every rel involving the topic (in_topic,
    member_of, etc.) **and** recursively soft-deletes the topic's default
    conversation (which then cascades to its messages and rels). See
    ``docs/MODEL.md``'s cascade table.

    Caller owns the transaction.
    """
    from wazzup.api.deletion import cascade_delete

    report = cascade_delete(db, table="topic", id=id, hard=hard)
    if report.primary == 0:
        raise NotFound(f"topic id={id} not found")


def query(
    db: Connection,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[TopicRead]:
    rows = db.execute(
        "SELECT * FROM topic WHERE deleted_at IS NULL "
        "ORDER BY id LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [_row_to_topicread(db, r) for r in rows]
