"""FastMCP server — exposes a curated subset of ``wazzup.api`` as tools.

This is the lesson-3 adapter. Each ``@mcp.tool()`` is a thin wrapper over
the existing ``wazzup.api.*`` functions; the api layer is unchanged. The
tool surface is deliberately curated — read operations are open, write
operations take an explicit ``as_user_slug`` so the caller picks
identity, destructive operations (clear chat, hard delete) are
deliberately *not* exposed.

**No auth** for v0.3. The server binds to ``127.0.0.1`` and accepts
any caller. The ``as_user_slug`` arg on write tools is how the caller
acts as a specific identity (alice, trump, etc.); production would
swap this for OAuth at the transport (lesson 3 §10).

**In-process, not over HTTP.** The MCP server imports ``wazzup.api``
directly. No httpx, no double-hop. The ``api/`` layer is the contract
both the FastAPI surface (``http/``) and this MCP surface adapt over.

Run with::

    uv run python -m wazzup.mcp.server

The server listens on ``http://127.0.0.1:8002/mcp`` (streamable HTTP).
Wire it to Claude Code via ``claude mcp add --transport http wazzup
http://127.0.0.1:8002/mcp``.
"""

from contextlib import contextmanager
from sqlite3 import Connection

from mcp.server.fastmcp import FastMCP

from wazzup.api import (
    NotFound,
    agents,
    conversations,
    messages,
    topics,
    users,
)
from wazzup.db import connect
from wazzup.models import (
    ConversationRead,
    MessageCreate,
    MessageRead,
    MessageReadInConversation,
    TopicRead,
    UserRead,
)

mcp = FastMCP("wazzup", host="127.0.0.1", port=8002)
# Bind to 8002 because the FastAPI server owns 8000 and the static UI
# server (``python -m http.server 8001 -d ui/``) owns 8001. Three
# processes, three ports — the ``/mcp`` path lives inside this
# process's port, not as a way to share a port with the UI. FastMCP
# reads host/port at construction; mutating ``mcp.settings.*`` after
# the fact does NOT take effect.


@contextmanager
def _db():
    """Per-tool-call DB connection — same lifecycle as ``http/get_db``.

    Open, yield, commit on clean exit, rollback on exception, close.
    FastMCP doesn't have FastAPI's ``Depends``-style DI, so each tool
    function calls this explicitly. The boilerplate is small enough
    not to factor; if the count of tools doubles, a decorator factory
    would be the right next step.
    """
    conn: Connection = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ----- read tools (open; no identity required) -----


@mcp.tool()
def list_topics() -> list[TopicRead]:
    """List every public topic in wazzup.

    Use this when the user asks "what topics exist", "what channels
    are there", or before posting on a topic to find its
    ``default_conversation_id``. Returns each topic with its slug,
    name, and the ``default_conversation_id`` / ``default_conversation_slug``
    needed to read messages or post in the topic.
    """
    with _db() as db:
        return topics.query(db)


@mcp.tool()
def get_topic(slug: str) -> TopicRead:
    """Look up a single topic by slug.

    Use when you know the topic's slug (e.g., "engineering",
    "daily-standup", "random") and need its ``default_conversation_id``
    to post in it. Errors if the slug doesn't match a live topic.
    """
    with _db() as db:
        topic = topics.get_by_slug(db, slug)
        if topic is None:
            raise NotFound(f"topic slug={slug!r} not found")
        return topic


@mcp.tool()
def list_users() -> list[UserRead]:
    """List every live user in wazzup — humans and agents both.

    Use this to discover slugs (e.g., "what's Trump's slug?") or to
    decide which agent to act as via ``post_message(as_user_slug=...)``.
    Each user carries ``slug``, ``name``, ``type`` ('human' or 'agent'),
    and ``persona`` (markdown system prompt for agents; null for
    humans).
    """
    with _db() as db:
        return users.query(db)


@mcp.tool()
def get_user(slug: str) -> UserRead:
    """Look up a single user by slug. Use when you know the slug
    (e.g., "alice", "trump", "min-ho") and want details — including
    the agent's persona text or whether they're human or agent."""
    with _db() as db:
        u = users.get_by_slug(db, slug)
        if u is None:
            raise NotFound(f"user slug={slug!r} not found")
        return u


@mcp.tool()
def list_messages_in_conversation(
    conversation_slug: str,
    limit: int = 20,
) -> list[MessageReadInConversation]:
    """Read the latest messages in a conversation, oldest-first within
    the window.

    The slug is the conversation's slug (a topic's ``default_conversation_slug``
    — same as the topic slug — or a DM slug like ``dm-alice-trump``).
    Returns up to ``limit`` messages (default 20, max 200), each
    enriched with ``sender_id`` / ``sender_slug`` / ``sender_name``
    so you can render multi-party threads. Soft-deleted messages
    are excluded.
    """
    with _db() as db:
        conv = conversations.get_by_slug(db, conversation_slug)
        if conv is None:
            raise NotFound(f"conversation slug={conversation_slug!r} not found")
        return messages.query_with_senders(
            db, conversation_id=conv.id, limit=min(limit, 200),
        )


# ----- write tools (caller picks identity via as_user_slug) -----


@mcp.tool()
def post_message(
    conversation_id: int,
    text: str,
    as_user_slug: str,
) -> MessageRead:
    """Post a message in a conversation, acting as the named user.

    - ``conversation_id``: the integer id of the target conversation
      (get this from ``list_topics`` for a public topic, or from
      ``open_dm`` for a 1:1 DM).
    - ``text``: the message body. At least 1 character.
    - ``as_user_slug``: the slug of the user posting — e.g. ``"alice"``,
      ``"trump"``, ``"kitty"``. The user must be a participant of the
      conversation (DMs require participation; topic-default
      conversations are open to anyone).

    **Side effect**: if ``as_user_slug`` is a *human*, the agent
    auto-reply dispatcher fires — every agent in the conversation
    replies in voice (chain semantics, random order). If
    ``as_user_slug`` is an *agent*, the loop guard skips dispatch:
    only that agent's message lands. So "post as trump in
    daily-standup" produces one Trump line; "post as alice in
    daily-standup" produces alice's line plus replies from every
    agent.
    """
    with _db() as db:
        sender = users.get_by_slug(db, as_user_slug)
        if sender is None:
            raise NotFound(f"user slug={as_user_slug!r} not found")
        if conversations.get(db, conversation_id) is None:
            raise NotFound(f"conversation id={conversation_id} not found")
        if not conversations.is_accessible_by(
            db, conversation_id=conversation_id, user_id=sender.id,
        ):
            raise PermissionError(
                f"user {as_user_slug!r} is not a participant of conversation "
                f"id={conversation_id}",
            )
        msg = messages.create(db, MessageCreate(
            conversation_id=conversation_id,
            sender_id=sender.id,
            text=text,
        ))
        # Mirror the http route's transaction shape (lesson 1 §6 +
        # CLAUDE.md): commit the human's message before dispatching
        # agent replies, so a strict-mode deviation in the dispatcher
        # doesn't unwind it.
        db.commit()
        agents.respond_to_human_message(
            db, conversation_id=conversation_id, sender_id=sender.id,
        )
        return msg


@mcp.tool()
def open_dm(as_user_slug: str, peer_slug: str) -> ConversationRead:
    """Open or create the 1:1 DM between two users. Idempotent.

    - ``as_user_slug``: slug of the user opening the DM ("acting as").
    - ``peer_slug``: slug of the other person.

    Same caller + peer twice = same conversation (no duplicates).
    Self-DM (``as_user_slug == peer_slug``) is rejected. Returns the
    conversation; pass its ``id`` to ``post_message`` to send messages
    in this DM.
    """
    with _db() as db:
        me = users.get_by_slug(db, as_user_slug)
        peer = users.get_by_slug(db, peer_slug)
        if me is None:
            raise NotFound(f"user slug={as_user_slug!r} not found")
        if peer is None:
            raise NotFound(f"user slug={peer_slug!r} not found")
        if me.id == peer.id:
            raise ValueError("cannot DM yourself")
        return conversations.get_or_create_dm(
            db, user_a_id=me.id, user_b_id=peer.id,
        )


def main():
    """Run the MCP server on streamable HTTP at ``127.0.0.1:8002/mcp``.

    Bind address is set at the ``FastMCP(...)`` construction above,
    not here — FastMCP doesn't accept host/port on ``run()``.
    """
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
