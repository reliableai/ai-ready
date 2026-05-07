"""Public router — login goes here.

Section 8 of the lesson: this is the *one* router that
deliberately has no ``dependencies=[Depends(require_auth)]``
argument. The absence is the opt-out, and the small file size
makes it easy to eyeball every public route in one place.

For the dev mode of wazzup (AUTH_DISABLED=1), there's nothing
to do — the X-User-Slug header is the "login". This file
becomes load-bearing once real auth is implemented (see
"What we haven't built (yet)").
"""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])   # no dependencies= → public

# TODO once real auth lands:
#   POST /auth/login (username + password → token)
#   POST /auth/refresh
