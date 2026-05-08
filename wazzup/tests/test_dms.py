"""DM HTTP tests.

Two surfaces, both via the FastAPI ``client`` fixture:

- ``POST /dms/{peer_slug}`` opens or creates the 1:1 DM. Idempotent
  (same peer twice → same conversation), 404 on unknown peer, 400 on
  self-DM.
- The api-layer ``conversations.get_or_create_dm`` is exercised in
  ``test_conversations.py``; here we just verify the http surface
  routes correctly through it.
"""

from wazzup.api import users
from wazzup.models import UserCreate

AUTH_HEADER = {"X-User-Slug": "alice"}


def _seed_alice_and_curie(db):
    """Seed users with explicit slugs so the auth header `X-User-Slug: alice` lines up."""
    users.create(db, UserCreate(name="Alice Smith", slug="alice", type="human"))
    users.create(db, UserCreate(
        name="Marie Curie", slug="curie", type="agent", persona="Quiet rigor.",
    ))


def test_post_dms_returns_conversation(client, db):
    """POST /dms/{peer_slug} → 200 + ConversationRead."""
    _seed_alice_and_curie(db)
    resp = client.post("/dms/curie", headers=AUTH_HEADER)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] > 0
    # Slug uses alphabetical user.slug ordering: alice < curie.
    assert body["slug"] == "dm-alice-curie"


def test_post_dms_idempotent(client, db):
    """Calling twice with the same peer returns the same conversation id."""
    _seed_alice_and_curie(db)
    a = client.post("/dms/curie", headers=AUTH_HEADER).json()
    b = client.post("/dms/curie", headers=AUTH_HEADER).json()
    assert a["id"] == b["id"]


def test_post_dms_404_on_unknown_peer(client, db):
    """Unknown peer slug → 404 via the NotFound handler."""
    _seed_alice_and_curie(db)
    resp = client.post("/dms/no-one", headers=AUTH_HEADER)
    assert resp.status_code == 404
    assert "no-one" in resp.json()["detail"]


def test_post_dms_400_on_self_dm(client, db):
    """peer_slug == authenticated user's slug → 400 'cannot DM yourself'."""
    _seed_alice_and_curie(db)
    resp = client.post("/dms/alice", headers=AUTH_HEADER)
    assert resp.status_code == 400
    assert "yourself" in resp.json()["detail"]


# ----- DELETE /conversations/{slug}/messages (clear chat) -----


def test_clear_dm_messages_removes_all(client, db):
    """A DM participant can clear all messages in the DM; reads return empty."""
    from wazzup.api import conversations, messages
    from wazzup.models import MessageCreate

    _seed_alice_and_curie(db)
    alice = users.get_by_slug(db, "alice")
    curie = users.get_by_slug(db, "curie")
    dm = conversations.get_or_create_dm(db, user_a_id=alice.id, user_b_id=curie.id)
    messages.create(db, MessageCreate(conversation_id=dm.id, sender_id=alice.id, text="hi"))
    messages.create(db, MessageCreate(conversation_id=dm.id, sender_id=curie.id, text="hello"))

    resp = client.delete(f"/conversations/{dm.slug}/messages", headers=AUTH_HEADER)
    assert resp.status_code == 204

    # Read after clear returns empty.
    msgs = client.get(f"/conversations/{dm.slug}/messages", headers=AUTH_HEADER).json()
    assert msgs == []


def test_clear_dm_messages_403_for_non_participant(client, db):
    """A non-participant trying to clear a DM gets 403, same as the read path."""
    from wazzup.api import conversations, messages
    from wazzup.models import MessageCreate

    _seed_alice_and_curie(db)
    users.create(db, UserCreate(name="Bob", slug="bob", type="human"))
    alice = users.get_by_slug(db, "alice")
    curie = users.get_by_slug(db, "curie")
    dm = conversations.get_or_create_dm(db, user_a_id=alice.id, user_b_id=curie.id)
    messages.create(db, MessageCreate(conversation_id=dm.id, sender_id=alice.id, text="hi"))

    resp = client.delete(
        f"/conversations/{dm.slug}/messages",
        headers={"X-User-Slug": "bob"},
    )
    assert resp.status_code == 403


def test_clear_topic_messages_403_rejects_public_clear(client, db):
    """Topic-default conversations reject clear: would wipe shared content."""
    from wazzup.api import messages, topics
    from wazzup.models import MessageCreate, TopicCreate

    _seed_alice_and_curie(db)
    alice = users.get_by_slug(db, "alice")
    eng = topics.create(db, TopicCreate(name="Engineering"))
    conv_id = topics.get_default_conversation_id(db, eng.id)
    messages.create(db, MessageCreate(conversation_id=conv_id, sender_id=alice.id, text="public"))

    resp = client.delete(
        f"/conversations/{eng.default_conversation_slug}/messages",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 403
    assert "topic" in resp.json()["detail"].lower()


def test_clear_dm_messages_404_unknown_slug(client, db):
    """Unknown slug → 404 (not 403; access check needs an existing conv)."""
    _seed_alice_and_curie(db)
    resp = client.delete("/conversations/nope/messages", headers=AUTH_HEADER)
    assert resp.status_code == 404
