"""Smoke tests for the Pydantic models.

Models are cheap to test and bugs there are easy to miss until
much later (silent corruption, validation errors at the read path,
etc.). This file pins the patterns from the *Nullability rule* and
*MessageRead decision* sections of ``wazzup/models.py`` module
docstring, so a future regression shows up here rather than in
production.

What's covered:
- default_factory wires up ``XDetails`` for every entity
- explicit ``None`` for nested-model fields in XUpdate is rejected
  at construction (``ValidationError``)
- MessageCreate / RelAdd: required-field validation
- MessageRead / RelRead: stored-columns-only shape (no rels-derived
  ids on MessageRead; no updated_at on RelRead)
"""

import pytest
from pydantic import ValidationError

from wazzup.models import (
    ConversationCreate,
    ConversationDetails,
    ConversationUpdate,
    MessageCreate,
    MessageDetails,
    MessageRead,
    MessageUpdate,
    RelAdd,
    RelDetails,
    RelRead,
    TopicCreate,
    TopicDetails,
    TopicUpdate,
    UserCreate,
    UserDetails,
    UserUpdate,
)

# ----- default_factory wiring (one test per entity) -----

def test_user_create_default_details():
    u = UserCreate(name="Alice", type="human")
    assert isinstance(u.details, UserDetails)
    assert u.details.timezone == "UTC"   # UserDetails default


def test_conversation_create_default_details():
    c = ConversationCreate(name="Daily Standup")
    assert isinstance(c.details, ConversationDetails)


def test_topic_create_default_details():
    t = TopicCreate(name="Engineering")
    assert isinstance(t.details, TopicDetails)


def test_message_create_default_details():
    m = MessageCreate(conversation_id=1, sender_id=2, text="hi")
    assert isinstance(m.details, MessageDetails)


def test_rel_add_default_details():
    r = RelAdd(src_type="user", src_id=1, tgt_type="topic", tgt_id=1, rel_type="member_of")
    assert isinstance(r.details, RelDetails)


# ----- nullability rule: explicit None on nested-model fields rejected at construction -----

def test_user_update_details_none_rejected():
    with pytest.raises(ValidationError):
        UserUpdate(details=None)


def test_conversation_update_details_none_rejected():
    with pytest.raises(ValidationError):
        ConversationUpdate(details=None)


def test_topic_update_details_none_rejected():
    with pytest.raises(ValidationError):
        TopicUpdate(details=None)


def test_message_update_details_none_rejected():
    with pytest.raises(ValidationError):
        MessageUpdate(details=None)


# ----- nullability rule: omitting nested-model field is OK (default fires, exclude_unset filters) -----

def test_user_update_omitted_details_excluded_from_dump():
    """The default_factory still fires, but exclude_unset=True keeps
    it out of the patch dict — the api layer won't touch the column."""
    u = UserUpdate(persona="cheerful")
    dumped = u.model_dump(exclude_unset=True)
    assert "details" not in dumped
    assert dumped == {"persona": "cheerful"}


# ----- MessageCreate / RelAdd validation shape -----

def test_message_create_requires_all_fields():
    """conversation_id, sender_id, text are required."""
    with pytest.raises(ValidationError):
        MessageCreate(conversation_id=1, sender_id=2)         # text missing
    with pytest.raises(ValidationError):
        MessageCreate(conversation_id=1, text="hi")           # sender_id missing
    with pytest.raises(ValidationError):
        MessageCreate(sender_id=2, text="hi")                 # conversation_id missing


def test_message_create_text_min_length():
    """text=\"\" fails min_length=1."""
    with pytest.raises(ValidationError):
        MessageCreate(conversation_id=1, sender_id=2, text="")


def test_rel_add_requires_all_fields():
    """src_type, src_id, tgt_type, tgt_id, rel_type are required."""
    with pytest.raises(ValidationError):
        RelAdd(src_type="user", src_id=1, tgt_type="topic", tgt_id=1)   # rel_type missing
    with pytest.raises(ValidationError):
        RelAdd(src_id=1, tgt_type="topic", tgt_id=1, rel_type="x")      # src_type missing


def test_rel_add_happy_path():
    """All required fields present → constructs OK; details defaults."""
    r = RelAdd(
        src_type="user", src_id=4,
        tgt_type="topic", tgt_id=2,
        rel_type="member_of",
    )
    assert r.src_id == 4 and r.tgt_id == 2
    assert r.rel_type == "member_of"


# ----- MessageRead / RelRead stored-columns-only shape -----

def test_message_read_has_no_rels_linked_ids():
    """MessageRead is stored-columns-only — no conversation_id / sender_id.

    The rels-only design (section 3 of the lesson, docs/MODEL.md)
    means those links live in `rels`, not on the message row. Routes
    that need them in responses define their own response shape.
    """
    fields = set(MessageRead.model_fields.keys())
    assert "conversation_id" not in fields
    assert "sender_id" not in fields
    # And the stored fields *are* there:
    assert {"id", "text", "created_at", "updated_at", "deleted_at", "details"} <= fields


def test_rel_read_has_no_updated_at():
    """rels has no updated_at column (per docs/MODEL.md). A rel either
    exists or is soft-deleted; it doesn't get edited."""
    fields = set(RelRead.model_fields.keys())
    assert "updated_at" not in fields
    # created_at and deleted_at are there:
    assert {"id", "created_at", "deleted_at"} <= fields
    # Plus the link fields from RelAdd:
    assert {"src_type", "src_id", "tgt_type", "tgt_id", "rel_type"} <= fields
