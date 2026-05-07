"""Slug derivation + uniqueness — section 6 of the lesson.

``slugify(name)`` produces the URL-friendly form. ``make_slug`` picks
a unique slug per table, with a numeric suffix on collision. The
race-safety net is the schema's ``UNIQUE`` constraint on ``slug``
per table (see ``docs/MODEL.md``); ``create()`` should catch the
``IntegrityError``, increment, retry.
"""

import re
from sqlite3 import Connection


def slugify(name: str) -> str:
    """'Alice Smith' → 'alice-smith'. Lowercase, hyphens, alphanumerics only."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "item"


def make_slug(
    db: Connection,
    table: str,
    name: str,
    override: str | None = None,
) -> str:
    """Pick a unique slug for the given table.

    Override wins if provided. On collision, append -2, -3, ... until unique.
    Filters live rows only (``deleted_at IS NULL``); soft-deleted slugs are
    considered free. Adjust if your product wants different semantics.
    """
    base = slugify(override) if override else slugify(name)
    candidate, n = base, 1
    while db.execute(
        f"SELECT 1 FROM {table} WHERE slug = ? AND deleted_at IS NULL",
        (candidate,),
    ).fetchone():
        n += 1
        candidate = f"{base}-{n}"
    return candidate
