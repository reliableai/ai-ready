"""
Stateless Agent - Each turn starts fresh

The model has no idea what you said before.
This is the simplest possible agent.

Run: uv run python labs/02_standalone_agents/1_stateless_agent.py
"""
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

print("=" * 50)
print("STATELESS AGENT")
print("Each turn is independent. No memory of previous turns.")
print("Type 'exit' to quit.")
print("=" * 50)
print()

while True:
    user_input = input("You: ").strip()
    if user_input.lower() == "exit":
        break
    if not user_input:
        continue

    start = time.time()

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "user", "content": user_input}  # Only current message
        ],
        temperature=0.7,
    )

    elapsed = time.time() - start
    reply = response.choices[0].message.content
    usage = response.usage

    print(f"\nAssistant ({elapsed:.2f}s):")
    print(reply)
    print(f"\n[Tokens: {usage.prompt_tokens} in, {usage.completion_tokens} out]")
    print()
