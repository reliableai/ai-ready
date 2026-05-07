"""Message HTTP routes — protected router.

Messages have no slug; routes use ids. Two routes for the smoke slice:
POST + GET-by-id. The conversation-scoped listing route
(``GET /conversations/{slug}/messages``) is a follow-up (TODO #21).

----------------------------------------------------------------------
WHY A ROUTE-LOCAL REQUEST MODEL (``MessageCreateRequest``)?
----------------------------------------------------------------------

The api-layer shape (``MessageCreate`` in ``models.py``) requires
``sender_id`` — that's how the api thinks: "give me everything I
need to write the message + 2 rels". But on the *HTTP* side we
*never* trust a client-supplied ``sender_id``: the sender is whoever
the auth dep produces. So if the route consumed ``MessageCreate``
directly, FastAPI would 422 a request that omitted ``sender_id`` —
even though the server is about to overwrite it with
``current_user.id``. The wire contract should not require a field
the server intentionally discards.

The fix is the symmetric pattern to the ``MessageRead`` decision
documented in ``models.py``: when a route's contract differs from
the api's, the route defines its own shape. ``MessageCreateRequest``
lives here (HTTP-layer concern) and is adapted into ``MessageCreate``
inside the handler.

This also has a nice side-effect: any extra field in the JSON body
(``sender_id`` or otherwise) is silently dropped by Pydantic v2's
default ``extra="ignore"``, so old clients that still send
``sender_id`` won't break — the field just doesn't reach the api.
"""

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from wazzup.api import NotFound
from wazzup.api import conversations as conversations_api
from wazzup.api import messages as messages_api
from wazzup.http.dependencies import current_user, get_db, require_auth
from wazzup.models import MessageCreate, MessageDetails, MessageRead, UserRead


def _require_access(db: Connection, *, conversation_id: int, user_id: int) -> None:
    """Raise 403 if the user can't access the conversation. Helper used by
    every route in this module that addresses messages by conversation."""
    if not conversations_api.is_accessible_by(
        db, conversation_id=conversation_id, user_id=user_id,
    ):
        raise HTTPException(403, "not a participant of this conversation")

router = APIRouter(
    prefix="/messages",
    tags=["messages"],
    dependencies=[Depends(require_auth)],
)


class MessageCreateRequest(BaseModel):
    """HTTP body for POST /messages. ``sender_id`` is intentionally
    absent — the route fills it from ``current_user``."""

    conversation_id: int
    text: str = Field(min_length=1)
    details: MessageDetails = Field(default_factory=MessageDetails)


@router.post("", status_code=201, response_model=MessageRead)
def create_message(
    body: MessageCreateRequest,
    db: Connection = Depends(get_db),
    me: UserRead = Depends(current_user),
) -> MessageRead:
    """Create a message. ``sender_id`` is set from ``current_user`` —
    not in the request body, by design (see module docstring).

    Access: the caller must pass ``conversations.is_accessible_by``
    on the target conversation. Non-participant on a DM → 403. Without
    this, any authenticated user could *write* into anyone's DM by
    guessing the conversation id (symmetric to the read break).
    """
    # Existence resolution: surface a 404 (matches the api-level
    # NotFound that messages_api.create would otherwise raise) BEFORE
    # the access check, so a typo'd id reads as "not found" rather than
    # "denied". The access check then runs only on a real conversation.
    if conversations_api.get(db, body.conversation_id) is None:
        raise NotFound(f"conversation_id={body.conversation_id} not found")
    _require_access(db, conversation_id=body.conversation_id, user_id=me.id)

    data = MessageCreate(
        conversation_id=body.conversation_id,
        sender_id=me.id,
        text=body.text,
        details=body.details,
    )
    return messages_api.create(db, data)


@router.get("", response_model=list[MessageRead])
def list_messages(
    conversation_id: int,
    sender_id: int | None = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Connection = Depends(get_db),
    me: UserRead = Depends(current_user),
) -> list[MessageRead]:
    """List live messages, filtered by conversation. Optional sender filter.

    ``conversation_id`` is a **required** query param — there's no "all
    messages" listing in the api layer. The decision is documented in
    ``api/messages.query``: a wide-open list is rarely what callers
    actually want, so the api forces the filter rather than fall
    through to ``conversation_id IS NULL`` semantics.

    Pagination: ``?limit=&offset=``, default ``limit=20`` (smaller
    than entity-list defaults; messages are higher-volume).

    Access: the caller must pass ``conversations.is_accessible_by``
    on ``conversation_id``. Non-participant on a DM → 403. Note this
    forces existence resolution before the query, so a typo'd id now
    surfaces a 404 instead of an empty array — that's a behavior
    change documented in ``tests/tests.md``.

    A nested view of the same data lives at
    ``GET /conversations/{slug}/messages``, which resolves the slug
    via ``conversations.get_by_slug`` before querying — use that when
    you have a slug, this when you have an id. Both call into the
    same ``messages_api.query`` after the same access check.
    """
    if conversations_api.get(db, conversation_id) is None:
        raise NotFound(f"conversation_id={conversation_id} not found")
    _require_access(db, conversation_id=conversation_id, user_id=me.id)
    return messages_api.query(
        db,
        conversation_id=conversation_id,
        sender_id=sender_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{id}", response_model=MessageRead)
def get_message(
    id: int,
    db: Connection = Depends(get_db),
    me: UserRead = Depends(current_user),
) -> MessageRead:
    """Look up a live message by id. 404 if absent or soft-deleted.

    ``id: int`` makes FastAPI auto-422 on a non-numeric path param.

    Access: after resolving the message, the route looks up its
    ``belongs_to`` conversation via the rel and runs the same access
    check as the listing routes. Non-participant on a DM → 403.
    """
    msg = messages_api.get(db, id)
    if msg is None:
        raise NotFound(f"message id={id} not found")
    conv_id = _belongs_to_conversation_id(db, message_id=id)
    if conv_id is None:
        # No belongs_to rel = orphaned message. Treat as not-found at
        # the http layer; the api layer should never produce one of
        # these (messages.create writes the rel atomically), so this
        # is the conservative path for a structural drift.
        raise NotFound(f"message id={id} not found")
    _require_access(db, conversation_id=conv_id, user_id=me.id)
    return msg


def _belongs_to_conversation_id(db: Connection, *, message_id: int) -> int | None:
    """Find the conversation a message ``belongs_to`` via its rel.

    Lives here (not in api/messages) because nothing else in the
    codebase needs it yet — promote when a third caller appears. The
    rel was written by ``messages.create`` alongside the message row.
    """
    row = db.execute(
        "SELECT tgt_id FROM rels "
        "WHERE src_type = 'message' AND src_id = ? "
        "  AND rel_type = 'belongs_to' AND tgt_type = 'conversation' "
        "  AND deleted_at IS NULL "
        "LIMIT 1",
        (message_id,),
    ).fetchone()
    return row["tgt_id"] if row else None
