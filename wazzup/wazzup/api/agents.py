"""Agent reply dispatch — the only place that creates agent reply messages.

When a human posts a message, the ``POST /messages`` HTTP route calls
``respond_to_human_message()`` *after* committing the human's message
explicitly (see ``CLAUDE.md`` and lesson §14a for the transaction
rationale).

Loop guard: only ``user.type='human'`` posts trigger replies. Agent
posts never reach the dispatcher. Without this, every agent reply
would re-trigger the dispatcher and burn LLM credits.

Scope (computed in ``_responders_for``):

- **DM** (no ``in_topic`` rel): the other participant, if they're an
  agent. Single reply at most.
- **Topic-default** (``in_topic`` rel exists): every ``user.type='agent'``
  user replies, in stable user-id order.

Failure isolation: each agent reply is wrapped in try/except. On
``llm.call`` failure, ``deviation()`` fires (lax mode logs + skip;
strict mode raises) and the loop ``continue``\\s. Per-agent commits
mean prior successes survive a downstream failure.
"""

import random
from sqlite3 import Connection

from wazzup import llm
from wazzup.api import conversations, messages, users
from wazzup.logging_setup import deviation
from wazzup.models import MessageCreate, MessageRead, UserRead

_HISTORY_WINDOW = 100   # last N messages each agent sees as LLM context.
                        # 100 is generous enough that demo conversations
                        # (≤30 messages from a seeded chat) fit entirely,
                        # so personas can call back to early exchanges
                        # rather than seeing only the trailing window.
                        # Cost scales linearly with conversation length;
                        # bump higher only if you have a reason.


def respond_to_human_message(
    db: Connection,
    *,
    conversation_id: int,
    sender_id: int,
) -> list[MessageRead]:
    """Dispatch agent replies in response to a human's just-posted message.

    Returns the newly-created agent messages, in the order they were
    created. No-op (returns ``[]``) if the sender isn't a live human.

    **Per-agent commit semantics.** Each successful reply commits before
    the next agent runs. The caller must commit the human's message
    *before* invoking this function — otherwise a strict-mode deviation
    in the loop would unwind the human's message via the request
    wrapper's rollback path (see ``CLAUDE.md`` and lesson §14a).
    """
    sender = users.get(db, sender_id)
    if sender is None or sender.type != "human":
        return []                                          # loop guard

    replies: list[MessageRead] = []
    for agent in _responders_for(db, conversation_id, sender_id):
        if not agent.persona:
            deviation(
                "agent has no persona, skipping",
                agent_slug=agent.slug, agent_id=agent.id,
            )
            continue
        history = _build_chat_history(
            db, conversation_id=conversation_id, agent=agent, n=_HISTORY_WINDOW,
        )
        text = _call_llm_with_persona(agent, history)
        if text is None:
            continue                                       # failure isolation
        msg = messages.create(db, MessageCreate(
            conversation_id=conversation_id,
            sender_id=agent.id,
            text=text,
        ))
        db.commit()                                        # per-agent commit
        replies.append(msg)
    return replies


def _responders_for(
    db: Connection,
    conversation_id: int,
    sender_id: int,
) -> list[UserRead]:
    """Pick which agents should reply to a message in this conversation.

    DM: the non-sender participant if they're an agent (at most one — no
    ordering question).

    Topic-default: every live agent user (defensively excluding the
    sender). **Order is random** — shuffled per dispatch — so the demo
    doesn't always have Trump speak first. One small constraint: the
    agent who spoke *most recently* in this conversation isn't promoted
    to lead the next round. If the shuffle puts them at index 0, they
    swap with index 1. Avoids the "same agent leading two rounds in a
    row" feel that pure shuffle occasionally produces.

    The shuffle uses ``random.shuffle`` directly (process-global RNG).
    Tests that need determinism should ``random.seed(...)`` or
    monkeypatch ``random.shuffle``.
    """
    topic_id = conversations.get_topic_id(db, conversation_id)
    if topic_id is None:
        # DM-shaped: the peer, if they're an agent.
        peer_ids = [
            uid for uid in conversations.get_participant_ids(db, conversation_id)
            if uid != sender_id
        ]
        peers: list[UserRead] = []
        for uid in peer_ids:
            u = users.get(db, uid)
            if u is not None and u.type == "agent":
                peers.append(u)
        return sorted(peers, key=lambda u: u.id)

    # Topic-default: every agent user replies, in random order.
    agent_list = [a for a in users.query(db, type="agent") if a.id != sender_id]
    random.shuffle(agent_list)

    # Don't repeat the previous round's leader — if the shuffle put the
    # most recent agent speaker at index 0, swap with index 1 so a
    # different agent leads. Trivial when len < 2.
    if len(agent_list) >= 2:
        last_agent_id = _last_agent_speaker_id(db, conversation_id)
        if last_agent_id is not None and agent_list[0].id == last_agent_id:
            agent_list[0], agent_list[1] = agent_list[1], agent_list[0]

    return agent_list


def _last_agent_speaker_id(db: Connection, conversation_id: int) -> int | None:
    """User id of the most recent message-sender in this conversation,
    *if* that sender is an agent. Returns ``None`` if the most recent
    speaker was a human or there are no messages.

    Used by ``_responders_for`` to keep the same agent from leading
    two rounds in a row. Looking at the most recent agent specifically
    (not the most recent message-of-any-kind) is what makes the rule
    useful: humans always trigger the dispatcher, so the "most recent
    message" right before a dispatch is always a human; we want the
    most recent *agent* before that human's post.
    """
    row = db.execute(
        """
        SELECT u.id AS user_id FROM message m
        JOIN rels r_send
            ON r_send.src_id = m.id
           AND r_send.src_type = 'message'
           AND r_send.rel_type = 'sent_by'
           AND r_send.tgt_type = 'user'
           AND r_send.deleted_at IS NULL
        JOIN user u
            ON u.id = r_send.tgt_id
           AND u.deleted_at IS NULL
           AND u.type = 'agent'
        JOIN rels r_conv
            ON r_conv.src_id = m.id
           AND r_conv.src_type = 'message'
           AND r_conv.rel_type = 'belongs_to'
           AND r_conv.tgt_type = 'conversation'
           AND r_conv.tgt_id = ?
           AND r_conv.deleted_at IS NULL
        WHERE m.deleted_at IS NULL
        ORDER BY m.id DESC
        LIMIT 1
        """,
        (conversation_id,),
    ).fetchone()
    return row["user_id"] if row else None


def _build_chat_history(
    db: Connection,
    *,
    conversation_id: int,
    agent: UserRead,
    n: int = _HISTORY_WINDOW,
) -> list[dict]:
    """Build the OpenAI ``messages`` list for an agent's LLM call.

    Shape:
    - first entry: ``{"role": "system", "content": agent.persona}``
    - then the last ``n`` messages in chronological order, where each
      sender mapping is:
        - the responding agent itself → ``role="assistant"``
        - any other user (human or another agent) → ``role="user"``
          with ``f"{name}: {text}"`` content. The name prefix is what
          carries "who said what" in a multi-party room — OpenAI's
          ``user`` role is one abstract speaker, so we encode the
          identity in the content itself.
    """
    out: list[dict] = [{"role": "system", "content": agent.persona}]

    history = messages.recent_history(db, conversation_id=conversation_id, n=n)
    for msg in history:
        sender_id = _sender_id_of_message(db, msg.id)
        if sender_id == agent.id:
            out.append({"role": "assistant", "content": msg.text})
            continue
        sender = users.get(db, sender_id) if sender_id is not None else None
        sender_name = sender.name if sender is not None else "(unknown)"
        out.append({
            "role": "user",
            "content": f"{sender_name}: {msg.text}",
        })
    return out


def _sender_id_of_message(db: Connection, message_id: int) -> int | None:
    """Find the user id this message was ``sent_by`` via its rel.

    Returns ``None`` if the rel is missing — that's an invariant
    violation (``messages.create`` writes the rel atomically), so
    history will surface a "(unknown)" speaker rather than crashing.
    """
    row = db.execute(
        "SELECT tgt_id FROM rels "
        "WHERE src_type = 'message' AND src_id = ? "
        "  AND rel_type = 'sent_by' AND tgt_type = 'user' "
        "  AND deleted_at IS NULL "
        "LIMIT 1",
        (message_id,),
    ).fetchone()
    return row["tgt_id"] if row else None


def _call_llm_with_persona(agent: UserRead, history: list[dict]) -> str | None:
    """Call ``llm.call`` and return the reply text, or ``None`` on failure.

    Wraps a broad ``except Exception`` because the LLM client surface is
    diverse (network errors, auth errors, rate limits, model errors). On
    failure, ``deviation()`` records the agent slug + the error so a
    debugger can find which agent's reply went wrong.
    """
    try:
        return llm.call(history)
    except Exception as e:                                 # noqa: BLE001 — we want any LLM failure
        deviation(
            "agent reply failed",
            agent_slug=agent.slug, agent_id=agent.id, error=str(e),
        )
        return None
