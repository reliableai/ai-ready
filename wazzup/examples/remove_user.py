"""Soft-delete (or hard-delete) a user; print the cascade report.

Section 10 of the lesson. Demonstrates ``cascade_delete`` from
``api/deletion.py``: soft-deleting a user sweeps every rel they
appear in (sent_by, member_of, participates_in, …) but leaves the
messages they sent alive (cascade only goes user → user's rels,
not user → user's messages).

The script calls ``cascade_delete`` directly (rather than
``users.delete``) so we can read and print the ``CascadeReport``.
The public ``users.delete`` returns ``None`` and just raises
``NotFound`` on a missing/already-deleted user.

Usage:
    python -m examples.remove_user alice                # soft-delete
    python -m examples.remove_user alice --hard         # physical removal
"""

import argparse
import json
import sys

from wazzup.api import users
from wazzup.api.deletion import cascade_delete
from wazzup.db import connect, init_schema


def remove_user(slug: str, hard: bool = False) -> None:
    db = connect()
    try:
        init_schema(db)

        u = users.get_by_slug(db, slug)
        if u is None:
            # Use sys.exit so the shell sees a non-zero status.
            print(f"no live user with slug={slug!r}", file=sys.stderr)
            sys.exit(1)

        # Pre-cascade snapshot — useful to compare against the report.
        from wazzup.api import rels
        rels_as_src = rels.list(db, src_type="user", src_id=u.id)
        rels_as_tgt = rels.list(db, tgt_type="user", tgt_id=u.id)
        print(
            f"user {slug!r} (id={u.id}) has "
            f"{len(rels_as_src)} src rels + {len(rels_as_tgt)} tgt rels"
        )

        report = cascade_delete(db, table="user", id=u.id, hard=hard)
        db.commit()

        print(json.dumps({
            "operation": "hard delete" if hard else "soft delete",
            "slug": slug,
            "id": u.id,
            "report": {
                "primary": report.primary,
                "rels": report.rels,
                "messages": report.messages,
            },
        }, indent=2))
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove a wazzup user.")
    parser.add_argument("slug", help="user's slug (e.g. 'alice')")
    parser.add_argument(
        "--hard", action="store_true",
        help="physically remove the row (default is soft-delete)",
    )
    args = parser.parse_args()
    remove_user(slug=args.slug, hard=args.hard)


if __name__ == "__main__":
    main()
