"""wazzup — small chat app where humans and AI users share one model.

**Side effect on import**: ``load_dotenv()`` runs so any code path that
ends up inside the ``wazzup`` package (the FastAPI app via uvicorn,
the ``examples/`` scripts via ``python -m``, pytest) picks up env vars
from a project-root ``.env`` file. The library is in the dependency
list (``pyproject.toml``) but nothing was *calling* it before — the
result was that ``llm.call()`` inside ``examples/seed.py`` failed
silently with a KeyError on ``LLM_API_KEY`` even though the file
existed on disk.

``load_dotenv()`` is idempotent and a no-op when the file is missing
or the vars are already set in the parent shell. Safe to call early.
"""

from dotenv import load_dotenv

load_dotenv()

__version__ = "0.1.0"
