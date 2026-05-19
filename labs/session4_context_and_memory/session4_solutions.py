# %% [markdown]
# # Lesson 4: Solutions — Managing Context

# %%
import os, json
from dotenv import load_dotenv
from openai import OpenAI
from jinja2 import Template

load_dotenv()
client = OpenAI()
MODEL = "gpt-4.1-mini"
print(f"Client ready — using {MODEL}")

# %% [markdown]
# ---
# ## Exercise 1: Selective memory
#
# We define a template that instructs the model to only store project-relevant
# facts. Personal chitchat ("feeling great", "pasta", "tired") should be
# filtered out of memory.

# %%
SELECTIVE_TEMPLATE = Template(
    """You are a helpful project assistant.

Task:
1) Answer the user's message.
2) Update the memory — but ONLY with project-relevant information.

RULES FOR MEMORY:
- KEEP: project goals, technical decisions, tools, datasets, results, deadlines
- IGNORE: personal greetings, feelings, chitchat, off-topic remarks
- Max 10 items in the memory list

CURRENT MEMORY:
{{ memory }}

USER MESSAGE:
{{ user_message }}

Return ONLY valid JSON:
{"answer": "...", "updated_memory": {"project": [...]}}"""
)

selective_prompts = [
    "Hey! I'm feeling great today. My name is Giulia.",
    "I'm building a sentiment analysis pipeline for hotel reviews.",
    "The weather in Trento is beautiful right now!",
    "We're using spaCy for NER and a fine-tuned BERT for classification.",
    "I had pasta for lunch, it was amazing.",
    "Our target F1 score is 0.85 on the test set.",
    "I'm a bit tired but let's keep going.",
    "We decided to use stratified 5-fold cross-validation.",
    "Remind me: what is my project about and what tools do I use?",
]

# %% [markdown]
# Run the 9-turn conversation. Watch the memory after each turn —
# project facts accumulate while chitchat is ignored.

# %%
memory = None

for i, user_message in enumerate(selective_prompts, start=1):
    memory_text = "(empty)" if memory is None else json.dumps(memory)
    prompt_text = SELECTIVE_TEMPLATE.render(memory=memory_text, user_message=user_message)

    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt_text}],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    parsed = json.loads(r.choices[0].message.content)
    answer = parsed.get("answer", "")
    memory = parsed.get("updated_memory", memory or {})

    print(f"--- Turn {i} ---")
    print(f"You:  {user_message}")
    print(f"Asst: {answer[:150]}")
    print(f"Memory: {json.dumps(memory)}\n")

# Check: memory should NOT contain feelings, pasta, weather, tired
print("=== Final selective memory ===")
print(json.dumps(memory, indent=2))

# %% [markdown]
# ---
# ## Exercise 2: Memory format comparison
#
# We define three different memory formats (structured, flat list, paragraph)
# and run the same 8-turn conversation with each. Then we compare: which
# preserves the most info? which is most compact? which gives the best recall?

# %%
# Define the three templates — each asks the model to store memory differently.

STRUCTURED_TEMPLATE = Template(
    """You are a helpful assistant.

Task:
1) Answer the user's message.
2) Update the memory summary.

CURRENT MEMORY:
{{ memory }}

USER MESSAGE:
{{ user_message }}

Rules:
- Update the memory with any new facts, preferences, or goals from this exchange
- Max 10 items total across all memory lists
- Return ONLY valid JSON, no other text

Return JSON with this shape:
{"answer": "...", "updated_memory": {"facts": [...], "preferences": [...], "goals": [...]}}"""
)

FLAT_LIST_TEMPLATE = Template(
    """You are a helpful assistant.

Task:
1) Answer the user's message.
2) Update the memory as a flat list of key facts.

CURRENT MEMORY:
{{ memory }}

USER MESSAGE:
{{ user_message }}

Rules:
- Max 10 items in the memory list
- Return ONLY valid JSON, no other text

Return JSON: {"answer": "...", "updated_memory": {"memory": ["fact 1", "fact 2", ...]}}"""
)

PARAGRAPH_TEMPLATE = Template(
    """You are a helpful assistant.

Task:
1) Answer the user's message.
2) Update the memory as a single concise paragraph.

CURRENT MEMORY:
{{ memory }}

USER MESSAGE:
{{ user_message }}

Rules:
- Keep the paragraph under 100 words
- Return ONLY valid JSON, no other text

Return JSON: {"answer": "...", "updated_memory": {"memory": "paragraph summary..."}}"""
)

marco_prompts = [
    "Hi! I'm Marco, a PhD student in Trento studying graph neural networks.",
    "I'm applying GNNs to drug discovery — specifically protein-ligand binding prediction.",
    "I use PyTorch Geometric and I prefer short, direct explanations.",
    "What are the main challenges in GNN-based drug discovery?",
    "How does message passing relate to molecular graphs?",
    "Can you explain virtual nodes and why they help?",
    "What evaluation metrics should I use for binding affinity prediction?",
    "Remind me: what's my research topic and what framework do I use?",
]


def run_conversation(template, prompts):
    """Run a multi-turn conversation with a given template."""
    memory = None
    stats = []
    last_answer = ""

    for user_message in prompts:
        memory_text = "(empty)" if memory is None else json.dumps(memory)
        prompt_text = template.render(memory=memory_text, user_message=user_message)

        r = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt_text}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(r.choices[0].message.content)
        last_answer = parsed.get("answer", "")
        memory = parsed.get("updated_memory", memory or {})
        stats.append(r.usage.prompt_tokens)

    return memory, stats, last_answer


# %% [markdown]
# Run all three formats and compare. The table shows memory size (chars),
# average prompt tokens per turn, and whether the last-turn recall is correct.

# %%
results = {}
for label, tmpl in [
    ("structured", STRUCTURED_TEMPLATE),
    ("flat_list", FLAT_LIST_TEMPLATE),
    ("paragraph", PARAGRAPH_TEMPLATE),
]:
    memory, stats, last_answer = run_conversation(tmpl, marco_prompts)
    memory_json = json.dumps(memory)
    results[label] = {
        "memory": memory,
        "memory_chars": len(memory_json),
        "avg_tokens": sum(stats) / len(stats),
        "last_answer": last_answer,
    }

print(f"{'Format':<12} {'Memory chars':>12} {'Avg tokens':>11}  Last answer")
print("-" * 80)
for label, r in results.items():
    print(f"{label:<12} {r['memory_chars']:>12,} {r['avg_tokens']:>11.0f}  {r['last_answer'][:60]}")

print()
for label, r in results.items():
    print(f"\n=== {label} memory ===")
    print(json.dumps(r["memory"], indent=2))

# %% [markdown]
# ---
# ## Exercise 3: Token-based windowing
#
# Instead of counting turns, we budget by estimated tokens. We walk backward
# through the conversation, accumulating `len(text) // 4` as a rough estimate,
# and stop before we exceed the budget.

# %%
def trim_to_token_budget(conversation, max_tokens=2000):
    """Keep as many recent messages as fit within a token budget."""
    kept = []
    budget_used = 0

    for msg in reversed(conversation):
        est = len(msg["content"]) // 4
        if budget_used + est > max_tokens:
            break
        kept.append(msg)
        budget_used += est

    return list(reversed(kept))


# Build a 6-turn conversation, then trim it to ~500 tokens.
# Expect: only the last few messages fit — early turns are dropped.
prompts = [
    "My name is Alice and I live in Trento.",
    "I work as a data scientist at a small startup.",
    "I'm building a recommendation engine using collaborative filtering.",
    "We're using PyTorch and the MovieLens 1M dataset.",
    "What RMSE should I target for a good baseline?",
    "Give me three concrete next steps for my project.",
]

history = []
for p in prompts:
    history.append({"role": "user", "content": p})
    r = client.chat.completions.create(model=MODEL, messages=history, temperature=0.2)
    history.append({"role": "assistant", "content": r.choices[0].message.content})

trimmed = trim_to_token_budget(history, max_tokens=500)
print(f"Kept {len(trimmed)} messages within ~500 token budget\n")
for m in trimmed:
    est = len(m["content"]) // 4
    print(f"  [{m['role']:>9}] ~{est:>3} tokens: {m['content'][:60]}...")
