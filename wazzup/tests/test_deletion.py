"""Cascade-deletion tests — task #13.

Covers ``api/deletion.cascade_delete`` and the funnel pattern in each
entity's public ``delete()``. The original-sin user-cascade test stays
in ``test_users.py`` because it motivated this whole task; this file
covers the rest of the cascade surface:

- per-entity rel cascade (topic, message)
- recursive cascade (conversation → message → rels)
- ``CascadeReport`` count accuracy
- hard cascade (physical removal end-to-end)
- idempotency on already-deleted entities
- the visited-set guard against cycles

Cascade rules (mirrored from ``api/deletion.py`` module docstring):
- user/topic/message: rels involving the entity (as src or tgt)
- conversation: nested messages + rels involving the conversation
"""

import pytest

from wazzup.api import (
    NotFound,
    conversations,
    messages,
    rels,
    topics,
    users,
)
from wazzup.api.deletion import cascade_delete
from wazzup.models import (
    ConversationCreate,
    MessageCreate,
    TopicCreate,
    UserCreate,
)

# ----- per-entity rel cascade -----


def test_topic_delete_cascades_to_rels(db):
    """Soft-deleting a topic soft-deletes every rel involving it.

    Includes the auto-created ``in_topic`` rel from ``topics.create()``
    and the explicitly-added ``member_of`` rel.
    """
    alice = users.create(db, UserCreate(name="Alice", type="human"))
    eng = topics.create(db, TopicCreate(name="Engineering"))
    rels.add(db, src_type="user", src_id=alice.id,
             tgt_type="topic", tgt_id=eng.id, rel_type="member_of")

    topics.delete(db, eng.id)

    # All rels pointing at the topic are gone from the live set
    # (member_of, in_topic).
    assert rels.list(db, tgt_type="topic", tgt_id=eng.id) == []


def test_topic_delete_cascades_to_default_conversation_and_messages(db):
    """v0.2 cascade rule: deleting a topic also deletes its default conversation
    (which then recursively cascades to its messages and their rels)."""
    alice = users.create(db, UserCreate(name="Alice", type="human"))
    eng = topics.create(db, TopicCreate(name="Engineering"))
    conv_id = topics.get_default_conversation_id(db, eng.id)
    assert conv_id is not None

    msg = messages.create(db, MessageCreate(
        conversation_id=conv_id, sender_id=alice.id, text="hi",
    ))

    topics.delete(db, eng.id)

    # Topic, conversation, and message all gone from live reads.
    assert topics.get(db, eng.id) is None
    assert conversations.get(db, conv_id) is None
    assert messages.get(db, msg.id) is None
    # Message's belongs_to + sent_by rels are gone.
    assert rels.list(db, src_type="message", src_id=msg.id) == []
    # Conversation's rels (in_topic) are gone.
    assert rels.list(db, src_type="conversation", src_id=conv_id) == []


def test_message_delete_cascades_to_rels(db):
    """Soft-deleting a message soft-deletes its belongs_to + sent_by rels."""
    alice = users.create(db, UserCreate(name="Alice", type="human"))
    standup = conversations._create(db, ConversationCreate(name="Daily Standup"))
    msg = messages.create(db, MessageCreate(
        conversation_id=standup.id, sender_id=alice.id, text="hi",
    ))

    # Pre-cascade: 2 live rels through the message
    assert len(rels.list(db, src_type="message", src_id=msg.id)) == 2

    messages.delete(db, msg.id)

    # Post-cascade: 0 live rels through the message
    assert rels.list(db, src_type="message", src_id=msg.id) == []


# ----- recursive cascade -----


def test_conversation_delete_cascades_to_messages_and_their_rels(db):
    """Soft-deleting a conversation cascades to its messages — and *their* rels.

    The recursive case: conversation → message (rule), message → rels
    (rule). All three layers are touched in one cascade call.
    """
    alice = users.create(db, UserCreate(name="Alice", type="human"))
    standup = conversations._create(db, ConversationCreate(name="Daily Standup"))
    m1 = messages.create(db, MessageCreate(
        conversation_id=standup.id, sender_id=alice.id, text="one",
    ))
    m2 = messages.create(db, MessageCreate(
        conversation_id=standup.id, sender_id=alice.id, text="two",
    ))

    conversations.delete(db, standup.id)

    # Both messages are gone from the live set.
    assert messages.get(db, m1.id) is None
    assert messages.get(db, m2.id) is None
    # Their belongs_to and sent_by rels are gone too.
    assert rels.list(db, src_type="message", src_id=m1.id) == []
    assert rels.list(db, src_type="message", src_id=m2.id) == []
    # The conversation itself is gone.
    assert conversations.get(db, standup.id) is None


# ----- CascadeReport counts -----


def test_cascade_report_counts_match_actual_changes(db):
    """The report's primary/rels/messages counts are accurate.

    Calls ``cascade_delete`` directly (not via the entity wrapper) so
    we can read the report — the wrappers just check ``primary == 0``
    and discard the rest.
    """
    alice = users.create(db, UserCreate(name="Alice", type="human"))
    standup = conversations._create(db, ConversationCreate(name="Daily Standup"))
    m1 = messages.create(db, MessageCreate(
        conversation_id=standup.id, sender_id=alice.id, text="one",
    ))
    m2 = messages.create(db, MessageCreate(
        conversation_id=standup.id, sender_id=alice.id, text="two",
    ))

    report = cascade_delete(db, table="conversation", id=standup.id)

    assert report.primary == 1                                    # the conversation
    assert report.messages == 2                                   # m1, m2
    # Each message has 2 rels (belongs_to + sent_by) = 4 total.
    # The conversation also had 2 belongs_to rels pointing at it,
    # but those were already soft-deleted during the message
    # cascade — so they don't count again here. Total: 4.
    assert report.rels == 4
    assert m1.id  # quiet the unused-warning
    assert m2.id


# ----- hard cascade -----


def test_hard_delete_cascades_hard(db):
    """``hard=True`` propagates: dependent rows are physically removed too."""
    alice = users.create(db, UserCreate(name="Alice", type="human"))
    standup = conversations._create(db, ConversationCreate(name="Daily Standup"))
    msg = messages.create(db, MessageCreate(
        conversation_id=standup.id, sender_id=alice.id, text="hi",
    ))

    conversations.delete(db, standup.id, hard=True)

    # Physically gone from message and rels tables.
    assert db.execute("SELECT id FROM message WHERE id = ?", (msg.id,)).fetchone() is None
    assert db.execute("SELECT id FROM conversation WHERE id = ?", (standup.id,)).fetchone() is None
    # The rels for the message (belongs_to + sent_by) are also physically gone.
    rel_count = db.execute(
        "SELECT COUNT(*) FROM rels WHERE src_id = ? AND src_type = 'message'",
        (msg.id,),
    ).fetchone()[0]
    assert rel_count == 0


# ----- idempotency -----


def test_cascade_idempotent_on_already_deleted(db):
    """Calling cascade_delete on an already-soft-deleted primary returns
    primary=0 without raising.

    The public ``delete()`` wrapper translates primary=0 to NotFound;
    this test exercises the underlying idempotency without that wrap.
    """
    alice = users.create(db, UserCreate(name="Alice", type="human"))
    cascade_delete(db, table="user", id=alice.id)   # first call: succeeds

    second = cascade_delete(db, table="user", id=alice.id)  # second call: no-op
    assert second.primary == 0
    assert second.rels == 0  # all rels were cleaned up on the first call


def test_double_delete_via_public_wrapper_raises_notfound(db):
    """The public ``delete()`` wrapper preserves the NotFound contract."""
    alice = users.create(db, UserCreate(name="Alice", type="human"))
    users.delete(db, alice.id)

    with pytest.raises(NotFound, match=str(alice.id)):
        users.delete(db, alice.id)


# ----- visited-set guard -----


def test_visited_set_short_circuits_already_processed(db):
    """The ``_visited`` set ensures (table, id) is processed once per call tree.

    Today's cascade rules are acyclic — the only recursion is
    ``conversation → message``, and message cascade has no recursion.
    The visited-set guard exists for *future* cascade-rule changes
    that might introduce a cycle. We document the guard's contract
    here by probing it directly: pre-populating ``_visited`` with the
    target makes ``cascade_delete`` return an empty report without
    touching the entity.

    This is a probe of private behavior (``_visited`` is internal to
    the recursion). Reasonable in a test that exists to pin the
    guard's documented contract.
    """
    alice = users.create(db, UserCreate(name="Alice", type="human"))
    pre_populated = {("user", alice.id)}

    report = cascade_delete(db, table="user", id=alice.id, _visited=pre_populated)
    assert report.primary == 0
    assert report.rels == 0
    # Alice is still alive — the guard short-circuited the cascade.
    assert users.get(db, alice.id) is not None
