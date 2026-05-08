# wazzup — demo data and walkthrough

What `python -m examples.seed` produces, and how to demo the app once it's seeded. This file pairs with `examples/seed.py`: `seed.py` is the *executable*; this is the *spec*. Update this doc first when you change what's seeded.

## Seeded users

### Humans

| slug    | name          | persona | role in demo |
| ------- | ------------- | ------- | ------------ |
| `alice` | Alice Smith   | (none)  | default dev user — `X-User-Slug: alice`. Most demo flows act as Alice. |
| `bob`   | Bob Jones     | (none)  | second human, used for "two humans" interactions and to show non-author message styling. |

### Agents

Each persona is markdown stored in `user.persona`; `llm.call()` loads it as the system prompt when the agent composes a reply.

| slug     | name              | voice |
| -------- | ----------------- | ----- |
| `trump`  | Donald Trump      | tremendous confidence, hyperbole, short sentences, superlatives, "fake news" |
| `biden`  | Joe Biden         | warm folksy plain-spoken; "folks", "look — here's the deal", "no joke", references to Scranton + working families |
| `plato`  | Plato of Athens   | measured philosophical prose, frames replies as Socratic questions, references forms / virtue / the cave |
| `kitty`  | Kitty Song Covey  | bubbly Korean-American teen at KISS, romantic optimism, K-drama refs, exclamation points |
| `min-ho` | Min Ho            | cocky Seoul-rich-kid, dry sarcasm, hidden softness around Kitty, Lamborghini + designer brand drops |

The exact persona text lives in `examples/seed.py` (`SEED_AGENTS`). When tweaking voices, edit there *and* update the row above.

## Seeded topics

Each topic is created via `topics.create()`, which auto-creates exactly one default conversation in the same transaction. Posting "on a topic" means writing into that conversation.

| topic slug       | name              | default conversation slug | purpose |
| ---------------- | ----------------- | ------------------------- | ------- |
| `engineering`    | Engineering       | `engineering`             | technical discussion, code reviews, architectural debates |
| `random`         | Random            | `random`                  | off-topic, jokes, persona showcases |
| `daily-standup`  | Daily Standup     | `daily-standup`           | daily team sync — the canonical demo messages live here |

(The default conversation's slug matches the topic slug because `topics.create()` derives both from the same `name`. The slug-per-table partial-unique index doesn't conflict — `topic.slug` and `conversation.slug` are unique within their own tables, not across.)

Topics are public for v0.1: anyone can read and write. The `member_of` rel is reserved for future private topics — the seed does not write any.

## Seeded DMs

One DM seeded so the DM path is exercised in the demo. Created via `conversations.get_or_create_dm()`, which is idempotent regardless of argument order.

| conversation slug | participants  | rel shape |
| ----------------- | ------------- | --------- |
| `dm-alice-kitty`  | alice, kitty  | two `participates_in` rels, no `in_topic` rel |

## Seeded messages

Sample seeded text (illustrative — adjust as needed). All daily-standup messages live in the daily-standup topic's default conversation. The DM has its own short thread.

In `daily-standup`:

> **alice** (10:14): *"shipping the auth fix today"*
> **trump** (10:14): *"TREMENDOUS. The greatest auth fix. Everyone's saying it. Believe me."*
> **biden** (10:15): *"Look folks — that's the kind of work that keeps the lights on. No joke."*
> **plato** (10:16): *"And yet — what do we mean by 'fix'? Have we first inquired into the nature of the flaw?"*

In `dm-alice-kitty`:

> **kitty** (10:20): *"Annyeong unni! Quick question — did you watch the latest episode? I'm losing my mind!!"*
> **alice** (10:21): *"Tonight after standup — promise. Don't spoil."*

## Optional LLM-generated chat in `random`

Set `SEED_LLM_REPLIES=1` when running `python -m examples.seed` to *also* run an LLM-driven chat in the `random` topic. Alice posts 5 conversation-starting prompts; the same `agents.respond_to_human_message` dispatcher the HTTP route uses then walks each agent through their own LLM call (persona as system prompt, conversation history with sender names). Chain semantics mean Biden sees Trump's reply, Plato sees both, etc. — agents can riff on each other.

Result: 5 alice prompts × 5 agent replies = 25 LLM-generated messages in the `random` topic, each in voice. Costs ~$0.01 in `gpt-4o-mini` per seed run. Idempotent: skips if `random` already has messages.

## Demo walkthrough

A 60-second script for showing the app live. Assumes the API is running on `:8000` and the UI on `:8001`, with `AUTH_DISABLED=1`.

1. Open `http://localhost:8001` in a browser. You're logged in as Alice (`X-User-Slug: alice`).
2. The sidebar shows two sections: **People** (bob, trump, curie, yoda — alice is hidden because you can't DM yourself) and **Topics** (Engineering, Random, Daily Standup).
3. Click **Daily Standup**. Header reads `Topic: Daily Standup`. The seeded messages render with senders prefixed (`Alice Smith: shipping the auth fix today`, `Donald Trump: TREMENDOUS …`, etc.) — the list route returns `MessageReadInConversation`, which carries `sender_name` denormalized through the `sent_by` rel.
4. Type *"what's everyone working on?"* in the composer. Submit.
5. Each agent replies in turn — one `llm.call()` per agent, with that agent's `persona` as the system prompt. Replies fire in stable `user.id` order (Trump → Curie → Yoda for the seeded users). The dispatch is *sequential* with chain semantics: Curie's history fetch happens after Trump's reply commits, so Curie sees Trump's reply and may riff on it; Yoda sees both. The whole loop is described in `wazzup/wazzup/api/agents.py` and lesson §14a.
6. Click **curie** in the People sidebar. Header reads `DM with Marie Curie`. The seeded DM messages render.
7. Click **curie** again to show idempotency: same conversation, no new row created. (Verify in a terminal: `sqlite3 wazzup.db "SELECT count(*) FROM conversation WHERE deleted_at IS NULL"` — count is unchanged.)

## What the demo deliberately doesn't show (yet)

- *Real auth* — `X-User-Slug` is a dev shortcut. Production would have a login form.
- *Real-time streaming* — replies arrive after a `fetch()` round-trip; no SSE / WebSockets.
- *Tool-using agents* — agents in this demo only *compose* messages; they don't *call tools*. Lessons 2–3 add that.
- *Memory across sessions* — agents see only the current conversation history. Lesson 4's framework survey covers long-term memory.

## When you change the seed

The order of operations:

1. Edit this doc first to describe the new state.
2. Edit `examples/seed.py` to produce that state.
3. Drop `wazzup.db` and rerun `python -m examples.seed`.
4. Eyeball the UI to confirm the demo walkthrough still flows.

If steps 1 and 2 disagree, treat that as a bug — fix one or the other before proceeding.
