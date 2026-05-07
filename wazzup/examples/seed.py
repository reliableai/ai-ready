"""Seed the canonical demo state — section 10 of the lesson.

Produces what ``docs/DEMO.md`` describes: 5 users (2 humans + 3
agents), 3 public topics each with their auto-default conversation,
one DM (alice ↔ curie), and seeded messages — 4 in the daily-standup
topic's default conversation, 2 in the alice ↔ curie DM.

**Idempotent.** Re-runs are safe — every step checks first via
``get_by_slug`` (or the rels-based DM detection) and skips if the row
already exists. Messages are addressed by id, so the script checks
for any existing message in a conversation and skips message seeding
there if some are present.

**Self-heals.** If a topic exists in the DB without its default
conversation (e.g., a row from before the model-shape v0.2 refactor),
the seed calls ``deviation()`` and creates the missing conversation
+ ``in_topic`` rel. This is belt-and-suspenders: the seed is the one
script most likely to encounter pre-refactor rows, so surfacing the
drift loudly here costs nothing and prevents quiet damage.

Usage:
    python -m examples.seed
"""

from sqlite3 import Connection

from wazzup.api import conversations, messages, rels, topics, users
from wazzup.db import connect, init_schema
from wazzup.logging_setup import deviation
from wazzup.models import (
    ConversationCreate,
    MessageCreate,
    TopicCreate,
    UserCreate,
)

SEED_HUMANS = [
    {"name": "Alice Smith", "slug": "alice", "type": "human"},
    {"name": "Bob Jones", "slug": "bob", "type": "human"},
]

SEED_AGENTS = [
    {
        "name": "Donald Trump",
        "slug": "trump",
        "type": "agent",
        "persona": (
            "You are Donald J. Trump. You speak with tremendous "
            "confidence — the greatest confidence, frankly. Use "
            "hyperbole liberally: the best, the worst, tremendous, "
            "fake news. Short sentences. Many of them. Refer to "
            "yourself in superlatives."
        ),
    },
    {
        "name": "Marie Curie",
        "slug": "curie",
        "type": "agent",
        "persona": (
            "You are Marie Curie. You speak with quiet rigor and "
            "measured curiosity. Favor precise observations over "
            "speculation; be patient with people working out an "
            "idea, even when it's wrong."
        ),
    },
    {
        "name": "Yoda",
        "slug": "yoda",
        "type": "agent",
        "persona": (
            "Yoda, you are. Speak you do, with inverted syntax. "
            "Wisdom you offer, in short pronouncements. Toward the "
            "deeper truth, others you guide — by asking questions, "
            "not by answering them."
        ),
    },
]

SEED_TOPICS = [
    {"name": "Engineering", "slug": "engineering"},
    {"name": "Random", "slug": "random"},
    {"name": "Daily Standup", "slug": "daily-standup"},
]

# Sender slug → message text. Order = post order. Live in the
# daily-standup topic's default conversation.
SEED_TOPIC_MESSAGES = [
    ("alice", "shipping the auth fix today"),
    ("trump", "TREMENDOUS. The greatest auth fix. Everyone's saying it."),
    ("curie", "Excellent. Did you confirm the token refresh path under load?"),
    ("yoda", "Tested under failure, the path also is, hmm?"),
]

# The seeded DM and its messages.
SEED_DM = ("alice", "curie")
SEED_DM_MESSAGES = [
    ("curie", "Quick one — do you have a moment to look at the resampling notebook?"),
    ("alice", "Send the link, will check after standup."),
]


def _seed_users(db: Connection) -> dict[str, int]:
    """Create users (humans + agents). Returns {slug: id}."""
    by_slug: dict[str, int] = {}
    for u in SEED_HUMANS + SEED_AGENTS:
        existing = users.get_by_slug(db, u["slug"])
        if existing:
            print(f"  user: {u['name']:<20} (exists, slug={u['slug']})")
            by_slug[u["slug"]] = existing.id
            continue
        created = users.create(db, UserCreate(**u))
        print(f"  user: {u['name']:<20} created (slug={created.slug}, id={created.id})")
        by_slug[u["slug"]] = created.id
    return by_slug


def _seed_topics(db: Connection) -> dict[str, int]:
    """Create topics + their auto-default conversations. Returns {topic_slug: topic_id}.

    ``topics.create()`` also creates the default conversation in the
    same transaction (and writes the ``in_topic`` rel). For idempotent
    re-runs against an already-seeded DB we just check existence.

    Self-heal path: a topic row without its default conversation is
    structurally invalid post-v0.2. We detect this via
    ``topics.get_default_conversation_id`` (returns None on missing
    rel) and repair it — fire ``deviation()`` so the drift is logged
    loudly, then create the conversation + rel.
    """
    by_slug: dict[str, int] = {}
    for t in SEED_TOPICS:
        existing = topics.get_by_slug(db, t["slug"])
        if existing:
            conv_id = topics.get_default_conversation_id(db, existing.id)
            if conv_id is None:
                deviation(
                    "topic without default conversation, repairing",
                    topic_slug=t["slug"], topic_id=existing.id,
                )
                conv = conversations._create(db, ConversationCreate(name=t["name"]))
                rels.add(
                    db,
                    src_type="conversation", src_id=conv.id,
                    tgt_type="topic", tgt_id=existing.id,
                    rel_type="in_topic",
                )
                print(
                    f"  topic: {t['name']:<20} (exists, slug={t['slug']}, "
                    f"REPAIRED missing default_conv → {conv.slug})"
                )
            else:
                print(f"  topic: {t['name']:<20} (exists, slug={t['slug']})")
            by_slug[t["slug"]] = existing.id
            continue
        created = topics.create(db, TopicCreate(**t))
        print(
            f"  topic: {t['name']:<20} created (slug={created.slug}, id={created.id}, "
            f"default_conv={created.default_conversation_slug})"
        )
        by_slug[t["slug"]] = created.id
    return by_slug


def _seed_topic_messages(
    db: Connection,
    topic_slug: str,
    topic_id: int,
    user_ids: dict[str, int],
    msgs: list[tuple[str, str]],
) -> int:
    """Seed messages into a topic's default conversation. Idempotent: skips if any present."""
    conv_id = topics.get_default_conversation_id(db, topic_id)
    if conv_id is None:
        # The repair path in _seed_topics should have prevented this.
        deviation("missing default conversation at message-seed time", topic_slug=topic_slug)
        return 0
    existing = messages.query(db, conversation_id=conv_id)
    if existing:
        print(f"  messages [{topic_slug}]: {len(existing)} already present, skipping seed")
        return 0
    for sender_slug, text in msgs:
        messages.create(db, MessageCreate(
            conversation_id=conv_id,
            sender_id=user_ids[sender_slug],
            text=text,
        ))
    print(f"  messages [{topic_slug}]: {len(msgs)} seeded")
    return len(msgs)


def _seed_dm(
    db: Connection,
    user_a_slug: str,
    user_b_slug: str,
    user_ids: dict[str, int],
    msgs: list[tuple[str, str]],
) -> int:
    """Seed the canonical DM and its messages. Returns conversation id.

    Uses ``conversations.get_or_create_dm`` so re-runs find the existing
    DM rather than creating a duplicate. Messages-seed is idempotent
    via the same any-existing-message proxy as topic messages.
    """
    a_id, b_id = user_ids[user_a_slug], user_ids[user_b_slug]
    conv_before = conversations.get_or_create_dm(db, user_a_id=a_id, user_b_id=b_id)
    print(
        f"  dm: {user_a_slug} ↔ {user_b_slug:<10} "
        f"(slug={conv_before.slug}, id={conv_before.id})"
    )
    existing = messages.query(db, conversation_id=conv_before.id)
    if existing:
        print(f"  messages [dm]: {len(existing)} already present, skipping seed")
        return conv_before.id
    for sender_slug, text in msgs:
        messages.create(db, MessageCreate(
            conversation_id=conv_before.id,
            sender_id=user_ids[sender_slug],
            text=text,
        ))
    print(f"  messages [dm]: {len(msgs)} seeded")
    return conv_before.id


def seed() -> None:
    db = connect()
    try:
        init_schema(db)
        print("seeding wazzup demo state…")
        user_ids = _seed_users(db)
        topic_ids = _seed_topics(db)
        _seed_topic_messages(
            db,
            topic_slug="daily-standup",
            topic_id=topic_ids["daily-standup"],
            user_ids=user_ids,
            msgs=SEED_TOPIC_MESSAGES,
        )
        _seed_dm(
            db,
            user_a_slug=SEED_DM[0],
            user_b_slug=SEED_DM[1],
            user_ids=user_ids,
            msgs=SEED_DM_MESSAGES,
        )
        db.commit()
        print("done.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
