"""DM HTTP tests.

Two surfaces, both via the FastAPI ``client`` fixture:

- ``POST /dms/{peer_slug}`` opens or creates the 1:1 DM. Idempotent
  (same peer twice → same conversation), 404 on unknown peer, 400 on
  self-DM.
- The api-layer ``conversations.get_or_create_dm`` is exercised in
  ``test_conversations.py``; here we just verify the http surface
  routes correctly through it.
"""

from wazzup.api import users
from wazzup.models import UserCreate

AUTH_HEADER = {"X-User-Slug": "alice"}


def _seed_alice_and_curie(db):
    """Seed users with explicit slugs so the auth header `X-User-Slug: alice` lines up."""
    users.create(db, UserCreate(name="Alice Smith", slug="alice", type="human"))
    users.create(db, UserCreate(
        name="Marie Curie", slug="curie", type="agent", persona="Quiet rigor.",
    ))


def test_post_dms_returns_conversation(client, db):
    """POST /dms/{peer_slug} → 200 + ConversationRead."""
    _seed_alice_and_curie(db)
    resp = client.post("/dms/curie", headers=AUTH_HEADER)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] > 0
    # Slug uses alphabetical user.slug ordering: alice < curie.
    assert body["slug"] == "dm-alice-curie"


def test_post_dms_idempotent(client, db):
    """Calling twice with the same peer returns the same conversation id."""
    _seed_alice_and_curie(db)
    a = client.post("/dms/curie", headers=AUTH_HEADER).json()
    b = client.post("/dms/curie", headers=AUTH_HEADER).json()
    assert a["id"] == b["id"]


def test_post_dms_404_on_unknown_peer(client, db):
    """Unknown peer slug → 404 via the NotFound handler."""
    _seed_alice_and_curie(db)
    resp = client.post("/dms/no-one", headers=AUTH_HEADER)
    assert resp.status_code == 404
    assert "no-one" in resp.json()["detail"]


def test_post_dms_400_on_self_dm(client, db):
    """peer_slug == authenticated user's slug → 400 'cannot DM yourself'."""
    _seed_alice_and_curie(db)
    resp = client.post("/dms/alice", headers=AUTH_HEADER)
    assert resp.status_code == 400
    assert "yourself" in resp.json()["detail"]
