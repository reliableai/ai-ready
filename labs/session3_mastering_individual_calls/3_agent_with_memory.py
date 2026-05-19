"""
Agent with Sliding Window + Memory Summary

Older turns are compressed into a summary.
Recent turns are kept verbatim.
This bounds cost while preserving important context.

Run: uv run python labs/02_standalone_agents/3_agent_with_memory.py

Configuration:
- WINDOW_TURNS: How many recent turns to keep verbatim
- SUMMARY_STYLE: How to format the memory (BULLETS, JSON, TLDR)
"""
import time
from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

# ----------------------------
# Configuration
# ----------------------------
MODEL = "gpt-4.1-mini"
WINDOW_TURNS = 6  # Keep last N turns verbatim (turn = user + assistant)
TEMPERATURE = 0.7

# Choose summary style: "BULLETS", "JSON", or "TLDR"
SUMMARY_STYLE = "BULLETS"

# ----------------------------
# Summary Prompts
# ----------------------------
SUMMARY_PROMPTS = {
    "BULLETS": """You are maintaining a long-term memory summary of a conversation.
Update the MEMORY so it remains short, factual, and useful.

Rules:
- Keep at most 10 bullet points
- Focus on: facts, preferences, goals, decisions, commitments
- If something is corrected later, reflect the latest info
- Avoid quoting long text verbatim

Return ONLY the updated MEMORY as bullet points.""",

    "JSON": """You are maintaining a long-term memory of a conversation.
Update the MEMORY into a compact JSON object:
{
  "facts": [...],
  "preferences": [...],
  "goals": [...],
  "decisions": [...]
}

Rules:
- Each list should have <= 5 items
- Keep items short (< 15 words each)
- Reflect the latest corrections

Return ONLY valid JSON.""",

    "TLDR": """You are maintaining a long-term memory summary of a conversation.
Update MEMORY into a very short paragraph (max 60 words).
Focus on stable facts, decisions, and what matters for continuing.
Return ONLY the updated MEMORY.""",
}


def summarize_turns(turns: List[Dict], existing_memory: str) -> str:
    """Compress conversation turns into a memory summary."""
    transcript = "\n".join([
        f"{m['role'].title()}: {m['content'][:500]}"  # Truncate long messages
        for m in turns
    ])

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SUMMARY_PROMPTS[SUMMARY_STYLE]},
            {"role": "user", "content": f"EXISTING MEMORY:\n{existing_memory or '(empty)'}\n\nNEW TURNS TO INCORPORATE:\n{transcript}"}
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def trim_to_window(conversation: List[Dict], window_turns: int) -> List[Dict]:
    """Keep only the last N turns (user + assistant pairs)."""
    if window_turns <= 0:
        return []

    # Count user messages from the end to identify turn boundaries
    kept = []
    user_count = 0
    for m in reversed(conversation):
        kept.append(m)
        if m["role"] == "user":
            user_count += 1
            if user_count >= window_turns:
                break

    return list(reversed(kept))


def build_messages(memory: str, window: List[Dict], user_input: str) -> List[Dict]:
    """Build the message array for the API call."""
    system_content = f"""You are a helpful assistant.

LONG-TERM MEMORY (summary of earlier conversation):
{memory or '(no prior context)'}

Use this memory as context when relevant. Focus on the recent conversation."""

    messages = [{"role": "system", "content": system_content}]
    messages.extend(window)
    messages.append({"role": "user", "content": user_input})
    return messages


def main():
    print("=" * 60)
    print("AGENT WITH MEMORY")
    print(f"Window: last {WINDOW_TURNS} turns | Summary style: {SUMMARY_STYLE}")
    print("Older turns are compressed into memory.")
    print("Type 'exit' to quit.")
    print("=" * 60)
    print()

    conversation: List[Dict] = []
    memory_summary: str = ""
    turn_number = 0

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "exit":
            break
        if not user_input:
            continue

        turn_number += 1

        # Check if we need to compress older turns
        window = trim_to_window(conversation, WINDOW_TURNS)
        older = conversation[:max(0, len(conversation) - len(window))]

        if older:
            print("\n[Compressing older turns into memory...]")
            memory_summary = summarize_turns(older, memory_summary)
            conversation = window  # Drop older turns from active conversation

        # Build messages: system (with memory) + window + new user input
        messages = build_messages(memory_summary, conversation, user_input)

        start = time.time()
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=TEMPERATURE,
        )
        elapsed = time.time() - start

        reply = response.choices[0].message.content
        usage = response.usage

        # Update conversation history
        conversation.append({"role": "user", "content": user_input})
        conversation.append({"role": "assistant", "content": reply})

        print(f"\nAssistant ({elapsed:.2f}s):")
        print(reply)
        print()
        print(f"--- Turn {turn_number} Stats ---")
        print(f"Window messages: {len(conversation)}")
        print(f"Memory length: {len(memory_summary)} chars")
        print(f"Input tokens: {usage.prompt_tokens}")
        print(f"Output tokens: {usage.completion_tokens}")

        if memory_summary:
            print(f"\n[Current Memory Preview]")
            preview = memory_summary[:300] + "..." if len(memory_summary) > 300 else memory_summary
            print(preview)
        print()


if __name__ == "__main__":
    main()
