"""Conversation HTTP routes — protected router.

Conversations are *internal plumbing* (see ``docs/MODEL.md``) — the UI
never shows them as a top-level concept. The only route here is the
one the UI actually needs: list the messages of a given conversation
by slug. Everything else (POST/list/by-slug) was deleted with the
model shape change in v0.2 because there's no public path to *create*
a conversation: ``topics.create()`` and ``conversations.get_or_create_dm()``
are the only producers.
"""

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query

from wazzup.api import NotFound
from wazzup.api import conversations as conversations_api
from wazzup.api import messages as messages_api
from wazzup.http.dependencies import current_user, get_db, require_auth
from wazzup.models import MessageReadInConversation, UserRead

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
    dependencies=[Depends(require_auth)],
)


@router.delete("/{slug}/messages", status_code=204)
def clear_messages_in_conversation(
    slug: str,
    db: Connection = Depends(get_db),
    me: UserRead = Depends(current_user),
) -> None:
    """Clear all messages in a DM conversation. Restricted to DMs.

    A public-topic conversation is shared by everyone authenticated;
    one user clearing it would wipe everyone else's content. So this
    route hard-rejects (403) when the conversation has an ``in_topic``
    rel. DMs (no in_topic, two participates_in rels) are the only
    shape this works on, and the access check then ensures only the
    two participants can clear their own thread.

    Soft-delete by default (each message gets ``deleted_at`` set; the
    sent_by + belongs_to rels are cascade-soft-deleted alongside).
    Returns 204 No Content.
    """
    conv = conversations_api.get_by_slug(db, slug)
    if conv is None:
        raise NotFound(f"conversation slug={slug!r} not found")
    if not conversations_api.is_accessible_by(
        db, conversation_id=conv.id, user_id=me.id,
    ):
        raise HTTPException(403, "not a participant of this conversation")
    # Reject if this is a topic-default conversation. Public history
    # isn't one user's to clear.
    if conversations_api.get_topic_id(db, conv.id) is not None:
        raise HTTPException(
            403, "cannot clear messages in a public topic conversation",
        )
    conversations_api.clear_messages(db, conversation_id=conv.id)


@router.get("/{slug}/messages", response_model=list[MessageReadInConversation])
def list_messages_in_conversation(
    slug: str,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Connection = Depends(get_db),
    me: UserRead = Depends(current_user),
) -> list[MessageReadInConversation]:
    """List live messages in a conversation, oldest first, with senders.

    The slug is resolved to a conversation_id (404 if no live match);
    then ``messages.query_with_senders(conversation_id=...)`` JOINs
    through ``belongs_to`` (for the conversation filter) and
    ``sent_by`` (for the sender denormalization). Default page size
    is 20 (smaller than the entity-list 50; messages are higher-volume).

    Access: the caller must pass ``conversations.is_accessible_by`` —
    a topic-default conversation is open to anyone today (topics are
    public in v0.1), but a DM only admits its two participants. Non-
    participant on a DM → 403, NOT 404; existence isn't secret.

    Response shape: ``MessageReadInConversation`` (controlled
    denormalization — see ``models.py``). Each item carries the stored
    columns *plus* ``sender_id`` / ``sender_slug`` / ``sender_name``
    so the UI can render multi-party threads without an N+1 fetch.

    This is the route the UI's chat view hits — for both topic-default
    conversations (loaded after ``GET /topics/{slug}``) and DMs
    (loaded after ``POST /dms/{peer_slug}``).
    """
    conv = conversations_api.get_by_slug(db, slug)
    if conv is None:
        raise NotFound(f"conversation slug={slug!r} not found")
    if not conversations_api.is_accessible_by(
        db, conversation_id=conv.id, user_id=me.id,
    ):
        raise HTTPException(403, "not a participant of this conversation")
    return messages_api.query_with_senders(
        db, conversation_id=conv.id, limit=limit, offset=offset,
    )
