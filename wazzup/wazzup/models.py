"""Pydantic models — XCreate / XRead / XUpdate triple per entity.

Section 7 of the lesson; ``docs/MODEL.md`` is the column-by-column
spec these models mirror.

Shape of the triple:

- ``XDetails`` is a Pydantic model that lives in the JSON ``details``
  column. Start empty for entities that don't have known fields yet
  and extend as needed; existing rows still validate.
- ``XCreate``: required fields + optional ``slug`` override + nested
  ``details`` (see "Nullability rule" below for the non-Optional /
  ``default_factory`` pattern).
- ``XRead`` extends ``XCreate`` with ``id``, ``created_at``,
  ``updated_at``, ``deleted_at``; ``slug`` is re-declared as required
  (server populates it).
- ``XUpdate``: every modifiable field is omittable; explicit ``None``
  is *not* the same as omitted — see "Nullability rule" below.

----------------------------------------------------------------------
NULLABILITY RULE (copy-paste this into every new XUpdate)
----------------------------------------------------------------------

*Omittable* and *nullable* are not the same.

- **Omittable** = caller can leave the field out of the patch
  entirely. ``model_dump(exclude_unset=True)`` filters it out, the
  api-layer SET clause skips it, the column isn't touched.
- **Nullable** = caller can set the field to ``None``, meaning
  *"clear this column to NULL"*. Only valid when the schema column
  is nullable.

A field that is *omittable but not nullable* — the common case, since
most NOT NULL columns are still optional in a PATCH — needs to reject
explicit ``None``. Pydantic v2's ``field_validator`` can't easily tell
*unset* from *set-to-None*, so we use two patterns depending on the
field type:

1. **Nested Pydantic models** (e.g., ``details: UserDetails``):
   non-Optional type with ``default_factory``. ``XUpdate()`` is
   valid (default fires); ``XUpdate(details=None)`` raises
   ``ValidationError`` at construction. This is the post-#8 fix
   that prevented silent row corruption when ``details=None``
   round-tripped as JSON ``"null"``.

2. **Scalar fields backing NOT NULL columns** (e.g., ``name: str``
   on a NOT NULL column, ``type: Literal[...]``): keep
   ``T | None = None`` for omittability, then have the api-layer
   ``update()`` function raise ``ValueError`` if ``None`` shows up
   in the patch dict for one of these fields. The DB's NOT NULL
   constraint is the safety net; the api-layer check is the
   friendly error message before SQL even runs. The set of NOT NULL
   fields per entity is declared next to the api ``update``
   function (see ``api/users.py``'s ``_NOT_NULL_FIELDS``).

3. **Nullable scalar fields** (e.g., ``persona: str | None`` on a
   nullable column): keep ``T | None = None`` and accept ``None``
   as the "clear this column" signal. Pass through to SQL as-is.

Apply rule 1 to every nested-model field. Apply rule 2 + a per-entity
``_NOT_NULL_FIELDS`` set to every scalar that the schema declares
NOT NULL. Apply rule 3 only when the schema column is genuinely
nullable.

----------------------------------------------------------------------
MESSAGEREAD DECISION
----------------------------------------------------------------------

``MessageRead`` carries *stored columns only* — id, text, timestamps,
details. *No* ``conversation_id`` / ``sender_id`` fields, because the
rels-only design (section 3 of the lesson; ``docs/MODEL.md``) means
those links live in the ``rels`` table, not in ``message`` columns.

Routes that need to surface the rel-linked ids in their responses
define their *own* response shape — see ``MessageReadInConversation``
below, which extends ``MessageRead`` with ``sender_id`` /
``sender_slug`` / ``sender_name`` populated via JOIN at the api
boundary. Keeping ``MessageRead`` aligned with the table is the
choice that makes the storage decision visible at every layer; the
alternative — silently denormalizing rels onto the read model —
would let the abstraction leak. ``MessageReadInConversation`` is
the controlled denormalization for route consumers (the UI) that
need the sender at-a-glance.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ----- user -----

class UserDetails(BaseModel):
    """Lives in the JSON `details` column."""
    bio: str | None = None
    timezone: str = "UTC"


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    slug: str | None = None
    type: Literal["human", "agent"]
    persona: str | None = None
    details: UserDetails = Field(default_factory=UserDetails)


class UserRead(UserCreate):
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    type: Literal["human", "agent"] | None = None
    persona: str | None = None
    # NOT Optional: `details=None` would round-trip as JSON "null" → Python
    # None → ValidationError on re-read (UserRead.details is non-Optional),
    # silently corrupting the row mid-update. With default_factory and a
    # non-Optional type, `UserUpdate(details=None)` raises at construction;
    # `UserUpdate()` is still valid and `exclude_unset=True` keeps it out
    # of the patch dict, so omission still means "don't update details".
    details: UserDetails = Field(default_factory=UserDetails)


# ----- conversation -----

class ConversationDetails(BaseModel):
    """Lives in the JSON `details` column. Empty for now; extend as needed."""
    pass


class ConversationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    slug: str | None = None
    details: ConversationDetails = Field(default_factory=ConversationDetails)


class ConversationRead(ConversationCreate):
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class ConversationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    details: ConversationDetails = Field(default_factory=ConversationDetails)


# ----- topic -----

class TopicDetails(BaseModel):
    """Lives in the JSON `details` column. Empty for now; extend as needed."""
    pass


class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    slug: str | None = None
    details: TopicDetails = Field(default_factory=TopicDetails)


class TopicRead(TopicCreate):
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    # Non-Optional by invariant: every topic owns a default conversation,
    # auto-created in the same transaction as the topic itself by
    # `topics.create()`. Both id and slug are populated by
    # `_row_to_topicread` via a single `in_topic` rel lookup. The id is
    # what the UI passes to `POST /messages`; the slug is what
    # `GET /conversations/{slug}/messages` expects. Carrying both
    # spares the UI a round-trip.
    #
    # If the rel is missing at read time, `topics._row_to_topicread`
    # fires `deviation()` — strict mode raises, lax mode surfaces
    # sentinel values (id=0, slug="<missing>") so the UI looks broken
    # loudly rather than silently coping. See `docs/MODEL.md`'s
    # "Invariants" section.
    default_conversation_id: int
    default_conversation_slug: str


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    details: TopicDetails = Field(default_factory=TopicDetails)


# ----- message (exception: no name/slug, no FK columns; links live in rels) -----

class MessageDetails(BaseModel):
    """Lives in the JSON `details` column. Empty for now; extend as needed."""
    pass


class MessageCreate(BaseModel):
    """Inputs for creating a message.

    NOTE: `conversation_id` and `sender_id` are NOT columns on the
    `message` table (see `docs/MODEL.md` and section 3 of the lesson —
    every link lives in `rels`). They're parameters that
    `messages.create()` uses to write the `belongs_to` and `sent_by`
    rels alongside the message row.
    """
    conversation_id: int
    sender_id: int
    text: str = Field(min_length=1)
    details: MessageDetails = Field(default_factory=MessageDetails)


class MessageRead(BaseModel):
    """A message row read from the DB. No conversation_id / sender_id —
    those live in rels. The HTTP layer can JOIN to surface them when
    a route's response shape needs them."""
    id: int
    text: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    details: MessageDetails = Field(default_factory=MessageDetails)


class MessageUpdate(BaseModel):
    """Message edits are rare; keeping the CRUD pattern uniform."""
    text: str | None = Field(default=None, min_length=1)
    details: MessageDetails = Field(default_factory=MessageDetails)


class MessageReadInConversation(MessageRead):
    """Read shape for list routes that need the sender at-a-glance.

    Same stored columns as ``MessageRead``, plus the sender's id, slug,
    and display name resolved through the ``sent_by`` rel + the user
    table. Populated by ``api.messages.query_with_senders`` (the api
    boundary owns the JOIN; routes pass through).

    The denormalization is *controlled* — only this read shape carries
    the rel-resolved fields, and only the list routes use it. ``MessageRead``
    stays stored-columns-only so the rels-only invariant is visible at
    every other layer.
    """
    sender_id: int
    sender_slug: str
    sender_name: str


# ----- rels (no name/slug, no updated_at; just links) -----

class RelDetails(BaseModel):
    """Lives in the JSON `details` column. Empty for now; extend as needed
    (e.g., role on `member_of`, joined_at on participant rels)."""
    pass


class RelAdd(BaseModel):
    """Polymorphic link from one entity to another.

    `src_type` / `tgt_type` are constrained at the schema level by
    a CHECK to one of `('user', 'conversation', 'topic', 'message')`
    — db.py's `NAMED_ENTITIES` is the source of truth. We don't
    duplicate the constraint here as a `Literal[...]` because then
    adding a new entity would require touching two places; the
    schema CHECK catches typos at insert time.
    """
    src_type: str
    src_id: int
    tgt_type: str
    tgt_id: int
    rel_type: str
    details: RelDetails = Field(default_factory=RelDetails)


class RelRead(RelAdd):
    id: int
    created_at: datetime
    deleted_at: datetime | None = None
    # Note: rels has no updated_at column (per `docs/MODEL.md`).
    # A rel either exists, or is soft-deleted; it doesn't get edited.
