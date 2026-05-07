"""Rels HTTP routes — protected router.

Most apps don't expose rels directly via HTTP (they're plumbing
for entity routes like /topics/{slug}/members). This router is
here for completeness; you may not need to mount it.
"""

from fastapi import APIRouter, Depends

from wazzup.http.dependencies import require_auth

router = APIRouter(
    prefix="/rels",
    tags=["rels"],
    dependencies=[Depends(require_auth)],
)

# TODO: only expose if you actually need a generic /rels surface.
