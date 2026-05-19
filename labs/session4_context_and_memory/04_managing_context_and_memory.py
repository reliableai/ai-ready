# %% [markdown]
# # Lesson 4: Managing Context
#
# **The central challenge:** LLMs are stateless functions. They don't remember anything — you must send the relevant context with every request. This has profound implications for cost, latency, and architecture.
#
# This notebook walks through five strategies, each solving a problem the previous one creates:
#
# | # | Strategy | Problem it solves | New problem it creates |
# |---|----------|-------------------|----------------------|
# | 1 | **Stateless** | Simplest possible call | No memory at all |
# | 2 | **Stateful (full history)** | Model remembers everything | Quadratic cost growth |
# | 3 | **Sliding window** | Bounded cost | Forgets old context |
# | 4 | **Window + summarization** | Preserves old context cheaply | Lossy compression |
# | 5 | **Long-term memory** | Persists across sessions | Needs user identity + storage |
#
# Run cells in order. Each section builds on the previous one.

# %%
import os, time, json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY not found — add it to .env")

client = OpenAI()
MODEL = "gpt-4.1-mini"
print(f"Client ready — using {MODEL}")

# %% [markdown]
# ---
# ## 1) Stateless: each call is independent
#
# The Chat Completions API is **stateless by design**. There is no server-side session. The model only sees the `messages` array you send in *that* request — nothing more.
#
# Below we make two separate calls. Turn 1 tells the model a name; turn 2 asks for it. Since turn 2 doesn't include turn 1's messages, the model has no idea.

# %%
# Turn 1: tell the model your name
turn1_messages = [{"role": "user", "content": "My name is Alice."}]
print("Turn 1 prompt messages:")
print(json.dumps(turn1_messages, indent=2))

turn1 = client.chat.completions.create(
    model=MODEL,
    messages=turn1_messages,
)
print("Turn 1:", turn1.choices[0].message.content)

# Turn 2: ask for your name — but we DON'T send turn 1
turn2_messages = [{"role": "user", "content": "What is my name?"}]
print("\nTurn 2 prompt messages:")
print(json.dumps(turn2_messages, indent=2))

turn2 = client.chat.completions.create(
    model=MODEL,
    messages=turn2_messages,
)
print("Turn 2:", turn2.choices[0].message.content)

# %% [markdown]
# The model can't answer because it literally never saw the first message. Each call is a clean slate.
#
# **When stateless is fine:** single-shot tasks (translation, classification, extraction) where each request is self-contained. Cost per call is constant and predictable.
#
# ---
# ## 2) Responses API: provider-managed memory
#
# The Responses API can keep conversation state **server-side**. You can chain turns using `previous_response_id` and the model will remember earlier turns without you resending the full message history.
#
# Later, we'll implement memory ourselves with Chat Completions (first by replaying the full history, then with bounded-context strategies like windows and summarization).

# %%
print("=== Responses API (server-side memory) ===\n")
try:
    resp1_input = "My name is Alice."
    print("Turn 1 input:")
    print(resp1_input)
    resp1 = client.responses.create(
        model=MODEL,
        input=resp1_input,
    )
    print("Turn 1:", resp1.output_text)

    resp2_input = "What is my name?"
    print("\nTurn 2 input:")
    print(resp2_input)
    resp2 = client.responses.create(
        model=MODEL,
        input=resp2_input,
        previous_response_id=resp1.id,
    )
    print("Turn 2:", resp2.output_text)
except Exception as e:
    print("Responses API demo unavailable in this environment.")
    print(type(e).__name__, e)

# %% [markdown]
# ## 2) Stateful: replay the full history
history = []

# Turn 1
history.append({"role": "user", "content": "My name is Alice."})
print("User:", history[-1]["content"])

r1 = client.chat.completions.create(model=MODEL, messages=history)
a1 = r1.choices[0].message.content
history.append({"role": "assistant", "content": a1})
print("Assistant:", a1)
print("Messages so far:")
print(json.dumps(history, indent=2))

print("\nTurn 2 — now the model sees BOTH messages")


# Turn 2 — now the model sees BOTH messages
next_prompt = "What is my name?"
history.append({"role": "user", "content": next_prompt})
print("\nUser:", next_prompt)
print("Prompt sent on turn 2 (messages payload):")
print(json.dumps(history, indent=2))
r2 = client.chat.completions.create(model=MODEL, messages=history)
a2 = r2.choices[0].message.content
history.append({"role": "assistant", "content": a2})
print("Assistant:", a2)
print("Messages so far:")
print(json.dumps(history, indent=2))

print(f"\nMessages sent on turn 2: {len(history) - 1}")  # minus the last assistant reply
print(f"Prompt tokens on turn 2: {r2.usage.prompt_tokens}")







# %% [markdown]
# It works — but notice: on turn 2, we sent *all* previous messages plus the new one. On turn 50, we'd send 50 turns of history. On turn 500, we'd send 500 turns. This is where cost becomes a problem.
#
# ---
# ## 3) Measuring the quadratic problem
#
# Let's run a real multi-turn conversation and watch the token count grow. If each turn adds ~300 tokens to the history, the input tokens on turn N are roughly 300N. The **cumulative** input tokens across all turns grow as ~150N² — quadratic.

# %%
prompts = [
    "My name is Alice and I live in Trento.",
    "I work as a data scientist at a small startup.",
    "I prefer concise answers — no fluff, just the key points.",
    "I'm building a recommendation engine using collaborative filtering.",
    "We're using PyTorch and the MovieLens 1M dataset.",
    "What RMSE should I target for a good baseline?",
    "Summarize everything you know about me so far.",
    "What details might be missing from my project description?",
    "Give me three concrete next steps for my project.",
    "What is my name, where do I live, and what am I working on?",
    "how are you today? i am fine, by the way",
    "what shall I do today?",
]

history = []
stats = []

for i, prompt in enumerate(prompts, start=1):
    history.append({"role": "user", "content": prompt})
    r = client.chat.completions.create(model=MODEL, messages=history, temperature=0.2)
    reply = r.choices[0].message.content
    history.append({"role": "assistant", "content": reply})
    print(f"\n--- Turn {i} ---\nUser: {prompt}\nAssistant: {reply}\n")

    stats.append({
        "turn": i,
        "prompt_tokens": r.usage.prompt_tokens,
        "completion_tokens": r.usage.completion_tokens,
    })

# Print the growth table
print(f"{'turn':>4}  {'prompt_tokens':>14}  {'completion_tokens':>18}  {'cumulative_input':>17}")
cumulative = 0
for s in stats:
    cumulative += s["prompt_tokens"]
    print(f"{s['turn']:>4}  {s['prompt_tokens']:>14,}  {s['completion_tokens']:>18,}  {cumulative:>17,}")

# %% [markdown]
# Notice how `prompt_tokens` grows with every turn — each turn re-sends all previous turns. The last turn pays for the entire conversation.
#
# **The cost math:** at gpt-4.1-mini pricing ($0.40/M input tokens), a 10-turn conversation is pennies. But scale to 500 turns and you're at ~$15 cumulative input cost for a single conversation. The model choice matters too — cheaper models (gpt-4.1-nano at $0.10/M) reduce cost 4×.
#
# **Latency grows too:** more input tokens = more processing time. By turn 100+, users may wait 5-10 seconds per response.
#
# ---
# ## 4) Sliding window: bounded cost, lossy context
#
# The simplest fix: only send the last N turns. Cost is now **bounded** regardless of conversation length.

# %%
# Demo: window of 2 turns on a 10-turn conversation
full_history = history  # from section 3
WINDOW_TURNS = 2
window = full_history[-2 * WINDOW_TURNS :]

print(f"Full history: {len(full_history)} messages ({len(full_history)//2} turns)")
print(f"Window (last 2 turns): {len(window)} messages\n")

for msg in window:
    role = msg["role"].upper()
    preview = msg["content"][:100].replace("\n", " ")
    print(f"  [{role}] {preview}{'...' if len(msg['content']) > 100 else ''}")

# %%
# Now ask a question that REQUIRES early context
# With a small window, the model won't know Alice's name or project


new_prompt = "What is my name and what project am I working on?"

windowed_messages = window + [{"role": "user", "content": new_prompt}]

print("What goes to LLM:\n")
for msg in windowed_messages:
    print(f"  [{msg['role'].upper()}] {msg['content']}")


r = client.chat.completions.create(model=MODEL, messages=windowed_messages, temperature=0.2)
# print("With window=2 (early context lost):")
print("Response:\n", r.choices[0].message.content)
print(f"\nPrompt tokens: {r.usage.prompt_tokens} (bounded!)")

# %% [markdown]
# The model can't answer — Alice's name and project details were in turns 1-5, outside the window. Cost is bounded, but we've lost important context.
#
#
# We need a way to *compress* old context, not just drop it.
#
# ---
# ## 5) Answer + memory in one call
#
# Instead of a separate summarization step, we can ask the model to do both in a single call:
# 1. Answer the user's question
# 2. Update a running memory summary
#
# Each turn sends: `[system prompt with current memory] + [user message]` → model returns `{"answer": "...", "updated_memory": {...}}`
#
# The memory is a structured JSON dict that grows and evolves across turns. Cost is **bounded** — we never send the full history, just the compact memory.

# %%
from jinja2 import Template


template_path = Path("prompt_templates/summarize_memory.j2")
if not template_path.exists():
    template_path = Path("labs/03_context/prompt_templates/summarize_memory.j2")

template_text = template_path.read_text()
PROMPT_TEMPLATE = Template(template_text)


# %%
# Single turn demo
memory = {}
user_message = "Hi! My name is Alice and I live in Trento."
memory_json = json.dumps(memory)
prompt = PROMPT_TEMPLATE.render(memory=memory_json, user_message=user_message)
r = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "user", "content": prompt},
    ],
    temperature=0.3,
    response_format={"type": "json_object"},
)
parsed = json.loads(r.choices[0].message.content)
answer = parsed.get("answer", "")
memory = parsed.get("updated_memory", memory)

print(f"Answer: {answer}")
print(f"Memory: {json.dumps(memory, indent=2)}")
print(f"Prompt tokens: {r.usage.prompt_tokens}")

# %%
# Second turn — memory carries over, no history needed
user_message = "I work as a data scientist. I prefer concise answers."
memory_json = json.dumps(memory)
prompt = PROMPT_TEMPLATE.render(memory=memory_json, user_message=user_message)
r = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "user", "content": prompt},
    ],
    temperature=0.3,
    response_format={"type": "json_object"},
)
parsed = json.loads(r.choices[0].message.content)
answer = parsed.get("answer", "")
memory = parsed.get("updated_memory", memory)

print(f"Answer: {answer}")
print(f"Memory: {json.dumps(memory, indent=2)}")
print(f"Prompt tokens: {r.usage.prompt_tokens}")

# Third turn — test recall
user_message = "What is my name and what do I do?"
memory_json = json.dumps(memory)
prompt = PROMPT_TEMPLATE.render(memory=memory_json, user_message=user_message)
r = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "user", "content": prompt},
    ],
    temperature=0.3,
    response_format={"type": "json_object"},
)
parsed = json.loads(r.choices[0].message.content)
answer = parsed.get("answer", "")
memory = parsed.get("updated_memory", memory)

print(f"\nAnswer: {answer}")
print(f"Prompt tokens: {r.usage.prompt_tokens} (bounded!)")

# %% [markdown]
# The model answers correctly using only the compact memory — no conversation history needed.
#
# **How it works:** each turn, the model sees only the system prompt (with memory JSON) and the current user message. The memory acts as a lossy compression of the entire conversation so far.
#
# ```
# [SYSTEM]  You are a helpful assistant.
#           CURRENT MEMORY: {"facts": ["Name: Alice", "Location: Trento", ...], ...}
#           ... return {"answer": "...", "updated_memory": {...}} ...
#
# [USER]    What is my name and what do I do?    ← only the current turn
# ```
#
# One API call per turn. Bounded tokens. No growing history.
#
# ---
# ## 6) Multi-turn conversation with memory
#
# Let's run a longer conversation and watch the memory evolve.

# %%
prompts = [
    "Hi! I'm Marco, a PhD student in Trento studying graph neural networks.",
    "I'm applying GNNs to drug discovery — specifically protein-ligand binding prediction.",
    "I use PyTorch Geometric and I prefer short, direct explanations.",
    "What are the main challenges in GNN-based drug discovery?",
    "How does message passing relate to molecular graphs?",
    "Can you explain virtual nodes and why they help?",
    "What evaluation metrics should I use for binding affinity prediction?",
    "Remind me: what's my research topic and what framework do I use?",
]

memory = {}
turn_stats = []

for i, prompt in enumerate(prompts):
    memory_json = json.dumps(memory)
    prompt = PROMPT_TEMPLATE.render(memory=memory_json, user_message=prompt)
    r = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    parsed = json.loads(r.choices[0].message.content)
    answer = parsed.get("answer", "")
    memory = parsed.get("updated_memory", memory)

    turn_stats.append({
        "turn": i,
        "prompt_tokens": r.usage.prompt_tokens,
        "memory_size": len(json.dumps(memory)),
    })
    print(f"--- Turn {i} ({r.usage.prompt_tokens} prompt tokens) ---")
    print(f"You:  {prompt}")
    print(f"\nAsst: {answer[:200]}{'...' if len(answer) > 200 else ''}\n")
    print(f"Memory: {json.dumps(memory, indent=2)}\n")

# Token count stays bounded
print("\n=== Token growth (bounded!) ===")
print(f"{'turn':>4}  {'prompt_tokens':>14}  {'memory_json':>12}")
for s in turn_stats:
    print(f"{s['turn']:>4}  {s['prompt_tokens']:>14,}  {s['memory_size']:>12,}")

# %%
# Show the final memory
print("=== Final memory ===")
print(json.dumps(memory, indent=2))

# %% [markdown]
# Key observation: the `prompt_tokens` column stays roughly bounded even as the conversation grows. The memory summary grows slowly (it gets compressed further on each update), while the window stays fixed. Compare this to section 3 where tokens grew linearly per turn and quadratically in total.
#
# ---
# ## 7) Long-term memory: persisting across sessions
#
# Everything above is **short-term memory** — it dies when the conversation ends. Real applications need to remember users *across* conversations.
#
# The pattern:
# 1. **End of session:** ask the LLM to extract structured facts from the conversation
# 2. **Save** those facts to disk (or a database), keyed by user ID
# 3. **Start of next session:** load the user's facts and inject them into the system prompt
#
# This is the pattern behind ChatGPT's "Memory" feature. It requires **user identity** — you need to know *whose* facts to load.

# %%
import tempfile

def extract_long_term_facts(conversation, existing_memory=None):
    """Ask the LLM to extract facts worth remembering across sessions.

    The LLM itself decides what's important enough to persist:
    facts, preferences, expertise, decisions — not ephemeral details.
    """
    if existing_memory is None:
        existing_memory = {"facts": [], "preferences": []}

    transcript = "\n".join(
        f"{m['role'].title()}: {m['content'][:300]}" for m in conversation
    )
    r = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": (
                "Extract LONG-TERM memory from this conversation.\n"
                "Include: facts about the user, preferences, decisions, expertise.\n"
                "Exclude: temporary details, one-off questions, ephemeral context.\n"
                "Return valid JSON: {\"facts\": [...], \"preferences\": [...]}\n"
                "Max 10 items per list. Merge with existing memory, remove duplicates."
            )},
            {"role": "user", "content": (
                f"EXISTING MEMORY:\n{json.dumps(existing_memory)}\n\n"
                f"CONVERSATION:\n{transcript}"
            )},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(r.choices[0].message.content)
    except json.JSONDecodeError:
        return existing_memory


# Use a temp file so we don't leave artifacts
memory_file = Path(tempfile.mkdtemp()) / "user_memories.json"


def save_user_memory(user_id, memory_data):
    """Save long-term memory for a user to disk."""
    all_memories = json.loads(memory_file.read_text()) if memory_file.exists() else {}
    all_memories[user_id.lower()] = memory_data
    memory_file.write_text(json.dumps(all_memories, indent=2))


def load_user_memory(user_id):
    """Load long-term memory for a user from disk."""
    if memory_file.exists():
        all_memories = json.loads(memory_file.read_text())
        return all_memories.get(user_id.lower(), {"facts": [], "preferences": []})
    return {"facts": [], "preferences": []}

# %%
# ── SESSION 1: Marco has a conversation ──────────────────────────

session1_conversation = [
    {"role": "user", "content": "Hi, I'm Marco. I'm a PhD student in Trento."},
    {"role": "assistant", "content": "Nice to meet you, Marco! What are you working on?"},
    {"role": "user", "content": "Graph neural networks for drug discovery — protein-ligand binding."},
    {"role": "assistant", "content": "Fascinating area! What tools are you using?"},
    {"role": "user", "content": "PyTorch Geometric mostly. And I prefer short, direct explanations."},
    {"role": "assistant", "content": "Noted — I'll keep things concise. How's the research going?"},
]

print("SESSION 1: Extracting long-term facts...")
extracted = extract_long_term_facts(session1_conversation)
save_user_memory("marco", extracted)

print(f"  Facts:       {extracted.get('facts', [])}")
print(f"  Preferences: {extracted.get('preferences', [])}")
print(f"  Saved to: {memory_file}\n")

# ── SESSION 2: New conversation — load memory ───────────────────

print("SESSION 2: Loading memory for 'marco'...")
loaded = load_user_memory("marco")
print(f"  Loaded: {json.dumps(loaded, indent=2)}\n")

# Use the loaded memory in a new conversation
session2_messages = [
    {"role": "system", "content": (
        "You are a helpful assistant.\n\n"
        f"LONG-TERM MEMORY (from previous sessions):\n"
        f"Facts: {loaded.get('facts', [])}\n"
        f"Preferences: {loaded.get('preferences', [])}\n\n"
        "Use this memory naturally — don't say 'according to my records'."
    )},
    {"role": "user", "content": "What do you know about me?"},
]

r = client.chat.completions.create(model=MODEL, messages=session2_messages, temperature=0.3)
print("Marco asks: 'What do you know about me?'")
print(f"Assistant: {r.choices[0].message.content}")

# Clean up temp file
memory_file.unlink(missing_ok=True)
memory_file.parent.rmdir()

# %% [markdown]
# The model "remembers" Marco from a previous session it never actually saw — because we loaded his facts into the system prompt.
#
# **Privacy note:** long-term memory means you're storing personal data. In production you need: clear data policies, user controls (view/delete), secure storage, and compliance with regulations (GDPR etc.). Our JSON file is fine for learning, not for production.
#
# | Product | Short-term memory | Long-term memory |
# |---------|-------------------|------------------|
# | ChatGPT | Conversation history | "Memory" feature (extracted facts) |
# | Claude | Conversation context | Project Knowledge (uploaded docs) |
# | GitHub Copilot | Current file + open tabs | Repository patterns, coding style |
# | Customer service bot | Current ticket | Customer history, past issues |
#
# ---
# ## 8) Exercises
#
# Try these to deepen your understanding.

# %% [markdown]
# ## Exercises
#
# See **`session4_exercises.py`** for interactive exercises
# (with solutions in `session4_solutions.py`):
#
# 1. **Selective memory** — remember only project-relevant info, not chitchat
# 2. **Memory format comparison** — structured vs flat list vs paragraph
# 3. **Token-based windowing** — budget by tokens, not turns

# %% [markdown]
# ---
# ## CLI scripts
#
# For the full interactive experience (try these in your terminal):
#
# ```bash
# uv run python labs/03_context/1_stateless_agent.py
# uv run python labs/03_context/2_stateful_agent.py
# uv run python labs/03_context/3_agent_with_memory.py
# uv run python labs/03_context/4_agent_with_long_term_memory.py
# ```
#
# ---
# ## Takeaways
#
# - **LLMs are stateless.** Context is your responsibility — you send it, or it doesn't exist.
# - **Full history doesn't scale.** Cost and latency grow quadratically with conversation length.
# - **Memory is lossy compression.** You choose what to keep and what to lose. The summarizer decides what matters.
# - **Short-term vs long-term.** Short-term resets with the conversation; long-term persists across sessions and requires user identity.
# - **Design for your constraints.** Window size, summary format, persistence strategy — all tradeoffs with no universal right answer.
