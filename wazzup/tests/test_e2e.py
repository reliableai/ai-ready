"""End-to-end happy-path test — task #15 + v0.2 model-shape refactor.

Section 9 of the lesson: *"create users → create a topic (which auto-
creates its default conversation) → exchange messages on that topic →
open a DM between two users → exchange messages there → soft-delete
one user → confirm cascade"*.

This test exercises the full critical path at the **api layer**:
every entity module, ``rels.add`` / ``rels.list``, the v0.2 boundary
(``topics.create`` and ``conversations.get_or_create_dm`` as the only
public producers of conversations), and ``cascade_delete`` all in one
realistic flow. It's the test that would fail loudest if any of them
silently broke their contract.

**Why api-level, not HTTP?** An HTTP-level e2e is in scope for a
follow-up; the api-level test verifies the cascade contract directly,
which is the most architecturally important thing to pin.

**Strict-mode coverage.** This test should pass under STRICT_MODE=1
in CI as well — the happy path must not trigger any ``deviation()``
calls. If it does, the deviation is either misplaced (the path
isn't actually unexpected) or there's a real bug. CI runs both
legs (#17).
"""

from wazzup.api import (
    conversations,
    messages,
    rels,
    topics,
    users,
)
from wazzup.models import (
    MessageCreate,
    TopicCreate,
    UserCreate,
)


def test_e2e_seed_chat_cascade(db):
    # ----- seed 4 users (2 humans + 2 agents) -----
    alice = users.create(db, UserCreate(name="Alice", type="human"))
    bob = users.create(db, UserCreate(name="Bob", type="human"))
    trump = users.create(db, UserCreate(
        name="Donald Trump", type="agent",
        persona="Speaks with tremendous confidence.",
    ))
    curie = users.create(db, UserCreate(
        name="Marie Curie", type="agent",
        persona="Speaks like a scientist who insists on evidence.",
    ))

    # ----- topic (auto-creates its default conversation + in_topic rel) -----
    eng = topics.create(db, TopicCreate(name="Engineering"))
    standup_id = topics.get_default_conversation_id(db, eng.id)
    assert standup_id is not None

    # ----- exchange 4 messages on the topic's default conversation -----
    m_alice = messages.create(db, MessageCreate(
        conversation_id=standup_id, sender_id=alice.id,
        text="shipping the auth fix today",
    ))
    m_bob = messages.create(db, MessageCreate(
        conversation_id=standup_id, sender_id=bob.id,
        text="reviewed it — looks good",
    ))
    m_trump = messages.create(db, MessageCreate(
        conversation_id=standup_id, sender_id=trump.id,
        text="TREMENDOUS. The greatest auth fix.",
    ))
    m_curie = messages.create(db, MessageCreate(
        conversation_id=standup_id, sender_id=curie.id,
        text="please attach the regression test results",
    ))

    # ----- DM: alice ↔ curie + 1 message -----
    dm = conversations.get_or_create_dm(
        db, user_a_id=alice.id, user_b_id=curie.id,
    )
    m_dm_alice = messages.create(db, MessageCreate(
        conversation_id=dm.id, sender_id=alice.id,
        text="ping me when you've reviewed",
    ))

    # ----- pre-cascade sanity -----
    topic_msgs = messages.query(db, conversation_id=standup_id)
    assert {m.id for m in topic_msgs} == {m_alice.id, m_bob.id, m_trump.id, m_curie.id}
    dm_msgs = messages.query(db, conversation_id=dm.id)
    assert {m.id for m in dm_msgs} == {m_dm_alice.id}
    # alice has 1 src rel (participates_in DM) and 2 tgt rels (sent_by m_alice, sent_by m_dm_alice).
    assert len(rels.list(db, src_type="user", src_id=alice.id)) == 1
    assert len(rels.list(db, tgt_type="user", tgt_id=alice.id)) == 2

    # ----- soft-delete alice -----
    users.delete(db, alice.id)

    # ----- alice is gone from reads -----
    assert users.get(db, alice.id) is None
    assert users.get_by_slug(db, "alice") is None

    # ----- alice's rels are all gone (cascade) -----
    assert rels.list(db, src_type="user", src_id=alice.id) == []
    assert rels.list(db, tgt_type="user", tgt_id=alice.id) == []

    # ----- alice's *messages* are still alive -----
    # cascade goes user → user's rels, NOT user → user's messages.
    # The message rows survive; only the sent_by rels through them are gone.
    fresh = messages.get(db, m_alice.id)
    assert fresh is not None
    assert fresh.text == "shipping the auth fix today"
    fresh_dm = messages.get(db, m_dm_alice.id)
    assert fresh_dm is not None

    # Topic conversation still has 4 messages — m_alice is in there.
    assert {m.id for m in messages.query(db, conversation_id=standup_id)} == {
        m_alice.id, m_bob.id, m_trump.id, m_curie.id,
    }

    # ----- the other 3 users, the topic, and the conversations are unaffected -----
    for u in (bob, trump, curie):
        assert users.get(db, u.id) is not None
    assert conversations.get(db, standup_id) is not None
    assert conversations.get(db, dm.id) is not None
    assert topics.get(db, eng.id) is not None
