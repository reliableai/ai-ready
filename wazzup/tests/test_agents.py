"""Agent-reply dispatch tests.

Pins the rules from ``docs/MODEL.md``'s "Agent reply loop" section and
``api/agents.py``'s docstring:

- Loop guard: only ``user.type='human'`` posts trigger replies.
- DM scope: agent peer (if any) responds; human↔human DMs are silent.
- Topic scope: every agent user replies, in stable user-id order.
- Chain semantics: each agent's history fetch sees prior agents' replies.
- Failure isolation: LLM failure logs (lax) or raises (strict); the
  human's message + any prior committed replies survive either way.

All tests mock ``wazzup.llm.call`` via ``monkeypatch`` — no real LLM
hits. The ``mock_llm`` fixture also captures every prompt so tests can
assert on the system prompt and history shape.
"""

import pytest

from wazzup.api import conversations, topics, users
from wazzup.models import TopicCreate, UserCreate

AUTH_HEADER_ALICE = {"X-User-Slug": "alice"}
AUTH_HEADER_BOB = {"X-User-Slug": "bob"}
AUTH_HEADER_TRUMP = {"X-User-Slug": "trump"}


@pytest.fixture
def mock_llm(monkeypatch):
    """Replace ``wazzup.llm.call`` with a deterministic fake.

    Returns the ``captured`` list — every prompt the dispatcher sends
    is appended, so tests can assert on persona / history shape.

    The reply text is keyed off the persona's slug-like substring so
    each agent's reply is identifiable in assertions.
    """
    captured: list[list[dict]] = []

    def _fake(messages, **kwargs):
        captured.append(messages)
        persona = (messages[0]["content"] or "").lower()
        if "trump" in persona:
            return "TREMENDOUS reply, the best."
        if "curie" in persona:
            return "Quietly, I observe."
        if "yoda" in persona:
            return "Reply, I do."
        return "(generic agent reply)"

    monkeypatch.setattr("wazzup.llm.call", _fake)
    monkeypatch.setattr("wazzup.api.agents.llm.call", _fake)
    return captured


def _seed_humans_and_agents(db):
    """alice + bob (humans) plus trump, curie, yoda (agents). Returns dict."""
    rec: dict[str, int] = {}
    rec["alice"] = users.create(db, UserCreate(
        name="Alice", slug="alice", type="human",
    )).id
    rec["bob"] = users.create(db, UserCreate(
        name="Bob", slug="bob", type="human",
    )).id
    rec["trump"] = users.create(db, UserCreate(
        name="Donald Trump", slug="trump", type="agent",
        persona="You are Donald Trump. Hyperbole, short sentences.",
    )).id
    rec["curie"] = users.create(db, UserCreate(
        name="Marie Curie", slug="curie", type="agent",
        persona="You are Marie Curie. Quiet rigor.",
    )).id
    rec["yoda"] = users.create(db, UserCreate(
        name="Yoda", slug="yoda", type="agent",
        persona="Yoda you are. Inverted syntax, you use.",
    )).id
    return rec


# ----- DM scope -----


def test_human_post_in_dm_with_agent_triggers_one_reply(client, db, mock_llm):
    """alice DMs trump, posts hi → 2 messages exist (alice's + trump's reply)."""
    rec = _seed_humans_and_agents(db)
    dm = conversations.get_or_create_dm(
        db, user_a_id=rec["alice"], user_b_id=rec["trump"],
    )

    resp = client.post(
        "/messages",
        headers=AUTH_HEADER_ALICE,
        json={"conversation_id": dm.id, "text": "hi"},
    )
    assert resp.status_code == 201

    msgs = client.get(
        f"/conversations/{dm.slug}/messages", headers=AUTH_HEADER_ALICE,
    ).json()
    texts = [m["text"] for m in msgs]
    assert texts == ["hi", "TREMENDOUS reply, the best."]


def test_human_human_dm_no_agent_reply(client, db, mock_llm):
    """alice DMs bob, posts → only the one message (no agent participates)."""
    rec = _seed_humans_and_agents(db)
    dm = conversations.get_or_create_dm(
        db, user_a_id=rec["alice"], user_b_id=rec["bob"],
    )
    resp = client.post(
        "/messages",
        headers=AUTH_HEADER_ALICE,
        json={"conversation_id": dm.id, "text": "hi"},
    )
    assert resp.status_code == 201

    msgs = client.get(
        f"/conversations/{dm.slug}/messages", headers=AUTH_HEADER_ALICE,
    ).json()
    assert [m["text"] for m in msgs] == ["hi"]
    assert len(mock_llm) == 0                           # no LLM calls


# ----- Topic scope -----


def test_human_post_in_topic_triggers_one_reply_per_agent(client, db, mock_llm):
    """alice posts in daily-standup → 4 messages (alice's + 3 agents)."""
    _seed_humans_and_agents(db)
    standup = topics.create(db, TopicCreate(name="Daily Standup"))

    resp = client.post(
        "/messages",
        headers=AUTH_HEADER_ALICE,
        json={
            "conversation_id": standup.default_conversation_id,
            "text": "what's everyone working on?",
        },
    )
    assert resp.status_code == 201

    msgs = client.get(
        f"/conversations/{standup.default_conversation_slug}/messages",
        headers=AUTH_HEADER_ALICE,
    ).json()
    texts = [m["text"] for m in msgs]
    assert texts == [
        "what's everyone working on?",
        "TREMENDOUS reply, the best.",
        "Quietly, I observe.",
        "Reply, I do.",
    ]


def test_agent_replies_in_user_id_order(client, db, mock_llm):
    """3 agent replies appear in stable order (Trump → Curie → Yoda by user.id)."""
    _seed_humans_and_agents(db)
    standup = topics.create(db, TopicCreate(name="Daily Standup"))

    client.post(
        "/messages",
        headers=AUTH_HEADER_ALICE,
        json={"conversation_id": standup.default_conversation_id, "text": "ping"},
    )

    # mock_llm captures the prompts in order; the persona of each is
    # observable in messages[0].content.
    personas = [c[0]["content"] for c in mock_llm]
    assert "Trump" in personas[0]
    assert "Curie" in personas[1]
    assert "Yoda" in personas[2]


# ----- Chain semantics -----


def test_chain_semantics_curie_sees_trumps_reply(client, db, mock_llm):
    """Curie's history fetch happens *after* Trump's reply commits, so
    Curie's prompt includes Trump's reply text."""
    _seed_humans_and_agents(db)
    standup = topics.create(db, TopicCreate(name="Daily Standup"))

    client.post(
        "/messages",
        headers=AUTH_HEADER_ALICE,
        json={"conversation_id": standup.default_conversation_id, "text": "go"},
    )

    # mock_llm[0] = Trump's prompt (sees only alice's msg)
    # mock_llm[1] = Curie's prompt (should see alice + Trump's reply)
    # mock_llm[2] = Yoda's prompt (should see alice + Trump + Curie)
    trump_history = mock_llm[0]
    curie_history = mock_llm[1]
    yoda_history = mock_llm[2]

    # Trump sees only alice's message, no prior agent replies.
    trump_user_msgs = [m["content"] for m in trump_history if m["role"] == "user"]
    assert any("go" in c for c in trump_user_msgs)
    assert not any("TREMENDOUS" in c for c in trump_user_msgs)

    # Curie sees Trump's reply (chain).
    curie_contents = [m["content"] for m in curie_history]
    assert any("TREMENDOUS reply, the best." in c for c in curie_contents)

    # Yoda sees Trump *and* Curie.
    yoda_contents = [m["content"] for m in yoda_history]
    assert any("TREMENDOUS reply, the best." in c for c in yoda_contents)
    assert any("Quietly, I observe." in c for c in yoda_contents)


# ----- Loop guard -----


def test_agent_post_does_not_trigger_replies(client, db, mock_llm):
    """Trump impersonating in dev mode posts in topic → no further replies."""
    _seed_humans_and_agents(db)
    standup = topics.create(db, TopicCreate(name="Daily Standup"))

    resp = client.post(
        "/messages",
        headers=AUTH_HEADER_TRUMP,
        json={"conversation_id": standup.default_conversation_id, "text": "I AM POSTING"},
    )
    assert resp.status_code == 201

    msgs = client.get(
        f"/conversations/{standup.default_conversation_slug}/messages",
        headers=AUTH_HEADER_ALICE,
    ).json()
    assert [m["text"] for m in msgs] == ["I AM POSTING"]
    assert len(mock_llm) == 0                            # no LLM calls dispatched


# ----- Prompt shape -----


def test_agent_reply_uses_persona_as_system_prompt(client, db, mock_llm):
    """The first message in every LLM call is the agent's persona as 'system'."""
    rec = _seed_humans_and_agents(db)
    dm = conversations.get_or_create_dm(
        db, user_a_id=rec["alice"], user_b_id=rec["trump"],
    )
    client.post(
        "/messages",
        headers=AUTH_HEADER_ALICE,
        json={"conversation_id": dm.id, "text": "hi"},
    )
    assert len(mock_llm) == 1
    prompt = mock_llm[0]
    assert prompt[0]["role"] == "system"
    assert "Trump" in prompt[0]["content"]


def test_agent_reply_history_carries_sender_names(client, db, mock_llm):
    """Multi-party history: trump's prompt prefixes user content with `{name}: `."""
    _seed_humans_and_agents(db)
    standup = topics.create(db, TopicCreate(name="Daily Standup"))

    # Two human posts before any agent has replied — but each post triggers
    # the dispatcher, so by the time bob posts, trump etc. have already
    # replied to alice. The point of this test is the name-prefix shape,
    # so we just check that bob's content includes "Bob: ".
    client.post(
        "/messages",
        headers=AUTH_HEADER_ALICE,
        json={"conversation_id": standup.default_conversation_id, "text": "first"},
    )
    client.post(
        "/messages",
        headers=AUTH_HEADER_BOB,
        json={"conversation_id": standup.default_conversation_id, "text": "second"},
    )

    # Find a Trump prompt (system content includes "Trump") and inspect
    # its user-role entries.
    trump_prompts = [c for c in mock_llm if "Trump" in c[0]["content"]]
    assert len(trump_prompts) >= 2                       # one per human post
    last_trump = trump_prompts[-1]
    user_contents = [m["content"] for m in last_trump if m["role"] == "user"]
    # The most recent user message before Trump's last reply should be Bob's.
    assert any(c.startswith("Bob: ") for c in user_contents)
    # Earlier user messages should include alice's prefix.
    assert any(c.startswith("Alice: ") for c in user_contents)


# ----- Failure isolation -----


def _raising_llm(messages, **kwargs):
    raise RuntimeError("simulated LLM outage")


def test_llm_failure_isolated_human_message_survives_lax(client, db, monkeypatch):
    """Lax mode: LLM raises → deviation logs → human's message persists, no agent reply."""
    from wazzup import logging_setup

    rec = _seed_humans_and_agents(db)
    dm = conversations.get_or_create_dm(
        db, user_a_id=rec["alice"], user_b_id=rec["trump"],
    )
    # Force lax mode so the deviation logs instead of raising. Without
    # this, the test would 500 under STRICT_MODE=1 in CI.
    monkeypatch.setattr(logging_setup, "STRICT_MODE", False)
    monkeypatch.setattr("wazzup.api.agents.llm.call", _raising_llm)

    resp = client.post(
        "/messages",
        headers=AUTH_HEADER_ALICE,
        json={"conversation_id": dm.id, "text": "hi"},
    )
    assert resp.status_code == 201                       # human's POST succeeds

    msgs = client.get(
        f"/conversations/{dm.slug}/messages", headers=AUTH_HEADER_ALICE,
    ).json()
    assert [m["text"] for m in msgs] == ["hi"]           # only the human's message


def test_llm_failure_strict_mode_500s_but_human_message_durable(
    client, db, monkeypatch,
):
    """Strict mode: deviation raises → request 500s → but human's message survives.

    This is the test the friend's review demands. It only passes if (a)
    ``http/messages.py`` calls ``db.commit()`` after the human's
    ``messages.create``, and (b) the test fixture's ``_override_get_db``
    mirrors production's commit/rollback wrapper.
    """
    from wazzup import logging_setup

    rec = _seed_humans_and_agents(db)
    dm = conversations.get_or_create_dm(
        db, user_a_id=rec["alice"], user_b_id=rec["trump"],
    )
    monkeypatch.setattr("wazzup.api.agents.llm.call", _raising_llm)
    monkeypatch.setattr(logging_setup, "STRICT_MODE", True)

    resp = client.post(
        "/messages",
        headers=AUTH_HEADER_ALICE,
        json={"conversation_id": dm.id, "text": "hi"},
    )
    assert resp.status_code == 500                       # deviation raised through

    msgs = client.get(
        f"/conversations/{dm.slug}/messages", headers=AUTH_HEADER_ALICE,
    ).json()
    assert [m["text"] for m in msgs] == ["hi"]           # human's message durable


def test_agent_reply_skipped_when_persona_missing(client, db, mock_llm, monkeypatch):
    """An agent with no persona is skipped (deviation logs); other agents still reply."""
    from wazzup import logging_setup

    # The "no persona" path fires deviation(); force lax mode so the test
    # asserts the lax behavior. Strict mode would 500 instead.
    monkeypatch.setattr(logging_setup, "STRICT_MODE", False)

    # Three agents seeded; one with no persona.
    rec = _seed_humans_and_agents(db)
    # Wipe trump's persona via raw SQL to simulate a malformed seed.
    db.execute(
        "UPDATE user SET persona = NULL WHERE id = ?", (rec["trump"],),
    )
    db.commit()
    standup = topics.create(db, TopicCreate(name="Daily Standup"))

    client.post(
        "/messages",
        headers=AUTH_HEADER_ALICE,
        json={"conversation_id": standup.default_conversation_id, "text": "hi"},
    )

    msgs = client.get(
        f"/conversations/{standup.default_conversation_slug}/messages",
        headers=AUTH_HEADER_ALICE,
    ).json()
    texts = [m["text"] for m in msgs]
    # alice's message + curie + yoda (trump skipped); count = 3.
    assert len(texts) == 3
    assert texts[0] == "hi"
    assert "TREMENDOUS" not in " ".join(texts)
