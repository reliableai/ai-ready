# %% [markdown]
# # Session 4: Exercises — Managing Context
#
# These exercises build on the session. Run `04_managing_context_and_memory.py` first
# so you understand the patterns, then come back here.

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
# ## Exercise 1: Selective memory — remember only what matters
#
# The lesson's memory template stores *everything*: facts, preferences, goals.
# But what if you only want the model to remember **project-related** information
# and deliberately forget personal small talk?
#
# **Task:** Modify the prompt template so that:
# - It remembers: project details, technical decisions, domain knowledge
# - It ignores: greetings, chitchat, personal feelings, off-topic remarks
#
# Then run this conversation and check what ends up in memory:

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

# TODO: run this conversation through the selective template and inspect the memory
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

# Your code here — loop through selective_prompts using SELECTIVE_TEMPLATE
# After each turn, print the answer and the memory
# At the end, check: does memory contain "feeling great", "pasta", "tired"? It shouldn't.

# %% [markdown]
# ---
# ## Exercise 2: Memory format comparison
#
# The lesson uses structured memory: `{"facts": [...], "preferences": [...], "goals": [...]}`.
# Try two alternative formats and compare:
#
# 1. **Flat list** — `{"memory": ["Name: Marco", "Studies GNNs", ...]}`
# 2. **Paragraph** — `{"memory": "Marco is a PhD student studying GNNs..."}`
#
# Run the same 8-turn Marco conversation with each format. Compare:
# - Which preserves the most information after 8 turns?
# - Which is most compact (fewest tokens)?
# - Which produces the best answers?

# %%
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

# TODO: run marco_prompts through each of the three templates
#   (FLAT_LIST_TEMPLATE, PARAGRAPH_TEMPLATE, and the original from the lesson)
# For each, track: final memory content, memory size in chars, prompt_tokens per turn
# Compare the three approaches

# Your code here

# %% [markdown]
# ---
# ## Exercise 3: Token-based windowing
#
# `trim_to_window` counts *turns*. But turns vary wildly in length — a 3-word
# question and a 500-word explanation are both "one turn".
#
# Write `trim_to_token_budget(conversation, max_tokens)` that keeps as many
# recent messages as fit within a token budget.
#
# Hint: a rough token estimate is `len(text) // 4`. For production, use `tiktoken`.

# %%
def trim_to_token_budget(conversation, max_tokens=2000):
    """Keep as many recent messages as fit within a token budget.

    Args:
        conversation: list of message dicts
        max_tokens: approximate token budget for the kept messages

    Returns:
        list of messages that fit within budget, in original order
    """
    # TODO: iterate from the end of conversation, accumulating token estimates
    # Stop when adding the next message would exceed max_tokens
    # Return the kept messages in original order
    pass


# To test, first build a conversation history:
# prompts = [
#     "My name is Alice and I live in Trento.",
#     "I work as a data scientist at a small startup.",
#     "I'm building a recommendation engine using collaborative filtering.",
#     "We're using PyTorch and the MovieLens 1M dataset.",
#     "What RMSE should I target for a good baseline?",
#     "Give me three concrete next steps for my project.",
# ]
# history = []
# for p in prompts:
#     history.append({"role": "user", "content": p})
#     r = client.chat.completions.create(model=MODEL, messages=history, temperature=0.2)
#     history.append({"role": "assistant", "content": r.choices[0].message.content})
#
# trimmed = trim_to_token_budget(history, max_tokens=500)
# print(f"Kept {len(trimmed)} messages within ~500 token budget")
# for m in trimmed:
#     est = len(m["content"]) // 4
#     print(f"  [{m['role']:>9}] ~{est:>3} tokens: {m['content'][:60]}...")
