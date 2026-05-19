"""
Hello Software 3.0 - Basic Chat Completion

Your first LLM API call. Send a message, get a response.
This is the foundation everything else builds on.

Run: uv run python labs/01_hello_world/1_chat.py
"""

import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # Load OPENAI_API_KEY from .env

client = OpenAI()  # Automatically uses OPENAI_API_KEY env var

start = time.time()

response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        {"role": "user", "content": "Explain Software 3.0 in one sentence."}
    ],
    temperature=0.7,
)

elapsed = time.time() - start

print(response.choices[0].message.content)
print(f"\n⏱ {elapsed:.2f}s")
