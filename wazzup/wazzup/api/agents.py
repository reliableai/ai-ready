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

from sqlite3 import Connection

from wazzup import llm
from wazzup.api import conversations, messages, users
from wazzup.logging_setup import deviation
from wazzup.models import MessageCreate, MessageRead, UserRead

_HISTORY_WINDOW = 20


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

    DM: the non-sender participant if they're an agent (at most one).
    Topic-default: all live agent users, defensively excluding the sender.
    Sorted by user.id ASC for stable demo order.
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

    # Topic-default: every agent user replies.
    agents = users.query(db, type="agent")
    return sorted(
        (a for a in agents if a.id != sender_id),
        key=lambda u: u.id,
    )


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
