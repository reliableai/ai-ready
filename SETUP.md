# Setup

One-time setup for the AI-Ready Engineers repo. Takes ~5 minutes.

## 1. Clone and install

```bash
# Clone the repo
git clone https://github.com/reliableai/ai-design-2026-pub.git
cd ai-design-2026-pub

# Install uv (Python package manager) if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies — creates a .venv and installs everything
uv sync
```

Requires Python 3.13+. `uv` handles the Python version automatically.

## 2. macOS only — portaudio

Needed for the voice demo in Session 1:

```bash
brew install portaudio
```

Linux/Windows: voice demo may need platform-specific audio setup — see the relevant session notebook for notes.

## 3. API keys

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

A shared API key will be provided during the session. All scripts load keys from `.env` via [python-dotenv](https://pypi.org/project/python-dotenv/).

### Alternative: OpenRouter

For text-based examples, [OpenRouter](https://openrouter.ai) provides a unified API to models from OpenAI, Anthropic, Meta, Google, and others — often at lower prices. Get a key at [openrouter.ai/keys](https://openrouter.ai/keys) and add `OPENROUTER_API_KEY` to `.env`.

Voice (Whisper, TTS) and image generation still require OpenAI direct.

## 4. Verify the setup

```bash
uv run pytest labs/tests/test_session1.py -v -m "not slow"
```

If this passes, you're ready for Session 1.

## 5. Ollama (for Session 1 homework)

The Session 1 homework runs a model locally with [Ollama](https://ollama.com).

Install from [ollama.com/download](https://ollama.com/download) (macOS/Linux/Windows), or on Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Then pull and run a small model to verify:

```bash
ollama pull llama3.2
ollama run llama3.2
```

Ollama exposes an OpenAI-compatible API on `http://localhost:11434/v1` — the same `openai` Python SDK works by changing `base_url`.

## Troubleshooting

- **`uv sync` fails on Python version** — `uv python install 3.13` then retry.
- **Voice script errors on macOS** — ensure `portaudio` is installed via Homebrew.
- **`OPENAI_API_KEY` not found** — check that `.env` exists in the repo root and the variable is spelled correctly (no quotes needed around the value).
- **Notebook can't find packages** — start Jupyter with `uv run jupyter lab` so it uses the project's virtualenv.
