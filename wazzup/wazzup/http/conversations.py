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

from fastapi import APIRouter, Depends, Query

from wazzup.api import NotFound
from wazzup.api import conversations as conversations_api
from wazzup.api import messages as messages_api
from wazzup.http.dependencies import get_db, require_auth
from wazzup.models import MessageRead

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
    dependencies=[Depends(require_auth)],
)


@router.get("/{slug}/messages", response_model=list[MessageRead])
def list_messages_in_conversation(
    slug: str,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Connection = Depends(get_db),
) -> list[MessageRead]:
    """List live messages in a conversation, oldest first.

    The slug is resolved to a conversation_id (404 if no live match);
    then ``messages.query(conversation_id=...)`` JOINs through rels
    to find belongs_to messages. Default page size is 20 (smaller
    than the entity-list 50; messages are higher-volume).

    This is the route the UI's chat view hits — for both topic-default
    conversations (loaded after ``GET /topics/{slug}``) and DMs
    (loaded after ``POST /dms/{peer_slug}``).
    """
    conv = conversations_api.get_by_slug(db, slug)
    if conv is None:
        raise NotFound(f"conversation slug={slug!r} not found")
    return messages_api.query(
        db, conversation_id=conv.id, limit=limit, offset=offset,
    )
