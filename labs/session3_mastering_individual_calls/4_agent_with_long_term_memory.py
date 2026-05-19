"""
Agent with Short-Term AND Long-Term Memory

Short-term: Within this conversation (window + summary)
Long-term: Across conversations, persisted to disk (user facts, preferences)

This demonstrates the two types of memory AI systems need:
- Short-term for conversation coherence
- Long-term for user personalization

Run: uv run python labs/02_standalone_agents/4_agent_with_long_term_memory.py

The agent will:
1. Ask for your name (user identity)
2. Load any existing long-term memory for you
3. Maintain short-term memory during the conversation
4. Extract and save long-term facts when you exit
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

# ----------------------------
# Configuration
# ----------------------------
MODEL = "gpt-4.1-mini"
MEMORY_FILE = Path(__file__).parent / "user_memories.json"
WINDOW_TURNS = 4  # Keep last N turns as short-term memory


# ----------------------------
# Long-Term Memory (Persistent)
# ----------------------------
def load_all_memories() -> Dict:
    """Load all user memories from disk."""
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE) as f:
            return json.load(f)
    return {}


def save_all_memories(memories: Dict) -> None:
    """Save all user memories to disk."""
    with open(MEMORY_FILE, "w") as f:
        json.dump(memories, f, indent=2)


def get_user_memory(user_id: str) -> Dict:
    """Get long-term memory for a specific user."""
    memories = load_all_memories()
    return memories.get(user_id.lower(), {"facts": [], "preferences": []})


def save_user_memory(user_id: str, memory: Dict) -> None:
    """Save long-term memory for a specific user."""
    memories = load_all_memories()
    memories[user_id.lower()] = memory
    save_all_memories(memories)


# ----------------------------
# Memory Extraction (LLM)
# ----------------------------
def extract_long_term_facts(
    conversation: List[Dict],
    existing_memory: Dict
) -> Dict:
    """
    Ask the LLM to extract facts worth remembering long-term.

    This is the key insight: the LLM itself decides what's important
    enough to persist across conversations.
    """
    transcript = "\n".join([
        f"{m['role'].title()}: {m['content'][:300]}"
        for m in conversation
    ])

    existing_facts = existing_memory.get("facts", [])
    existing_prefs = existing_memory.get("preferences", [])

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "system",
            "content": """You are extracting LONG-TERM memory from a conversation.

Long-term memory should include:
- Facts about the user (name, job, location, projects)
- User preferences (communication style, interests, dislikes)
- Important decisions or commitments made
- Expertise areas or skill levels

Do NOT include:
- Temporary conversation details
- Questions asked during this session only
- Anything that wouldn't matter in a future conversation

Return valid JSON with this structure:
{
  "facts": ["fact1", "fact2", ...],
  "preferences": ["pref1", "pref2", ...]
}

Keep each list to max 10 items. Merge with existing memory, removing duplicates."""
        }, {
            "role": "user",
            "content": f"""EXISTING LONG-TERM MEMORY:
Facts: {existing_facts}
Preferences: {existing_prefs}

NEW CONVERSATION TO ANALYZE:
{transcript}

Extract updated long-term memory:"""
        }],
        temperature=0,
        response_format={"type": "json_object"}
    )

    try:
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        return existing_memory


def summarize_short_term(conversation: List[Dict]) -> str:
    """Compress older turns into short-term summary."""
    if len(conversation) < 4:
        return ""

    transcript = "\n".join([
        f"{m['role'].title()}: {m['content'][:200]}"
        for m in conversation[:-4]  # Everything except last 4 messages
    ])

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "system",
            "content": "Summarize this conversation in 2-3 sentences. Focus on what was discussed and any decisions made."
        }, {
            "role": "user",
            "content": transcript
        }],
        temperature=0,
    )

    return response.choices[0].message.content.strip()


# ----------------------------
# Agent
# ----------------------------
def build_messages(
    long_term_memory: Dict,
    short_term_summary: str,
    recent_conversation: List[Dict],
    user_input: str
) -> List[Dict]:
    """Build the message array with both memory types."""

    # Format long-term memory
    facts = long_term_memory.get("facts", [])
    prefs = long_term_memory.get("preferences", [])

    long_term_str = ""
    if facts:
        long_term_str += "Facts about this user:\n" + "\n".join(f"- {f}" for f in facts)
    if prefs:
        long_term_str += "\n\nUser preferences:\n" + "\n".join(f"- {p}" for p in prefs)

    system_content = f"""You are a helpful assistant with memory.

=== LONG-TERM MEMORY (persists across conversations) ===
{long_term_str or "(No long-term memory yet for this user)"}

=== SHORT-TERM MEMORY (this conversation only) ===
{short_term_summary or "(Conversation just started)"}

Use this memory naturally. Don't explicitly mention "my memory says" - just know these things about the user."""

    messages = [{"role": "system", "content": system_content}]
    messages.extend(recent_conversation)
    messages.append({"role": "user", "content": user_input})

    return messages


def main():
    print("=" * 60)
    print("AGENT WITH SHORT-TERM AND LONG-TERM MEMORY")
    print("=" * 60)
    print()
    print("This agent remembers you across conversations!")
    print("- Short-term: What we discuss now (window + summary)")
    print("- Long-term: Facts about you (saved to disk)")
    print()

    # Get user identity
    user_id = input("What's your name? ").strip()
    if not user_id:
        user_id = "anonymous"

    # Load long-term memory
    long_term_memory = get_user_memory(user_id)

    if long_term_memory.get("facts") or long_term_memory.get("preferences"):
        print(f"\n[Loaded long-term memory for '{user_id}']")
        if long_term_memory.get("facts"):
            print(f"  Facts: {long_term_memory['facts'][:3]}...")
    else:
        print(f"\n[No existing memory for '{user_id}' - starting fresh]")

    print()
    print("Type 'exit' to quit (memories will be saved)")
    print("-" * 60)
    print()

    conversation: List[Dict] = []
    short_term_summary: str = ""
    turn_number = 0

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "exit":
            break
        if not user_input:
            continue

        turn_number += 1

        # Update short-term memory if conversation is getting long
        if len(conversation) > WINDOW_TURNS * 2:
            print("\n[Compressing older turns to short-term memory...]")
            short_term_summary = summarize_short_term(conversation)
            conversation = conversation[-(WINDOW_TURNS * 2):]

        # Build messages with both memory types
        messages = build_messages(
            long_term_memory,
            short_term_summary,
            conversation,
            user_input
        )

        start = time.time()
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7,
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
        print(f"[Turn {turn_number} | Tokens: {usage.prompt_tokens} in, {usage.completion_tokens} out]")
        print()

    # Save long-term memory on exit
    if conversation:
        print("\n[Extracting long-term memories from this conversation...]")
        updated_memory = extract_long_term_facts(conversation, long_term_memory)
        save_user_memory(user_id, updated_memory)

        print(f"[Saved long-term memory for '{user_id}']")
        if updated_memory.get("facts"):
            print(f"  Facts: {updated_memory['facts']}")
        if updated_memory.get("preferences"):
            print(f"  Preferences: {updated_memory['preferences']}")

    print("\n[Goodbye! Your memories are saved for next time.]")


if __name__ == "__main__":
    main()
