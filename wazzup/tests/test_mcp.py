"""MCP server smoke test.

End-to-end probe of ``wazzup.mcp.server`` using the official MCP
``Client`` against the FastMCP server's in-memory transport. No
real LLM calls; ``llm.call`` is monkeypatched so post_message
doesn't burn tokens when the auto-reply dispatcher fires.

Why ``mcp.shared.memory`` and not streamable HTTP? The HTTP server
binds a port and runs an event loop, which is awkward inside pytest.
The in-memory transport is the same protocol over a `MemoryObjectSendStream`
pair — exact same tool surface, no port juggling, no async complexity
beyond a single ``asyncio.run``.
"""

import asyncio

import pytest

from wazzup.api import topics, users
from wazzup.models import TopicCreate, UserCreate


@pytest.fixture
def mcp_no_llm(db, monkeypatch):
    """Test-only patch of ``wazzup.mcp.server._db`` and ``llm.call``.

    Two patches in one fixture because the test depends on both:

    1. ``_db()``: the production helper opens a fresh connection via
       ``wazzup.db.connect()`` (default path ``./wazzup.db``), which
       targets the on-disk dev database — *not* the test's in-memory
       fixture. We replace it with a context manager that yields the
       shared test connection, so every tool's writes are visible to
       the test code's reads.

    2. ``llm.call``: post_message triggers the agent-reply dispatcher
       when the sender is human; without a stub, the test would burn
       real LLM tokens (or fail loudly when the env isn't configured).
    """
    from contextlib import contextmanager

    @contextmanager
    def _shared_db():
        yield db

    monkeypatch.setattr("wazzup.mcp.server._db", _shared_db)

    def _fake(messages, **kwargs):
        return "(stub agent reply)"
    monkeypatch.setattr("wazzup.llm.call", _fake)
    monkeypatch.setattr("wazzup.api.agents.llm.call", _fake)


def _seed_for_mcp(db):
    """Seed enough state for the MCP smoke: alice + trump, daily-standup topic."""
    alice = users.create(db, UserCreate(name="Alice", slug="alice", type="human"))
    users.create(db, UserCreate(
        name="Donald Trump", slug="trump", type="agent",
        persona="You are Donald Trump. Tremendous.",
    ))
    standup = topics.create(db, TopicCreate(name="Daily Standup"))
    return alice, standup


def _run_mcp_session(coro):
    """Helper: run a coroutine that uses an in-memory MCP session.

    Importing inside the helper keeps test collection cheap (the MCP
    SDK's async machinery is not free at import time).
    """
    from mcp.shared.memory import create_connected_server_and_client_session

    from wazzup.mcp.server import mcp

    async def _runner():
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            return await coro(session)

    return asyncio.run(_runner())


def test_mcp_lists_curated_tools(db, mcp_no_llm):
    """list_tools() returns exactly the curated 7 tools, no surprises."""
    _seed_for_mcp(db)

    async def probe(session):
        return await session.list_tools()

    result = _run_mcp_session(probe)
    names = {t.name for t in result.tools}
    assert names == {
        "list_topics", "get_topic",
        "list_users", "get_user",
        "list_messages_in_conversation",
        "post_message", "open_dm",
    }


def test_mcp_list_topics_returns_seeded_topics(db, mcp_no_llm):
    _seed_for_mcp(db)

    async def probe(session):
        return await session.call_tool("list_topics", {})

    result = _run_mcp_session(probe)
    # FastMCP returns content blocks; the structured payload is in
    # ``result.structuredContent`` (when the tool returns a typed value).
    payload = result.structuredContent or {}
    rows = payload.get("result") or payload.get("topics") or []
    # Different SDK versions wrap this differently; tolerate either
    # the top-level dict-with-result or a direct list in the textual content.
    if not rows and result.content:
        import json
        rows = json.loads(result.content[0].text)
    slugs = {t["slug"] for t in rows}
    assert "daily-standup" in slugs


def test_mcp_post_message_as_alice_lands_and_dispatches(db, mcp_no_llm):
    """Posting as a human triggers the agent dispatcher (loop guard
    only kicks in for agent posts). The stubbed llm.call keeps the
    test deterministic; we only assert that the human's message
    lands, not the exact reply text."""
    alice, standup = _seed_for_mcp(db)

    async def probe(session):
        return await session.call_tool(
            "post_message",
            {
                "conversation_id": standup.default_conversation_id,
                "text": "shipping the auth fix today",
                "as_user_slug": "alice",
            },
        )

    _run_mcp_session(probe)

    # Re-query messages: alice's message + trump's reply (auto-dispatched).
    from wazzup.api import messages
    msgs = messages.query(db, conversation_id=standup.default_conversation_id)
    texts = [m.text for m in msgs]
    assert "shipping the auth fix today" in texts
    assert "(stub agent reply)" in texts


def test_mcp_post_message_as_trump_skips_dispatch(db, mcp_no_llm):
    """Posting as an agent: only Trump's message lands; the loop guard
    prevents further agent replies (no chain reaction)."""
    _, standup = _seed_for_mcp(db)

    async def probe(session):
        return await session.call_tool(
            "post_message",
            {
                "conversation_id": standup.default_conversation_id,
                "text": "I AM POSTING.",
                "as_user_slug": "trump",
            },
        )

    _run_mcp_session(probe)

    from wazzup.api import messages
    msgs = messages.query(db, conversation_id=standup.default_conversation_id)
    texts = [m.text for m in msgs]
    assert texts == ["I AM POSTING."]


def test_mcp_open_dm_idempotent(db, mcp_no_llm):
    """open_dm with the same caller + peer twice → same conversation id."""
    _seed_for_mcp(db)

    async def probe(session):
        first = await session.call_tool(
            "open_dm",
            {"as_user_slug": "alice", "peer_slug": "trump"},
        )
        second = await session.call_tool(
            "open_dm",
            {"as_user_slug": "alice", "peer_slug": "trump"},
        )
        return first, second

    first, second = _run_mcp_session(probe)
    import json
    a = json.loads(first.content[0].text) if first.content else first.structuredContent
    b = json.loads(second.content[0].text) if second.content else second.structuredContent
    # Tolerate both nested structuredContent and content[0].text shapes.
    a_id = a.get("id") if isinstance(a, dict) else a
    b_id = b.get("id") if isinstance(b, dict) else b
    assert a_id == b_id
