"""Conversation CRUD — internal plumbing for messages.

**Boundary rule (see ``docs/MODEL.md``).** Conversations are not user-
facing — the UI only shows users (DMs) and topics (public rooms). Every
conversation is either a topic-default (one ``in_topic`` rel pointing
at a topic) or a DM (exactly two ``participates_in`` user rels and no
``in_topic`` rel). To enforce that invariant by *boundary* rather than
by runtime check, this module exposes only two public producers:

- ``topics.create()`` — creates a topic-default conversation alongside
  the topic, in the same transaction.
- ``conversations.get_or_create_dm()`` — finds or creates a 1:1 DM.

The low-level row insert lives in the module-private ``_create()``.
Don't add a public ``create()`` back; the absence of a public
producer is the contract.

Differences from users (because conversations have a smaller schema):

- No ``type`` field, no ``persona`` column.
- ``_UPDATABLE_FIELDS = {"name", "details"}`` — no type/persona to
  patch.

Everything else (caller-owns-transaction, bounded retry on
slug-collision race, ``_row_to_conversationread`` helper, NotFound
on update/delete, soft-delete-aware reads) is identical to users.py.

Cascade through rels and recursive message-cascade live in
``api/deletion.py`` (single source of truth).
"""

import json
from datetime import UTC, datetime
from sqlite3 import Connection, IntegrityError, Row

from wazzup.api import NotFound
from wazzup.api.slugs import make_slug
from wazzup.models import ConversationCreate, ConversationRead, ConversationUpdate

_UPDATABLE_FIELDS = {"name", "details"}

# Subset of _UPDATABLE_FIELDS whose columns are NOT NULL in the schema.
# Same defense as users.update — see nullability rule in models.py.
# ConversationUpdate.name is typed `str | None = None` so Pydantic accepts
# `name=None`; without this guard it would round-trip to `name = NULL`
# and surface as a misleading IntegrityError instead of a friendly
# api-layer ValueError.
_NOT_NULL_FIELDS = {"name"}

_MAX_SLUG_RETRIES = 5


def _row_to_conversationread(row: Row) -> ConversationRead:
    """sqlite3.Row → ConversationRead. Same json.loads pattern as users.py."""
    raw = dict(row)
    raw["details"] = json.loads(raw["details"]) if raw["details"] else {}
    return ConversationRead.model_validate(raw)


def _create(db: Connection, data: ConversationCreate) -> ConversationRead:
    """Module-private row insert — only ``topics.create()`` and
    ``conversations.get_or_create_dm()`` should call this.

    Slug is server-derived from ``data.name``; explicit ``data.slug``
    overrides if provided. Same silent-suffix-on-collision behavior
    as users; same TODO #19 caveat for explicit-override conflicts.

    Caller owns the transaction.
    """
    now = datetime.now(UTC).isoformat()
    details_json = json.dumps(data.details.model_dump())

    last_error: IntegrityError | None = None
    for _ in range(_MAX_SLUG_RETRIES):
        slug = make_slug(db, "conversation", data.name, override=data.slug)
        try:
            cursor = db.execute(
                "INSERT INTO conversation (name, slug, created_at, updated_at, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (data.name, slug, now, now, details_json),
            )
            row = db.execute(
                "SELECT * FROM conversation WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return _row_to_conversationread(row)
        except IntegrityError as e:
            last_error = e
            continue
    raise last_error if last_error else IntegrityError("create conversation: exhausted retries")


def get(db: Connection, id: int) -> ConversationRead | None:
    row = db.execute(
        "SELECT * FROM conversation WHERE id = ? AND deleted_at IS NULL", (id,)
    ).fetchone()
    return _row_to_conversationread(row) if row else None


def get_by_slug(db: Connection, slug: str) -> ConversationRead | None:
    row = db.execute(
        "SELECT * FROM conversation WHERE slug = ? AND deleted_at IS NULL", (slug,)
    ).fetchone()
    return _row_to_conversationread(row) if row else None


def update(db: Connection, id: int, patch: ConversationUpdate) -> ConversationRead:
    """PATCH semantics. Slugs are stable (no ``slug`` field on ConversationUpdate).

    Caller owns the transaction. Raises NotFound if id doesn't match a live row.
    """
    fields = patch.model_dump(exclude_unset=True)

    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValueError(f"conversations.update: unknown fields in patch: {sorted(unknown)}")

    null_violations = [f for f in _NOT_NULL_FIELDS if f in fields and fields[f] is None]
    if null_violations:
        raise ValueError(
            f"conversations.update: cannot set NOT NULL field(s) to None: {null_violations}. "
            f"To leave them unchanged, omit them from the patch."
        )

    if "details" in fields:
        fields["details"] = json.dumps(fields["details"])

    fields["updated_at"] = datetime.now(UTC).isoformat()

    set_clause = ", ".join(f"{col} = ?" for col in fields)
    params = list(fields.values()) + [id]

    cursor = db.execute(
        f"UPDATE conversation SET {set_clause} WHERE id = ? AND deleted_at IS NULL",
        params,
    )
    if cursor.rowcount == 0:
        raise NotFound(f"conversation id={id} not found")

    return get(db, id)


def _delete_primary(db: Connection, id: int, hard: bool = False) -> bool:
    """Delete just the conversation row. Returns True iff a row was affected.

    See ``users._delete_primary`` for the rationale on the split.
    """
    if hard:
        cursor = db.execute("DELETE FROM conversation WHERE id = ?", (id,))
    else:
        now = datetime.now(UTC).isoformat()
        cursor = db.execute(
            "UPDATE conversation SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (now, id),
        )
    return cursor.rowcount > 0


def delete(db: Connection, id: int, hard: bool = False) -> None:
    """Soft-delete by default. Raises NotFound if id doesn't match a live row.

    Cascades via ``api/deletion.cascade_delete`` (#13): soft-deleting a
    conversation also soft-deletes its messages (recursively, including
    *their* rels) and every rel involving the conversation. Hard cascade
    is symmetric.

    Caller owns the transaction.
    """
    from wazzup.api.deletion import cascade_delete

    report = cascade_delete(db, table="conversation", id=id, hard=hard)
    if report.primary == 0:
        raise NotFound(f"conversation id={id} not found")


def get_or_create_dm(
    db: Connection,
    *,
    user_a_id: int,
    user_b_id: int,
) -> ConversationRead:
    """Find or create the 1:1 DM conversation between two users.

    Idempotent and order-invariant: ``get_or_create_dm(a, b)`` and
    ``get_or_create_dm(b, a)`` return the same conversation. Caller
    owns the transaction.

    A DM is identified structurally: a conversation with **exactly two
    distinct ``participates_in`` user rels and no ``in_topic`` rel**.
    The lookup query enforces all three clauses — exactly-two, no-third-
    participant, and no-topic-link — so a 3-person conversation that
    happens to include the same pair won't accidentally match. See
    ``test_get_or_create_dm_does_not_match_three_party_conversation``.

    Raises ``ValueError`` if both ids are the same (no self-DM) and
    ``NotFound`` if either user doesn't exist.
    """
    # Lazy-imported to avoid pulling users at module top — keeps the
    # api/ import order shallow. (We don't strictly need it for cycle
    # avoidance here, but the lazy pattern matches rels.py.)
    from wazzup.api import users

    if user_a_id == user_b_id:
        raise ValueError("get_or_create_dm: cannot DM yourself")

    user_a = users.get(db, user_a_id)
    if user_a is None:
        raise NotFound(f"get_or_create_dm: user id={user_a_id} not found")
    user_b = users.get(db, user_b_id)
    if user_b is None:
        raise NotFound(f"get_or_create_dm: user id={user_b_id} not found")

    # The DM-detection query — see module docstring for the rule.
    # Bound parameters: (a, b, a, b). The two NOT EXISTS sub-selects pin
    # the "exactly-two-participants, no-topic-link" half of the
    # invariant; the GROUP BY + HAVING pins the COUNT(DISTINCT)=2 half.
    row = db.execute(
        """
        SELECT r.tgt_id AS conv_id
        FROM rels r
        WHERE r.rel_type = 'participates_in'
          AND r.tgt_type = 'conversation'
          AND r.src_type = 'user'
          AND r.src_id IN (?, ?)
          AND r.deleted_at IS NULL
        GROUP BY r.tgt_id
        HAVING COUNT(DISTINCT r.src_id) = 2
           AND NOT EXISTS (
             SELECT 1 FROM rels r3
             WHERE r3.tgt_id = r.tgt_id
               AND r3.tgt_type = 'conversation'
               AND r3.rel_type = 'participates_in'
               AND r3.src_id NOT IN (?, ?)
               AND r3.deleted_at IS NULL
           )
           AND NOT EXISTS (
             SELECT 1 FROM rels r2
             WHERE r2.src_type = 'conversation'
               AND r2.src_id = r.tgt_id
               AND r2.rel_type = 'in_topic'
               AND r2.deleted_at IS NULL
           )
        LIMIT 1
        """,
        (user_a_id, user_b_id, user_a_id, user_b_id),
    ).fetchone()

    if row is not None:
        existing = get(db, row["conv_id"])
        if existing is None:
            # The lookup found the rels but the conversation row itself
            # is soft-deleted. Treat as not-found and create a fresh DM
            # below — the rels will be re-added with new ids.
            row = None

    if row is not None:
        return existing

    # No live DM matches — create one. Slug uses alphabetical user.slug
    # ordering for stability; name uses the same ordering for symmetry.
    slug_lo, slug_hi = sorted((user_a.slug, user_b.slug))
    name_lo, name_hi = (
        (user_a.name, user_b.name) if user_a.slug == slug_lo else (user_b.name, user_a.name)
    )
    dm_data = ConversationCreate(
        name=f"{name_lo} ↔ {name_hi}",
        slug=f"dm-{slug_lo}-{slug_hi}",
    )
    conv = _create(db, dm_data)

    # Late import: rels imports api.conversations for FK validation.
    from wazzup.api import rels

    rels.add(
        db,
        src_type="user", src_id=user_a_id,
        tgt_type="conversation", tgt_id=conv.id,
        rel_type="participates_in",
    )
    rels.add(
        db,
        src_type="user", src_id=user_b_id,
        tgt_type="conversation", tgt_id=conv.id,
        rel_type="participates_in",
    )
    return conv


def get_topic_id(db: Connection, conversation_id: int) -> int | None:
    """Return the topic id this conversation belongs to via ``in_topic``,
    or ``None`` if it has no topic linkage (i.e., it's a DM).

    Single source of truth for the topic-vs-DM structural distinction —
    used by ``is_accessible_by`` for authorization and by
    ``api/agents._responders_for`` for dispatch scope.
    """
    row = db.execute(
        "SELECT tgt_id FROM rels "
        "WHERE src_type = 'conversation' AND src_id = ? "
        "  AND rel_type = 'in_topic' AND tgt_type = 'topic' "
        "  AND deleted_at IS NULL "
        "LIMIT 1",
        (conversation_id,),
    ).fetchone()
    return row["tgt_id"] if row else None


def get_participant_ids(db: Connection, conversation_id: int) -> list[int]:
    """User ids of all live ``participates_in`` rels for this conversation.

    For DMs this is exactly two ids; for topic-default conversations it
    can be empty (no participation rels are written for topics today).
    """
    rows = db.execute(
        "SELECT src_id FROM rels "
        "WHERE src_type = 'user' "
        "  AND tgt_type = 'conversation' AND tgt_id = ? "
        "  AND rel_type = 'participates_in' "
        "  AND deleted_at IS NULL "
        "ORDER BY src_id ASC",
        (conversation_id,),
    ).fetchall()
    return [r["src_id"] for r in rows]


def is_accessible_by(
    db: Connection,
    *,
    conversation_id: int,
    user_id: int,
) -> bool:
    """Authorize a user to read or write a conversation.

    Encodes invariant #8 from ``docs/MODEL.md``:

    - **Topic-default conversations** (one ``in_topic`` rel pointing at a
      topic): gated by ``topics.can_access(db, user_id=, topic_id=)``.
      v0.1 returns ``True`` for all authenticated users — topics are
      public. Future private/group topics flip ``can_access`` without
      touching this helper or its call sites.
    - **DMs** (no ``in_topic`` rel): caller must have a live
      ``participates_in`` rel pointing at the conversation.
    - **Anything else** (no in_topic AND no participation): denied. A
      conservative default that protects against malformed conversation
      shapes — they shouldn't exist (boundary enforcement: only
      ``topics.create`` and ``get_or_create_dm`` produce conversations),
      but if they ever do, "deny" is the safe fallback.

    The api layer answers a *structural* question ("is this user a
    participant / member"); the http layer ties it to the authenticated
    caller and translates ``False`` to a 403. Don't read auth headers
    here — keep this callable from tests, CLIs, and future MCP tools
    without a request context.
    """
    # Lazy-imported to avoid pulling topics into module-load time.
    from wazzup.api import topics

    topic_id = get_topic_id(db, conversation_id)
    if topic_id is not None:
        return topics.can_access(db, user_id=user_id, topic_id=topic_id)

    # Otherwise: DM-shaped — caller must be a participant.
    return user_id in get_participant_ids(db, conversation_id)


def query(
    db: Connection,
    *,
    topic_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ConversationRead]:
    """List live conversations. Soft-deleted excluded. Empty list on no match.

    If ``topic_id`` is provided, JOINs through the ``in_topic`` rel
    and returns only conversations belonging to that topic. Same JOIN
    shape as ``messages.query(conversation_id=...)`` — both follow
    from the rels-only design (links live in rels, not as columns).
    Soft-deleted ``in_topic`` rels also hide their conversation from
    the filtered view (cascade visibility).
    """
    if topic_id is None:
        sql = (
            "SELECT * FROM conversation "
            "WHERE deleted_at IS NULL "
            "ORDER BY id LIMIT ? OFFSET ?"
        )
        params: list = [limit, offset]
    else:
        sql = (
            "SELECT c.* FROM conversation c "
            "JOIN rels r "
            "  ON r.src_id = c.id "
            " AND r.src_type = 'conversation' "
            " AND r.rel_type = 'in_topic' "
            " AND r.deleted_at IS NULL "
            "WHERE r.tgt_id = ? AND r.tgt_type = 'topic' "
            "  AND c.deleted_at IS NULL "
            "ORDER BY c.id LIMIT ? OFFSET ?"
        )
        params = [topic_id, limit, offset]
    rows = db.execute(sql, params).fetchall()
    return [_row_to_conversationread(r) for r in rows]
