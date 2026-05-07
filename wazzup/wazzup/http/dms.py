"""Direct-message HTTP routes — protected router.

Single route: ``POST /dms/{peer_slug}`` opens or creates the 1:1 DM
between the authenticated user and the named peer. Idempotent — same
peer twice returns the same conversation. The UI calls this when a
user clicks a person in the People sidebar.

Why ``POST`` and not ``GET``? The route may *create* a conversation
on the first call. Idempotent-but-creating is a classic POST shape;
GET would be misleading (a cached GET wouldn't ever fire the
side effect).
"""

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException

from wazzup.api import NotFound
from wazzup.api import conversations as conversations_api
from wazzup.api import users as users_api
from wazzup.http.dependencies import current_user, get_db, require_auth
from wazzup.models import ConversationRead, UserRead

router = APIRouter(
    prefix="/dms",
    tags=["dms"],
    dependencies=[Depends(require_auth)],
)


@router.post("/{peer_slug}", response_model=ConversationRead)
def open_dm(
    peer_slug: str,
    db: Connection = Depends(get_db),
    me: UserRead = Depends(current_user),
) -> ConversationRead:
    """Open or create the DM with ``peer_slug``. Returns the conversation.

    - 404 if ``peer_slug`` doesn't match a live user.
    - 400 if ``peer_slug`` is the caller's own slug (no self-DM).
    - 200 + ``ConversationRead`` on success (existing or newly-created).
    """
    if peer_slug == me.slug:
        raise HTTPException(400, "cannot DM yourself")
    peer = users_api.get_by_slug(db, peer_slug)
    if peer is None:
        raise NotFound(f"user slug={peer_slug!r} not found")
    return conversations_api.get_or_create_dm(
        db, user_a_id=me.id, user_b_id=peer.id,
    )
