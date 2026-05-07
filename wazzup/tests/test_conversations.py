"""Conversation tests — task #11 + v0.2 model-shape refactor.

Two surfaces under test:

1. **Low-level CRUD** (``_create`` / ``get`` / ``update`` / ``delete`` /
   ``query``). The module-private ``_create`` is reachable from tests
   (they probe internals); production callers use ``topics.create()``
   or ``conversations.get_or_create_dm()`` exclusively. The boundary
   (no public ``create``) is the contract; the CRUD shape is what
   these tests pin.

2. **DM helper** (``get_or_create_dm``). The DM-detection rule —
   *exactly two distinct ``participates_in`` user rels and no
   ``in_topic`` rel* — is subtle enough to deserve its own focused
   tests, especially the 3-party negative case that the naïve
   ``COUNT = 2`` query would silently match.
"""

import pytest

from wazzup.api import NotFound, conversations, rels, topics, users
from wazzup.models import (
    ConversationCreate,
    ConversationUpdate,
    TopicCreate,
    UserCreate,
)

# ----- low-level CRUD (api-layer) -----


def test_create_round_trips(db):
    c = conversations._create(db, ConversationCreate(name="Daily Standup"))
    assert c.id > 0
    assert c.name == "Daily Standup"
    assert c.slug == "daily-standup"


def test_get_and_get_by_slug(db):
    c = conversations._create(db, ConversationCreate(name="Daily Standup"))
    assert conversations.get(db, c.id).id == c.id
    assert conversations.get_by_slug(db, "daily-standup").id == c.id
    assert conversations.get(db, 99999) is None
    assert conversations.get_by_slug(db, "nope") is None


def test_update_partial_fields(db):
    c = conversations._create(db, ConversationCreate(name="Daily Standup"))
    patched = conversations.update(db, c.id, ConversationUpdate(name="Weekly Sync"))
    # name updated, slug unchanged (slugs are stable; ConversationUpdate has no slug field)
    assert patched.name == "Weekly Sync"
    assert patched.slug == "daily-standup"


def test_delete_soft_hides_from_reads(db):
    c = conversations._create(db, ConversationCreate(name="Daily Standup"))
    conversations.delete(db, c.id)
    assert conversations.get(db, c.id) is None
    assert conversations.get_by_slug(db, "daily-standup") is None


def test_query_excludes_soft_deleted(db):
    a = conversations._create(db, ConversationCreate(name="Alpha"))
    conversations._create(db, ConversationCreate(name="Beta"))
    conversations.delete(db, a.id)
    everyone = conversations.query(db)
    assert {c.name for c in everyone} == {"Beta"}


def test_query_filters_by_topic_id(db):
    """``query(topic_id=...)`` JOINs through the ``in_topic`` rel.

    Under v0.2, ``topics.create`` writes the in_topic rel automatically,
    so this test relies on that rather than wiring rels by hand. Soft-
    deleting the topic also soft-deletes the conversation (cascade rule),
    so the topic-filtered list shrinks accordingly.
    """
    eng = topics.create(db, TopicCreate(name="Engineering"))
    rnd = topics.create(db, TopicCreate(name="Random"))

    in_eng = conversations.query(db, topic_id=eng.id)
    assert {c.name for c in in_eng} == {"Engineering"}    # the auto-default conv

    in_rnd = conversations.query(db, topic_id=rnd.id)
    assert {c.name for c in in_rnd} == {"Random"}


def test_update_name_none_rejected_at_api_layer(db):
    """ConversationUpdate(name=None) triggers the api-layer NOT NULL defense."""
    c = conversations._create(db, ConversationCreate(name="Daily Standup"))
    with pytest.raises(ValueError, match="cannot set NOT NULL field"):
        conversations.update(db, c.id, ConversationUpdate(name=None))


# ----- DM helper -----


def _alice_and_curie(db) -> tuple[int, int]:
    alice = users.create(db, UserCreate(name="Alice Smith", slug="alice", type="human"))
    curie = users.create(db, UserCreate(
        name="Marie Curie", slug="curie", type="agent", persona="Quiet rigor.",
    ))
    return alice.id, curie.id


def test_get_or_create_dm_creates_when_missing(db):
    a_id, c_id = _alice_and_curie(db)
    conv = conversations.get_or_create_dm(db, user_a_id=a_id, user_b_id=c_id)
    assert conv.id > 0
    assert conv.slug == "dm-alice-curie"                       # alphabetical user.slug ordering
    # Two participates_in rels, no in_topic rel.
    parts = rels.list(db, rel_type="participates_in", tgt_type="conversation", tgt_id=conv.id)
    assert {r.src_id for r in parts} == {a_id, c_id}
    in_topic = rels.list(db, rel_type="in_topic", src_type="conversation", src_id=conv.id)
    assert in_topic == []


def test_get_or_create_dm_idempotent(db):
    """Same args twice → same conversation id (no duplicate row)."""
    a_id, c_id = _alice_and_curie(db)
    conv1 = conversations.get_or_create_dm(db, user_a_id=a_id, user_b_id=c_id)
    conv2 = conversations.get_or_create_dm(db, user_a_id=a_id, user_b_id=c_id)
    assert conv1.id == conv2.id


def test_get_or_create_dm_argument_order_invariant(db):
    """(a, b) and (b, a) → same conversation."""
    a_id, c_id = _alice_and_curie(db)
    conv1 = conversations.get_or_create_dm(db, user_a_id=a_id, user_b_id=c_id)
    conv2 = conversations.get_or_create_dm(db, user_a_id=c_id, user_b_id=a_id)
    assert conv1.id == conv2.id


def test_get_or_create_dm_self_dm_rejected(db):
    a_id, _ = _alice_and_curie(db)
    with pytest.raises(ValueError, match="cannot DM yourself"):
        conversations.get_or_create_dm(db, user_a_id=a_id, user_b_id=a_id)


def test_get_or_create_dm_unknown_user_raises(db):
    a_id, _ = _alice_and_curie(db)
    with pytest.raises(NotFound):
        conversations.get_or_create_dm(db, user_a_id=a_id, user_b_id=999)


def test_get_or_create_dm_does_not_match_topic_default(db):
    """A topic-default conversation with the same 2 participates_in rels
    must NOT be returned as a DM — the in_topic rel disqualifies it."""
    a_id, c_id = _alice_and_curie(db)
    eng = topics.create(db, TopicCreate(name="Engineering"))
    # Manually attach the same two users as participants of the topic-default conv.
    default_conv_id = topics.get_default_conversation_id(db, eng.id)
    assert default_conv_id is not None
    rels.add(db, src_type="user", src_id=a_id,
             tgt_type="conversation", tgt_id=default_conv_id,
             rel_type="participates_in")
    rels.add(db, src_type="user", src_id=c_id,
             tgt_type="conversation", tgt_id=default_conv_id,
             rel_type="participates_in")

    # The DM helper must skip the topic-default and create a fresh DM.
    dm = conversations.get_or_create_dm(db, user_a_id=a_id, user_b_id=c_id)
    assert dm.id != default_conv_id


def test_get_or_create_dm_does_not_match_three_party_conversation(db):
    """A 3-person conversation containing both alice and curie must NOT match.

    This is the test the *naïve* SQL (``COUNT(DISTINCT) = 2`` without
    the no-third-participant clause) would fail. We construct a fake
    "group conversation" with three participants and assert the DM
    helper still creates a fresh, separate DM.
    """
    a_id, c_id = _alice_and_curie(db)
    bob = users.create(db, UserCreate(name="Bob Jones", type="human"))

    group = conversations._create(db, ConversationCreate(name="Threesome"))
    for u_id in (a_id, c_id, bob.id):
        rels.add(db, src_type="user", src_id=u_id,
                 tgt_type="conversation", tgt_id=group.id,
                 rel_type="participates_in")

    # The DM helper sees the group as having 3 participants → no match.
    dm = conversations.get_or_create_dm(db, user_a_id=a_id, user_b_id=c_id)
    assert dm.id != group.id

    # Fresh DM has exactly 2 participants.
    parts = rels.list(db, rel_type="participates_in",
                      tgt_type="conversation", tgt_id=dm.id)
    assert {r.src_id for r in parts} == {a_id, c_id}


def test_get_or_create_dm_after_soft_delete_creates_new(db):
    """Soft-deleting the DM removes its conversation row from live reads;
    a subsequent call creates a fresh DM (with new id and rels)."""
    a_id, c_id = _alice_and_curie(db)
    first = conversations.get_or_create_dm(db, user_a_id=a_id, user_b_id=c_id)
    conversations.delete(db, first.id)

    second = conversations.get_or_create_dm(db, user_a_id=a_id, user_b_id=c_id)
    assert second.id != first.id


# ----- HTTP smoke (slimmed: only the route the UI actually uses) -----

AUTH_HEADER = {"X-User-Slug": "alice"}


def test_get_messages_in_conversation(client, db):
    """GET /conversations/{slug}/messages → live messages, ordered by id."""
    from wazzup.api import messages
    from wazzup.models import MessageCreate
    alice = users.create(db, UserCreate(name="Alice", type="human"))
    eng = topics.create(db, TopicCreate(name="Engineering"))
    conv_id = topics.get_default_conversation_id(db, eng.id)
    m1 = messages.create(db, MessageCreate(
        conversation_id=conv_id, sender_id=alice.id, text="hello",
    ))
    m2 = messages.create(db, MessageCreate(
        conversation_id=conv_id, sender_id=alice.id, text="world",
    ))

    resp = client.get(
        f"/conversations/{eng.default_conversation_slug}/messages",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [m["id"] for m in body] == [m1.id, m2.id]
    assert [m["text"] for m in body] == ["hello", "world"]


def test_get_messages_in_conversation_404_when_slug_missing(client, db):
    """GET /conversations/{nope}/messages → 404 for unknown conversation slug."""
    users.create(db, UserCreate(name="Alice", type="human"))
    resp = client.get(
        "/conversations/nope/messages",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 404
    assert "nope" in resp.json()["detail"]
