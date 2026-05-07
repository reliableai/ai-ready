"""FastAPI dependencies — section 8 of the lesson.

These are the functions consumed via ``Depends(...)`` across all
routers:

- ``get_db`` — per-request DB connection (yields a sqlite3.Connection,
  commits on success, rolls back on exception, closes in finally).
- ``require_auth`` — gate + identity. Returns the authenticated
  user's slug (or, eventually, token claims) on success; raises 401
  otherwise. Returning the identity (rather than None) means
  downstream deps don't have to re-parse the auth header — the chain
  is single-pass.
- ``current_user`` — resolves the authenticated identity to a
  ``UserRead`` via the api layer. Depends on ``require_auth``'s
  return value, not on the raw header.

The ``request_id`` middleware lives in ``http/main.py`` directly
(not a Depends — middleware runs unconditionally on every request,
which is what we want for log correlation).

Auth posture (dev-mode):

- ``AUTH_DISABLED=1`` switches on a development bypass where the
  ``X-User-Slug`` header IS the identity. Tests rely on this to seed
  authenticated requests without going through a real login flow.
- Production mode is not yet implemented; ``require_auth`` raises
  501 in that branch. Real auth lands later (see "What we haven't
  built (yet)" in the lesson).
"""

import os
from sqlite3 import Connection

from fastapi import Depends, Header, HTTPException

from wazzup.api import users as users_api
from wazzup.db import connect
from wazzup.models import UserRead

AUTH_DISABLED = os.environ.get("AUTH_DISABLED", "0") == "1"


def get_db():
    """Yield a per-request sqlite3.Connection.

    Caller (the route) owns the transaction *within* the request:
    ``api/`` functions deliberately don't commit (see ``CLAUDE.md``).
    This dep wraps the request boundary — commit on clean exit,
    rollback on exception, close in ``finally``.

    Note: yields a single connection per request, not pooled. SQLite
    on a small teaching app doesn't need pooling, and the simpler
    lifecycle is easier to reason about.
    """
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def require_auth(
    authorization: str | None = Header(None),
    x_user_slug: str | None = Header(None),
) -> str:
    """Gate + identity. Returns the authenticated slug; raises 401 otherwise.

    In dev mode (AUTH_DISABLED=1), the ``X-User-Slug`` header IS the
    identity — no token check, no DB lookup *here*. ``current_user``
    is the dep that goes from slug → ``UserRead``.

    In production mode (not yet implemented), this would decode the
    Bearer token and return the claims dict (or a typed claims object).
    For now it raises 501 to make the gap explicit.

    Returning the identity (instead of ``None``) means downstream
    deps like ``current_user`` consume the return value via
    ``Depends(require_auth)`` rather than re-parsing the header —
    the auth chain is single-pass and the dep contract is honest
    about what auth produces.
    """
    if AUTH_DISABLED:
        if not x_user_slug:
            raise HTTPException(401, "X-User-Slug header required in dev mode")
        return x_user_slug
    raise HTTPException(501, "real auth not yet implemented (set AUTH_DISABLED=1)")


def current_user(
    auth_slug: str = Depends(require_auth),
    db: Connection = Depends(get_db),
) -> UserRead:
    """Resolve the authenticated identity to a ``UserRead``.

    Depends on ``require_auth``'s return value, so ``X-User-Slug`` is
    parsed exactly once. If the slug doesn't match a live user, raise
    401 — *never* auto-create. Silent ghost-user creation is the kind
    of thing that bites you a year later. Tests must explicitly seed
    users before issuing authenticated requests.
    """
    u = users_api.get_by_slug(db, auth_slug)
    if u is None:
        raise HTTPException(401, f"user not found: {auth_slug!r}")
    return u
