"""
Streaming Responses

Instead of waiting for the full response, get tokens as they're generated.
Watch the text appear word by word - like the model is typing.

Run: uv run python labs/01_hello_world/2_streaming.py
"""

import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # Load OPENAI_API_KEY from .env

client = OpenAI()  # Automatically uses OPENAI_API_KEY env var

start = time.time()

stream = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        {"role": "user", "content": "Write a haiku about APIs."}
    ],
    stream=True,
)

print("Response: ", end="", flush=True)

for chunk in stream:
    content = chunk.choices[0].delta.content
    if content:
        print(content, end="", flush=True)

elapsed = time.time() - start
print(f"\n\n⏱ {elapsed:.2f}s (time to full response)")
