"""Topic CRUD tests + v0.2 model-shape additions.

Three things under test:

1. The base topic CRUD shape (same as conversations / users).
2. The v0.2 invariant: ``topics.create()`` auto-creates the default
   conversation in the same transaction and writes the ``in_topic`` rel.
3. The drift-detection path: if a topic somehow has no default
   conversation, ``topics.get*()`` calls ``deviation()`` (raises in
   strict mode; surfaces sentinel values in lax mode).
"""


import pytest

from wazzup.api import conversations, rels, topics, users
from wazzup.models import TopicCreate, TopicUpdate, UserCreate

AUTH_HEADER = {"X-User-Slug": "alice"}


# ----- base CRUD -----


def test_create_round_trips(db):
    t = topics.create(db, TopicCreate(name="Engineering"))
    assert t.id > 0
    assert t.name == "Engineering"
    assert t.slug == "engineering"


def test_get_by_slug(db):
    t = topics.create(db, TopicCreate(name="Engineering"))
    assert topics.get_by_slug(db, "engineering").id == t.id
    assert topics.get_by_slug(db, "nope") is None


def test_update_name_none_rejected_at_api_layer(db):
    """Same NOT NULL defense as users / conversations."""
    t = topics.create(db, TopicCreate(name="Engineering"))
    with pytest.raises(ValueError, match="cannot set NOT NULL field"):
        topics.update(db, t.id, TopicUpdate(name=None))


# ----- auto-default conversation invariant -----


def test_create_topic_auto_creates_default_conversation(db):
    """``topics.create()`` writes a conversation row + an in_topic rel."""
    t = topics.create(db, TopicCreate(name="Engineering"))

    # The conversation row exists, named after the topic.
    assert t.default_conversation_slug == "engineering"
    assert t.default_conversation_id > 0
    conv = conversations.get(db, t.default_conversation_id)
    assert conv is not None
    assert conv.name == "Engineering"
    assert conv.slug == "engineering"

    # The in_topic rel exists.
    rs = rels.list(
        db,
        rel_type="in_topic",
        src_type="conversation", src_id=conv.id,
        tgt_type="topic", tgt_id=t.id,
    )
    assert len(rs) == 1


def test_get_topic_returns_default_conversation_slug(db):
    """``get_by_slug`` re-populates the default conversation slug from rels."""
    created = topics.create(db, TopicCreate(name="Engineering"))
    fetched = topics.get_by_slug(db, "engineering")
    assert fetched is not None
    assert fetched.default_conversation_slug == created.default_conversation_slug
    assert fetched.default_conversation_id == created.default_conversation_id


def test_query_populates_default_conversation_slug_for_each_row(db):
    """``query()`` populates the slug on every TopicRead in the result list."""
    topics.create(db, TopicCreate(name="Engineering"))
    topics.create(db, TopicCreate(name="Random"))
    listed = topics.query(db)
    assert {(t.slug, t.default_conversation_slug) for t in listed} == {
        ("engineering", "engineering"),
        ("random", "random"),
    }


def test_topic_missing_default_conversation_raises_in_strict_mode(db, monkeypatch):
    """If the in_topic rel is missing at read time, deviation fires.

    Strict mode raises ``UnexpectedDeviation``; lax mode logs and surfaces
    the ``"<missing>"`` slug + ``0`` id sentinels. We force strict mode for
    this test via ``logging_setup.STRICT_MODE`` (the module-level constant
    the ``deviation()`` helper consults).
    """
    from wazzup import logging_setup

    t = topics.create(db, TopicCreate(name="Engineering"))
    # Soft-delete the in_topic rel by hand to simulate the drift state.
    matching = rels.list(
        db,
        rel_type="in_topic",
        src_type="conversation",
        tgt_type="topic", tgt_id=t.id,
    )
    assert len(matching) == 1
    rels.remove(db, matching[0].id)

    # Force strict mode for the duration of the test.
    monkeypatch.setattr(logging_setup, "STRICT_MODE", True)

    with pytest.raises(
        logging_setup.UnexpectedDeviation,
        match="topic missing default conversation",
    ):
        topics.get_by_slug(db, "engineering")


def test_topic_missing_default_conversation_surfaces_sentinel_in_lax_mode(db, monkeypatch):
    """In lax mode the read returns the sentinel values rather than raising."""
    from wazzup import logging_setup

    t = topics.create(db, TopicCreate(name="Engineering"))
    matching = rels.list(
        db,
        rel_type="in_topic",
        src_type="conversation",
        tgt_type="topic", tgt_id=t.id,
    )
    rels.remove(db, matching[0].id)

    monkeypatch.setattr(logging_setup, "STRICT_MODE", False)

    drift = topics.get_by_slug(db, "engineering")
    assert drift is not None
    assert drift.default_conversation_slug == "<missing>"
    assert drift.default_conversation_id == 0


# ----- HTTP smoke -----


def test_post_topics_creates_201(client, db):
    """POST /topics → 201 + TopicRead with default_conversation_slug."""
    users.create(db, UserCreate(name="Alice", type="human"))
    resp = client.post(
        "/topics",
        headers=AUTH_HEADER,
        json={"name": "Engineering"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Engineering"
    assert body["slug"] == "engineering"
    assert body["default_conversation_slug"] == "engineering"
    assert body["default_conversation_id"] > 0


def test_get_topics_returns_list_with_slugs(client, db):
    """GET /topics → live topics; each row carries its default conversation slug."""
    users.create(db, UserCreate(name="Alice", type="human"))
    topics.create(db, TopicCreate(name="Engineering"))
    topics.create(db, TopicCreate(name="Random"))

    resp = client.get("/topics", headers=AUTH_HEADER)
    assert resp.status_code == 200
    rows = resp.json()
    assert {(t["slug"], t["default_conversation_slug"]) for t in rows} == {
        ("engineering", "engineering"),
        ("random", "random"),
    }


def test_get_topic_by_slug_404_for_unknown(client, db):
    users.create(db, UserCreate(name="Alice", type="human"))
    resp = client.get("/topics/nope", headers=AUTH_HEADER)
    assert resp.status_code == 404
