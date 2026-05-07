"""User HTTP routes — protected router (auth required).

Section 8 of the lesson. Two patterns this file pins:

1. **Auth posture is declared once, at the top.** The router is built
   with ``dependencies=[Depends(require_auth)]``; every route below
   inherits the gate. New routes default to *protected* — adding a
   public route is a deliberate step (move it to ``http/auth.py``,
   which is the only router declared without ``require_auth``).

2. **Routes are thin translators.** Pull the validated body, call
   into ``wazzup.api.users``, return the result. No business logic
   in this file. The api layer is where the rules live; the HTTP
   layer is where they're exposed.

Routes implemented in #10:
    POST   /users           → create  (201, returns UserRead)
    GET    /users/{slug}    → get_by_slug (404 on miss)

The remaining verbs (PATCH, DELETE, GET list) land in #11 alongside
the other entities, once the pattern is mechanical.
"""

from sqlite3 import Connection

from fastapi import APIRouter, Depends, Query

from wazzup.api import NotFound
from wazzup.api import users as users_api
from wazzup.http.dependencies import get_db, require_auth
from wazzup.models import UserCreate, UserRead

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_auth)],   # every route below is gated
)


@router.post("", status_code=201, response_model=UserRead)
def create_user(body: UserCreate, db: Connection = Depends(get_db)) -> UserRead:
    """Create a user. Returns 201 + the created UserRead.

    Errors (handled by main.py's exception handlers):
      - 422 — invalid body (Pydantic; e.g., missing name, type not in {human, agent})
      - 401 — missing X-User-Slug in dev mode (router-level require_auth)
      - 409 — slug collision after retry exhaustion (rare race; api layer)
    """
    return users_api.create(db, body)


@router.get("", response_model=list[UserRead])
def list_users(
    type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Connection = Depends(get_db),
) -> list[UserRead]:
    """List live users. Optional ``?type=human`` or ``?type=agent`` filter.

    Pagination via ``?limit=`` (1..200, default 50) and ``?offset=``
    (≥0, default 0). The bounds are enforced at the HTTP boundary —
    SQLite would silently treat ``LIMIT -1`` as "no limit", which
    breaks the page-cap contract callers expect.

    Soft-deleted users are excluded; deliberately no ``include_deleted``
    flag (a separate audit endpoint would be the right place).
    """
    return users_api.query(db, type=type, limit=limit, offset=offset)


@router.get("/{slug}", response_model=UserRead)
def get_user_by_slug(slug: str, db: Connection = Depends(get_db)) -> UserRead:
    """Look up a live user by slug. 404 if absent or soft-deleted.

    The slug path param is unconstrained at the route level (any path
    segment); a typo just falls through to the not-found branch.
    Adding a regex match here would short-circuit obviously-wrong
    inputs but adds defensive code that doesn't add real safety.
    """
    user = users_api.get_by_slug(db, slug)
    if user is None:
        raise NotFound(f"user slug={slug!r} not found")
    return user
