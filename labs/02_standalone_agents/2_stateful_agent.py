"""
Stateful Agent - Maintains full conversation history

Every turn includes all previous messages.
Watch how token counts grow with each turn.

Run: uv run python labs/02_standalone_agents/2_stateful_agent.py
"""
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

# ---- AGENT STATE ----
conversation = []
turn_number = 0
cumulative_input_tokens = 0

print("=" * 50)
print("STATEFUL AGENT")
print("Full conversation history sent with every turn.")
print("Watch the token counts grow!")
print("Type 'exit' to quit.")
print("=" * 50)
print()

while True:
    user_input = input("You: ").strip()
    if user_input.lower() == "exit":
        break
    if not user_input:
        continue

    turn_number += 1

    # Add user message to history
    conversation.append({"role": "user", "content": user_input})

    start = time.time()

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=conversation,  # Send FULL history
        temperature=0.7,
    )

    elapsed = time.time() - start
    reply = response.choices[0].message.content
    usage = response.usage

    # Add assistant message to history
    conversation.append({"role": "assistant", "content": reply})

    # Track cumulative tokens
    cumulative_input_tokens += usage.prompt_tokens

    print(f"\nAssistant ({elapsed:.2f}s):")
    print(reply)
    print()
    print(f"--- Turn {turn_number} Stats ---")
    print(f"Messages in history: {len(conversation)}")
    print(f"Input tokens this turn: {usage.prompt_tokens}")
    print(f"Output tokens: {usage.completion_tokens}")
    print(f"Cumulative input tokens: {cumulative_input_tokens}")
    print()
