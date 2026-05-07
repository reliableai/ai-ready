"""Message CRUD smoke tests — task #11.

Messages are the *exception* in the entity set: no name/slug, links
via rels (belongs_to conversation, sent_by user). Tests verify:

- the dual-rel write is correct (one INSERT into ``message`` + two
  INSERTs into ``rels``)
- ``MessageRead`` is stored-columns-only (no conversation_id /
  sender_id surface)
- ``query(conversation_id=...)`` JOINs through rels correctly
- the HTTP layer overrides ``sender_id`` from ``current_user`` (so
  clients can't impersonate)
- linking to nonexistent conversation/sender raises NotFound
  (the api-layer guard against orphan messages)
"""

import pytest

from wazzup.api import NotFound, conversations, messages, topics, users
from wazzup.models import (
    ConversationCreate,
    MessageCreate,
    MessageUpdate,
    TopicCreate,
    UserCreate,
)


def _seed_alice_and_standup(db):
    """Seed the canonical (alice, standup) pair used by most tests.

    The "standup" conversation is the daily-standup topic's auto-default
    conversation, not a free-floating row. Topics are public in v0.1, so
    this conversation is accessible to any authenticated user — which is
    what the HTTP tests need to satisfy ``conversations.is_accessible_by``.
    """
    alice = users.create(db, UserCreate(name="Alice", type="human"))
    standup_topic = topics.create(db, TopicCreate(name="Daily Standup"))
    standup = conversations.get(db, standup_topic.default_conversation_id)
    return alice, standup


# ----- api-layer -----


def test_create_writes_message_and_two_rels(db):
    """create() inserts the message row + a belongs_to rel + a sent_by rel."""
    alice, standup = _seed_alice_and_standup(db)
    msg = messages.create(db, MessageCreate(
        conversation_id=standup.id,
        sender_id=alice.id,
        text="Good morning!",
    ))
    assert msg.id > 0
    assert msg.text == "Good morning!"

    # The message row exists.
    row = db.execute("SELECT text FROM message WHERE id = ?", (msg.id,)).fetchone()
    assert row["text"] == "Good morning!"

    # belongs_to rel: message → conversation
    belongs_to = db.execute(
        "SELECT tgt_id FROM rels WHERE src_type='message' AND src_id=? "
        "AND rel_type='belongs_to' AND deleted_at IS NULL",
        (msg.id,),
    ).fetchone()
    assert belongs_to is not None
    assert belongs_to["tgt_id"] == standup.id

    # sent_by rel: message → user
    sent_by = db.execute(
        "SELECT tgt_id FROM rels WHERE src_type='message' AND src_id=? "
        "AND rel_type='sent_by' AND deleted_at IS NULL",
        (msg.id,),
    ).fetchone()
    assert sent_by is not None
    assert sent_by["tgt_id"] == alice.id


def test_create_unknown_sender_raises_notfound(db):
    """sender_id not matching a live user → NotFound (api-layer guard)."""
    _, standup = _seed_alice_and_standup(db)
    with pytest.raises(NotFound, match="sender_id=999"):
        messages.create(db, MessageCreate(
            conversation_id=standup.id,
            sender_id=999,
            text="hi",
        ))


def test_create_unknown_conversation_raises_notfound(db):
    """conversation_id not matching a live conversation → NotFound."""
    alice, _ = _seed_alice_and_standup(db)
    with pytest.raises(NotFound, match="conversation_id=999"):
        messages.create(db, MessageCreate(
            conversation_id=999,
            sender_id=alice.id,
            text="hi",
        ))


def test_get_returns_message_without_rel_linked_ids(db):
    """MessageRead is stored-columns-only — no conversation_id/sender_id surface."""
    alice, standup = _seed_alice_and_standup(db)
    msg = messages.create(db, MessageCreate(
        conversation_id=standup.id,
        sender_id=alice.id,
        text="hi",
    ))
    fetched = messages.get(db, msg.id)
    assert fetched is not None
    assert fetched.id == msg.id
    assert fetched.text == "hi"
    # The point of the rels-only design: these fields don't exist on the model.
    assert not hasattr(fetched, "conversation_id")
    assert not hasattr(fetched, "sender_id")


def test_update_text_works(db):
    """Patching text works; updated_at advances."""
    alice, standup = _seed_alice_and_standup(db)
    msg = messages.create(db, MessageCreate(
        conversation_id=standup.id,
        sender_id=alice.id,
        text="original",
    ))
    patched = messages.update(db, msg.id, MessageUpdate(text="edited"))
    assert patched.text == "edited"
    assert patched.updated_at >= msg.updated_at


def test_update_text_none_rejected_at_api_layer(db):
    """MessageUpdate(text=None) triggers the api-layer NOT NULL defense.

    Same pattern as users / conversations / topics — Pydantic accepts
    `text=None` (type is `str | None`), but the schema column is NOT NULL.
    """
    alice, standup = _seed_alice_and_standup(db)
    msg = messages.create(db, MessageCreate(
        conversation_id=standup.id,
        sender_id=alice.id,
        text="hi",
    ))
    with pytest.raises(ValueError, match="cannot set NOT NULL field"):
        messages.update(db, msg.id, MessageUpdate(text=None))


def test_query_filters_by_conversation(db):
    """query(conversation_id=...) returns only that conversation's messages."""
    alice, standup = _seed_alice_and_standup(db)
    other = conversations._create(db, ConversationCreate(name="Off-topic"))

    m1 = messages.create(db, MessageCreate(
        conversation_id=standup.id, sender_id=alice.id, text="standup msg",
    ))
    messages.create(db, MessageCreate(
        conversation_id=other.id, sender_id=alice.id, text="off-topic msg",
    ))

    standup_msgs = messages.query(db, conversation_id=standup.id)
    assert {m.id for m in standup_msgs} == {m1.id}


# ----- HTTP smoke -----

AUTH_HEADER = {"X-User-Slug": "alice"}


def test_post_messages_body_does_not_require_sender_id(client, db):
    """The HTTP body does NOT require sender_id — it's filled from current_user.

    Regression for the contract bug: previously the route consumed
    MessageCreate directly, which required sender_id; clients got a
    422 even though the server was about to overwrite the field. The
    fix introduced ``MessageCreateRequest`` (in http/messages.py) with
    no sender_id field. This test pins the new contract.
    """
    _, standup = _seed_alice_and_standup(db)
    resp = client.post(
        "/messages",
        headers=AUTH_HEADER,
        json={
            "conversation_id": standup.id,
            "text": "hi",
        },                              # no sender_id
    )
    assert resp.status_code == 201


def test_post_messages_ignores_spoofed_sender_id_in_body(client, db):
    """Defense-in-depth: even if a (legacy) client sends sender_id, it's ignored.

    Pydantic v2's default ``extra="ignore"`` drops the field before
    it reaches the route body. The sent_by rel points at the
    authenticated user (alice), never at the spoofed user (bob).
    """
    alice, standup = _seed_alice_and_standup(db)
    bob = users.create(db, UserCreate(name="Bob", type="human"))

    resp = client.post(
        "/messages",
        headers=AUTH_HEADER,
        json={
            "conversation_id": standup.id,
            "sender_id": bob.id,           # extra field; silently dropped
            "text": "hi from alice",
        },
    )
    assert resp.status_code == 201
    msg_id = resp.json()["id"]

    # The sent_by rel must point at alice (current_user), NOT bob.
    sent_by = db.execute(
        "SELECT tgt_id FROM rels WHERE src_type='message' AND src_id=? "
        "AND rel_type='sent_by' AND deleted_at IS NULL",
        (msg_id,),
    ).fetchone()
    assert sent_by["tgt_id"] == alice.id
    assert sent_by["tgt_id"] != bob.id


def test_post_messages_404_on_unknown_conversation(client, db):
    """POST /messages with bogus conversation_id → 404 via NotFound handler."""
    users.create(db, UserCreate(name="Alice", type="human"))
    resp = client.post(
        "/messages",
        headers=AUTH_HEADER,
        json={"conversation_id": 999, "sender_id": 1, "text": "hi"},
    )
    assert resp.status_code == 404
    assert "conversation_id=999" in resp.json()["detail"]


# ----- GET /messages list (#21) -----


def test_get_messages_with_conversation_filter(client, db):
    """GET /messages?conversation_id=N → live messages in that conversation only."""
    alice, standup = _seed_alice_and_standup(db)
    other = conversations._create(db, ConversationCreate(name="Off-topic"))

    m1 = messages.create(db, MessageCreate(
        conversation_id=standup.id, sender_id=alice.id, text="standup",
    ))
    messages.create(db, MessageCreate(
        conversation_id=other.id, sender_id=alice.id, text="off-topic",
    ))

    resp = client.get(
        f"/messages?conversation_id={standup.id}",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    assert {m["id"] for m in resp.json()} == {m1.id}


def test_get_messages_requires_conversation_id(client, db):
    """conversation_id is a required query param — no 'all messages' fallthrough.

    Mirrors the api-layer decision documented in ``api/messages.query``:
    a global listing would surprise callers who expected a filtered view.
    FastAPI auto-422s when a required query param is missing.
    """
    _seed_alice_and_standup(db)
    resp = client.get("/messages", headers=AUTH_HEADER)
    assert resp.status_code == 422


def test_get_messages_with_sender_filter(client, db):
    """?sender_id= narrows within a conversation."""
    alice, standup = _seed_alice_and_standup(db)
    bob = users.create(db, UserCreate(name="Bob", type="human"))

    messages.create(db, MessageCreate(
        conversation_id=standup.id, sender_id=alice.id, text="from alice",
    ))
    m_bob = messages.create(db, MessageCreate(
        conversation_id=standup.id, sender_id=bob.id, text="from bob",
    ))

    resp = client.get(
        f"/messages?conversation_id={standup.id}&sender_id={bob.id}",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    assert {m["id"] for m in resp.json()} == {m_bob.id}


def test_get_messages_rejects_negative_pagination(client, db):
    """Negative ``limit`` / ``offset`` → 422 at the HTTP boundary.

    Regression: SQLite treats ``LIMIT -1`` as "no limit" and ``OFFSET -1``
    as 0, silently widening / shifting the result set. The HTTP route
    catches it via ``Query(ge=…)`` so a misbehaving client gets a
    clear 422 instead of unbounded results.
    """
    alice, standup = _seed_alice_and_standup(db)

    # Negative limit: 422.
    resp = client.get(
        f"/messages?conversation_id={standup.id}&limit=-1",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 422

    # Negative offset: 422.
    resp = client.get(
        f"/messages?conversation_id={standup.id}&offset=-1",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 422

    # Zero limit also rejected (le bound is 1).
    resp = client.get(
        f"/messages?conversation_id={standup.id}&limit=0",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 422

    # Above-cap limit: 422 (le=200).
    resp = client.get(
        f"/messages?conversation_id={standup.id}&limit=99999",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 422
