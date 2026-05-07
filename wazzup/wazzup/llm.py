"""Thin LLM wrapper — section 14 of the lesson.

Single function ``llm.call(messages)``. Reads provider, model, and
API key from environment variables. All three providers (openai,
azure, openrouter) expose OpenAI-compatible chat APIs, so the
dispatch is just "build the right client, call the same method".
"""

import os


def _client():
    """Build the right OpenAI-compatible client based on LLM_PROVIDER."""
    from openai import AzureOpenAI, OpenAI

    provider = os.environ.get("LLM_PROVIDER", "openai")
    api_key = os.environ["LLM_API_KEY"]
    if provider == "openai":
        return OpenAI(api_key=api_key)
    if provider == "openrouter":
        return OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    if provider == "azure":
        return AzureOpenAI(
            api_key=api_key,
            azure_endpoint=os.environ["AZURE_ENDPOINT"],
            api_version=os.environ.get("AZURE_API_VERSION", "2024-02-15-preview"),
        )
    raise ValueError(f"unknown provider: {provider!r}")


def call(messages: list[dict], **kwargs) -> str:
    """OpenAI-style messages in, assistant reply (text) out."""
    model = os.environ["LLM_MODEL"]
    r = _client().chat.completions.create(model=model, messages=messages, **kwargs)
    return r.choices[0].message.content
