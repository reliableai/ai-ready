"""Cascade rules for soft-delete — section 4 of the lesson.

One file, one source of truth. §4: *"Implement this in **one place**
(a delete() helper) — never scatter cascade logic across routes."*

Every entity's public ``delete()`` funnels through ``cascade_delete``.
The entity-side ``delete()`` is a 3-line wrapper:

    def delete(db, id, hard=False):
        from wazzup.api.deletion import cascade_delete  # late import (cycle)
        report = cascade_delete(db, table=<entity>, id=id, hard=hard)
        if report.primary == 0:
            raise NotFound(...)

----------------------------------------------------------------------
CASCADE RULES (single source of truth — mirrored in docs/MODEL.md)
----------------------------------------------------------------------

- ``user``: all rels with src=(user, id) OR tgt=(user, id). No nested
  entities.
- ``topic``: all rels with src=(topic, id) OR tgt=(topic, id), AND the
  topic's default conversation linked via ``in_topic`` — which itself
  recursively cascades per the conversation rule.
- ``message``: all rels with src=(message, id) OR tgt=(message, id).
  No nested entities.
- ``conversation``: all rels with src=(conversation, id) OR
  tgt=(conversation, id), AND all messages with a ``belongs_to`` rel
  pointing at this conversation — which themselves cascade per the
  message rule.

Recursive cascade applies to ``conversation → message`` and
``topic → conversation → message``. A ``visited`` set guards against
future schema mistakes that might introduce a cycle — depth in
practice is ≤ 3.

----------------------------------------------------------------------
HARD vs SOFT (Option A — uniform)
----------------------------------------------------------------------

The ``hard`` flag propagates to all dependents. Soft cascade is
reversible end-to-end (un-soft-delete the primary, dependents
reappear); hard cascade is destructive end-to-end. Mixed modes
(soft primary + hard dependents, or vice versa) are rejected at
plan time as confusing — see TODO.md "Plan for #13" design
decision 4.

----------------------------------------------------------------------
IDEMPOTENCY
----------------------------------------------------------------------

``cascade_delete`` is idempotent on the *primary*: calling it on an
already-soft-deleted entity returns ``CascadeReport(primary=0, ...)``
without raising. The cascading-through-rels path still runs, in case
a previous partial cascade left some live stragglers.

The public entity ``delete()`` wrappers preserve the ``NotFound``
contract by checking ``report.primary == 0`` and raising. So:

- ``users.delete(db, missing_id)`` → ``NotFound`` (primary=0, no rels touched)
- ``users.delete(db, soft_deleted_id)`` → ``NotFound`` (primary=0; same shape)
- ``users.delete(db, live_id)`` → returns None, primary=1, rels=N

The two ``NotFound`` cases are intentionally indistinguishable — "not
there anymore" is "not there".

----------------------------------------------------------------------
TRANSACTION
----------------------------------------------------------------------

Caller owns the transaction. ``cascade_delete`` does not commit.
"""

from dataclasses import dataclass
from sqlite3 import Connection

from wazzup.api import (
    NotFound,
    conversations,
    rels,
    topics,
    users,
)
from wazzup.api import messages as messages_api


@dataclass
class CascadeReport:
    """Counts of what cascade_delete actually changed.

    - ``primary``: 0 or 1 — whether the primary entity row was affected.
      0 means it was already deleted (idempotent path); the public
      ``delete()`` wrapper raises ``NotFound`` in that case.
    - ``rels``: total live rels soft/hard-deleted across the entire
      cascade tree (includes rels of recursive sub-cascades).
    - ``conversations``: conversations cascaded as a side-effect of
      deleting a topic (its default conversation).
    - ``messages``: messages cascaded as a side-effect of deleting a
      conversation (directly, or via topic → conversation).
    """
    primary: int = 0
    rels: int = 0
    conversations: int = 0
    messages: int = 0


# Dispatch: which entity's ``_delete_primary`` to call for a given table.
# Each entity exposes a private ``_delete_primary(db, id, hard) -> bool``
# alongside its public ``delete()`` (see e.g. ``api/users.py``).
_PRIMARY_DELETE = {
    "user": users._delete_primary,
    "conversation": conversations._delete_primary,
    "topic": topics._delete_primary,
    "message": messages_api._delete_primary,
}


def cascade_delete(
    db: Connection,
    *,
    table: str,
    id: int,
    hard: bool = False,
    _visited: set[tuple[str, int]] | None = None,
) -> CascadeReport:
    """Soft- or hard-delete an entity and everything that cascades from it.

    Returns a ``CascadeReport`` so callers (and tests) can verify what
    actually changed. See module docstring for the cascade rules,
    hard/soft propagation, idempotency, and transaction policy.

    The ``_visited`` set is a recursion guard for future schemas that
    might (mistakenly) introduce a cycle in cascade rules. Today the
    cascade is acyclic (only ``conversation → message``), so the guard
    is dead code on the happy path; keep it as a defensive measure.
    """
    if table not in _PRIMARY_DELETE:
        raise ValueError(f"cascade_delete: unknown table {table!r}")

    if _visited is None:
        _visited = set()
    if (table, id) in _visited:
        # Already cascaded in this call tree — return an empty report
        # so we don't double-count.
        return CascadeReport()
    _visited.add((table, id))

    report = CascadeReport()

    # 1. Recursive cascade for nested entities.
    # - conversation → message: belongs_to rels point from message → conversation.
    # - topic → conversation: in_topic rels point from conversation → topic.
    if table == "conversation":
        msg_rels = rels.list(
            db,
            rel_type="belongs_to",
            tgt_type="conversation",
            tgt_id=id,
        )
        for r in msg_rels:
            sub = cascade_delete(
                db, table="message", id=r.src_id, hard=hard, _visited=_visited,
            )
            report.messages += sub.primary
            report.rels += sub.rels
    elif table == "topic":
        in_topic_rels = rels.list(
            db,
            rel_type="in_topic",
            tgt_type="topic",
            tgt_id=id,
        )
        for r in in_topic_rels:
            sub = cascade_delete(
                db, table="conversation", id=r.src_id, hard=hard, _visited=_visited,
            )
            report.conversations += sub.primary
            report.messages += sub.messages
            report.rels += sub.rels

    # 2. Cascade through rels: every live rel where this entity appears
    # as src OR tgt. The recursive sub-cascade above may have already
    # soft-deleted some of these (e.g. the message's belongs_to rel
    # was removed during the message cascade); list() filters those
    # out by virtue of WHERE deleted_at IS NULL.
    affected_rels = (
        rels.list(db, src_type=table, src_id=id)
        + rels.list(db, tgt_type=table, tgt_id=id)
    )
    for r in affected_rels:
        try:
            rels.remove(db, r.id, hard=hard)
            report.rels += 1
        except NotFound:
            # Already removed via another path in this tree. Idempotent.
            pass

    # 3. Delete the primary row. Returns False if already-deleted —
    # that's the idempotent path; the wrapper translates to NotFound.
    if _PRIMARY_DELETE[table](db, id, hard):
        report.primary = 1

    return report
