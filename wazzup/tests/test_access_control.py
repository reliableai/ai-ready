"""Conversation access-control tests.

Pins the rule from ``docs/MODEL.md`` invariant #8: a user may read or
write a conversation iff it's a topic-default they're allowed to see
(today: any topic — public for v0.1) OR a DM they're a participant of.

Four routes go through ``conversations.is_accessible_by``:

- ``GET /conversations/{slug}/messages``
- ``GET /messages?conversation_id=``
- ``GET /messages/{id}``
- ``POST /messages``

For each, three cases:

1. Topic-default conversation → any authenticated user gets 200/201.
   (Confirms the helper doesn't over-deny on the public path.)
2. DM, caller IS a participant → 200/201.
3. DM, caller is NOT a participant → 403.

The tests are deliberately scoped to the access dimension; the
content-shape assertions are pinned in ``test_messages.py`` and
``test_conversations.py``.
"""

from wazzup.api import conversations, messages, topics, users
from wazzup.models import (
    MessageCreate,
    TopicCreate,
    UserCreate,
)


def _seed_three_users_and_dm(db):
    """Alice, Curie (DM partners), Bob (the outsider).

    Returns ((alice_id, curie_id, bob_id), dm_conversation).
    """
    alice = users.create(db, UserCreate(name="Alice", slug="alice", type="human"))
    curie = users.create(db, UserCreate(name="Curie", slug="curie", type="human"))
    bob = users.create(db, UserCreate(name="Bob", slug="bob", type="human"))
    dm = conversations.get_or_create_dm(db, user_a_id=alice.id, user_b_id=curie.id)
    return (alice.id, curie.id, bob.id), dm


def _seed_topic_with_message(db, sender_id):
    """Public topic, default conversation, one seeded message from sender."""
    eng = topics.create(db, TopicCreate(name="Engineering"))
    conv_id = topics.get_default_conversation_id(db, eng.id)
    msg = messages.create(db, MessageCreate(
        conversation_id=conv_id, sender_id=sender_id, text="public post",
    ))
    return eng, conv_id, msg


# ----- GET /conversations/{slug}/messages -----


def test_get_conv_messages_topic_default_open_to_anyone(client, db):
    """Any authenticated user can read a topic-default conversation's messages."""
    (alice_id, _, _), _ = _seed_three_users_and_dm(db)
    eng, _, _ = _seed_topic_with_message(db, alice_id)

    # Bob is not in the topic's default conversation in any structural sense,
    # but topics are public — he should still read.
    resp = client.get(
        f"/conversations/{eng.default_conversation_slug}/messages",
        headers={"X-User-Slug": "bob"},
    )
    assert resp.status_code == 200
    assert [m["text"] for m in resp.json()] == ["public post"]


def test_get_conv_messages_dm_participant_allowed(client, db):
    """A participant of a DM can read its messages."""
    (alice_id, curie_id, _), dm = _seed_three_users_and_dm(db)
    messages.create(db, MessageCreate(
        conversation_id=dm.id, sender_id=alice_id, text="hello curie",
    ))

    resp = client.get(
        f"/conversations/{dm.slug}/messages",
        headers={"X-User-Slug": "curie"},
    )
    assert resp.status_code == 200
    assert [m["text"] for m in resp.json()] == ["hello curie"]


def test_get_conv_messages_dm_non_participant_denied(client, db):
    """A non-participant gets 403 on a DM (the original bug)."""
    (alice_id, _, _), dm = _seed_three_users_and_dm(db)
    messages.create(db, MessageCreate(
        conversation_id=dm.id, sender_id=alice_id, text="private to curie",
    ))

    resp = client.get(
        f"/conversations/{dm.slug}/messages",
        headers={"X-User-Slug": "bob"},
    )
    assert resp.status_code == 403
    assert "participant" in resp.json()["detail"].lower()


# ----- GET /messages?conversation_id= -----


def test_get_messages_topic_default_open_to_anyone(client, db):
    (alice_id, _, _), _ = _seed_three_users_and_dm(db)
    _, conv_id, _ = _seed_topic_with_message(db, alice_id)

    resp = client.get(
        f"/messages?conversation_id={conv_id}",
        headers={"X-User-Slug": "bob"},
    )
    assert resp.status_code == 200
    assert [m["text"] for m in resp.json()] == ["public post"]


def test_get_messages_dm_participant_allowed(client, db):
    (alice_id, _, _), dm = _seed_three_users_and_dm(db)
    messages.create(db, MessageCreate(
        conversation_id=dm.id, sender_id=alice_id, text="hello",
    ))
    resp = client.get(
        f"/messages?conversation_id={dm.id}",
        headers={"X-User-Slug": "curie"},
    )
    assert resp.status_code == 200


def test_get_messages_dm_non_participant_denied(client, db):
    (alice_id, _, _), dm = _seed_three_users_and_dm(db)
    messages.create(db, MessageCreate(
        conversation_id=dm.id, sender_id=alice_id, text="secret",
    ))
    resp = client.get(
        f"/messages?conversation_id={dm.id}",
        headers={"X-User-Slug": "bob"},
    )
    assert resp.status_code == 403


def test_get_messages_404_for_unknown_conversation_id(client, db):
    """Now-404 (was previously empty array).

    The access check forces conversation existence resolution, so a
    typo'd id can't pretend to be an empty conversation anymore.
    """
    _seed_three_users_and_dm(db)
    resp = client.get(
        "/messages?conversation_id=99999",
        headers={"X-User-Slug": "bob"},
    )
    assert resp.status_code == 404


# ----- GET /messages/{id} -----


def test_get_message_by_id_topic_default_open_to_anyone(client, db):
    (alice_id, _, _), _ = _seed_three_users_and_dm(db)
    _, _, msg = _seed_topic_with_message(db, alice_id)
    resp = client.get(
        f"/messages/{msg.id}",
        headers={"X-User-Slug": "bob"},
    )
    assert resp.status_code == 200


def test_get_message_by_id_dm_participant_allowed(client, db):
    (alice_id, _, _), dm = _seed_three_users_and_dm(db)
    msg = messages.create(db, MessageCreate(
        conversation_id=dm.id, sender_id=alice_id, text="hi",
    ))
    resp = client.get(
        f"/messages/{msg.id}",
        headers={"X-User-Slug": "curie"},
    )
    assert resp.status_code == 200


def test_get_message_by_id_dm_non_participant_denied(client, db):
    (alice_id, _, _), dm = _seed_three_users_and_dm(db)
    msg = messages.create(db, MessageCreate(
        conversation_id=dm.id, sender_id=alice_id, text="hi",
    ))
    resp = client.get(
        f"/messages/{msg.id}",
        headers={"X-User-Slug": "bob"},
    )
    assert resp.status_code == 403


# ----- POST /messages -----


def test_post_message_topic_default_open_to_anyone(client, db):
    """Any authenticated user can post into a public topic's default conversation."""
    _seed_three_users_and_dm(db)
    eng = topics.create(db, TopicCreate(name="Engineering"))
    resp = client.post(
        "/messages",
        headers={"X-User-Slug": "bob"},
        json={"conversation_id": eng.default_conversation_id, "text": "hi from bob"},
    )
    assert resp.status_code == 201


def test_post_message_dm_participant_allowed(client, db):
    (_, _, _), dm = _seed_three_users_and_dm(db)
    resp = client.post(
        "/messages",
        headers={"X-User-Slug": "curie"},
        json={"conversation_id": dm.id, "text": "ack"},
    )
    assert resp.status_code == 201


def test_post_message_dm_non_participant_denied(client, db):
    """The symmetric write-side bug: Bob must not be able to post into Alice ↔ Curie's DM."""
    (_, _, _), dm = _seed_three_users_and_dm(db)
    resp = client.post(
        "/messages",
        headers={"X-User-Slug": "bob"},
        json={"conversation_id": dm.id, "text": "intrusion"},
    )
    assert resp.status_code == 403
