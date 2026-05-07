"""Rels API smoke tests — task #12.

8 tests over `add` / `remove` / `list`. Pin:

- the FK-existence validation (since rels has no DB-level FK)
- the dedupe-among-live behavior (schema partial UNIQUE)
- soft-delete reuse (same partial UNIQUE filters live only)
- the kw-only filter combinations on ``list``

The rels-only design is now load-bearing for the message tests in
#11 too — those still pass because messages.create writes its rels
through ``rels.add`` (TODO #22 closed in this task).
"""

from sqlite3 import IntegrityError

import pytest

from wazzup.api import NotFound, conversations, rels, topics, users
from wazzup.models import ConversationCreate, TopicCreate, UserCreate


def _seed_alice_and_engineering(db):
    alice = users.create(db, UserCreate(name="Alice", type="human"))
    eng = topics.create(db, TopicCreate(name="Engineering"))
    return alice, eng


# ----- add -----


def test_add_writes_a_rel(db):
    alice, eng = _seed_alice_and_engineering(db)
    r = rels.add(
        db,
        src_type="user", src_id=alice.id,
        tgt_type="topic", tgt_id=eng.id,
        rel_type="member_of",
    )
    assert r.id > 0
    assert r.src_type == "user" and r.src_id == alice.id
    assert r.tgt_type == "topic" and r.tgt_id == eng.id
    assert r.rel_type == "member_of"
    assert r.deleted_at is None


def test_add_unknown_src_raises_notfound(db):
    _, eng = _seed_alice_and_engineering(db)
    with pytest.raises(NotFound, match="src .user, 999."):
        rels.add(
            db,
            src_type="user", src_id=999,
            tgt_type="topic", tgt_id=eng.id,
            rel_type="member_of",
        )


def test_add_unknown_tgt_raises_notfound(db):
    alice, _ = _seed_alice_and_engineering(db)
    with pytest.raises(NotFound, match="tgt .topic, 999."):
        rels.add(
            db,
            src_type="user", src_id=alice.id,
            tgt_type="topic", tgt_id=999,
            rel_type="member_of",
        )


def test_add_duplicate_live_raises_integrityerror(db):
    """Schema's ``rels_dedupe_alive`` partial UNIQUE catches duplicates.

    Same (src_type, src_id, tgt_type, tgt_id, rel_type) tuple twice
    on live rows fails. Up to the caller to decide retry / report.
    """
    alice, eng = _seed_alice_and_engineering(db)
    rels.add(db, src_type="user", src_id=alice.id,
             tgt_type="topic", tgt_id=eng.id, rel_type="member_of")
    with pytest.raises(IntegrityError):
        rels.add(db, src_type="user", src_id=alice.id,
                 tgt_type="topic", tgt_id=eng.id, rel_type="member_of")


def test_add_after_remove_is_allowed(db):
    """Soft-delete reuse: partial UNIQUE filters live rows only."""
    alice, eng = _seed_alice_and_engineering(db)
    r = rels.add(db, src_type="user", src_id=alice.id,
                 tgt_type="topic", tgt_id=eng.id, rel_type="member_of")
    rels.remove(db, r.id)
    # Re-adding the same tuple now succeeds — the previous one is soft-deleted.
    r2 = rels.add(db, src_type="user", src_id=alice.id,
                  tgt_type="topic", tgt_id=eng.id, rel_type="member_of")
    assert r2.id != r.id


# ----- remove -----


def test_remove_soft_hides_from_list(db):
    alice, eng = _seed_alice_and_engineering(db)
    r = rels.add(db, src_type="user", src_id=alice.id,
                 tgt_type="topic", tgt_id=eng.id, rel_type="member_of")
    rels.remove(db, r.id)
    # Live list is empty; the row is still in the DB.
    assert rels.list(db, src_type="user", src_id=alice.id) == []
    row = db.execute("SELECT deleted_at FROM rels WHERE id = ?", (r.id,)).fetchone()
    assert row["deleted_at"] is not None


def test_remove_hard_removes_row(db):
    alice, eng = _seed_alice_and_engineering(db)
    r = rels.add(db, src_type="user", src_id=alice.id,
                 tgt_type="topic", tgt_id=eng.id, rel_type="member_of")
    rels.remove(db, r.id, hard=True)
    row = db.execute("SELECT id FROM rels WHERE id = ?", (r.id,)).fetchone()
    assert row is None


# ----- list -----


def test_list_filters_by_src_and_rel_type(db):
    """``list`` filters compose: src + rel_type narrows to one match."""
    alice, eng = _seed_alice_and_engineering(db)
    standup = conversations._create(db, ConversationCreate(name="Daily Standup"))

    rels.add(db, src_type="user", src_id=alice.id,
             tgt_type="topic", tgt_id=eng.id, rel_type="member_of")
    rels.add(db, src_type="user", src_id=alice.id,
             tgt_type="conversation", tgt_id=standup.id, rel_type="participates_in")

    # All rels FROM alice
    all_alice = rels.list(db, src_type="user", src_id=alice.id)
    assert len(all_alice) == 2

    # Just member_of
    members = rels.list(db, src_type="user", src_id=alice.id, rel_type="member_of")
    assert len(members) == 1
    assert members[0].tgt_type == "topic"

    # No-match returns empty
    none = rels.list(db, src_type="user", src_id=999)
    assert none == []
