"""Topic HTTP routes — protected router.

Topics are the public-room half of the app's user-facing surface
(users + topics; conversations are internal plumbing). ``TopicRead``
carries the topic's auto-default conversation slug so the UI can
load messages without a second round-trip.
"""

from sqlite3 import Connection

from fastapi import APIRouter, Depends, Query

from wazzup.api import NotFound
from wazzup.api import topics as topics_api
from wazzup.http.dependencies import get_db, require_auth
from wazzup.models import TopicCreate, TopicRead

router = APIRouter(
    prefix="/topics",
    tags=["topics"],
    dependencies=[Depends(require_auth)],
)


@router.post("", status_code=201, response_model=TopicRead)
def create_topic(
    body: TopicCreate,
    db: Connection = Depends(get_db),
) -> TopicRead:
    """Create a topic and (in the same transaction) its default conversation.

    Returns the topic with ``default_conversation_slug`` populated so the
    caller can immediately load or post into the topic without an extra
    request.
    """
    return topics_api.create(db, body)


@router.get("", response_model=list[TopicRead])
def list_topics(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Connection = Depends(get_db),
) -> list[TopicRead]:
    """List live topics. Pagination via ``?limit=`` (1..200) and ``?offset=`` (≥0)."""
    return topics_api.query(db, limit=limit, offset=offset)


@router.get("/{slug}", response_model=TopicRead)
def get_topic_by_slug(
    slug: str,
    db: Connection = Depends(get_db),
) -> TopicRead:
    topic = topics_api.get_by_slug(db, slug)
    if topic is None:
        raise NotFound(f"topic slug={slug!r} not found")
    return topic
