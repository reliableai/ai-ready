"""Create a single user via the internal Python API.

Section 10 of the lesson — the smallest possible "is the install
working?" smoke test. Calls ``users.create`` directly (no HTTP),
prints the resulting ``UserRead`` as JSON.

For the full demo state (humans + agents + topics + conversation +
messages), use ``examples/seed.py``. For the cascade demo, use
``examples/remove_user.py``.

Usage:
    python -m examples.add_user "Alice Smith"
    python -m examples.add_user "Donald Trump" --type agent --persona "Tremendous confidence."
    python -m examples.add_user "Alice" --slug alice-prime
"""

import argparse

from wazzup.api import users
from wazzup.db import connect, init_schema
from wazzup.models import UserCreate


def add_user(
    name: str,
    type_: str = "human",
    persona: str | None = None,
    slug: str | None = None,
) -> None:
    db = connect()
    try:
        init_schema(db)
        u = users.create(db, UserCreate(
            name=name,
            type=type_,
            persona=persona,
            slug=slug,
        ))
        db.commit()
        # Pydantic v2 model_dump_json gives a clean JSON line.
        print(u.model_dump_json(indent=2))
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a wazzup user.")
    parser.add_argument("name", help="display name (e.g. 'Alice Smith')")
    parser.add_argument(
        "--type", dest="type_", choices=["human", "agent"], default="human",
        help="user type (default: human)",
    )
    parser.add_argument(
        "--persona", default=None,
        help="markdown persona (only meaningful for agents)",
    )
    parser.add_argument(
        "--slug", default=None,
        help="explicit slug override; otherwise derived from name",
    )
    args = parser.parse_args()
    add_user(
        name=args.name,
        type_=args.type_,
        persona=args.persona,
        slug=args.slug,
    )


if __name__ == "__main__":
    main()
