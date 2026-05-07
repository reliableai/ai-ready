"""User CRUD smoke tests — tasks #8 (api-layer) and #10 (HTTP-layer).

Two suites in one file:

- **api-layer** (top): narrow per-function tests against
  ``wazzup.api.users`` using the ``db`` fixture. These pin
  business-logic invariants (slug derivation, soft-delete reuse,
  NOT NULL defenses, …) without going through HTTP.

- **HTTP-layer** (bottom, "----- HTTP via TestClient -----"):
  smoke tests against the FastAPI app using the ``client`` fixture.
  These pin the route surface — status codes, error envelope shape,
  auth gate, request-id middleware. They're intentionally narrow:
  the per-endpoint behavior spec lives in ``tests/tests.md`` and
  the per-entity routes are added in #11.

Design decisions pinned here (cross-reference TODO.md):
- silent-suffix-on-collision behavior is locked in by
  test_create_explicit_override_collision — see TODO #19 for the
  future split between explicit-override (probably 409) and
  auto-derived collisions (suffix)
- timestamp comparison uses ``>=`` plus a change assertion (not ``>``)
- the cascade-through-rels gap is tracked by an xfail test
- `UserUpdate(details=None)` is rejected at the model boundary
- `UserUpdate(name=None)` / `(type=None)` rejected at the api layer
  (nullability rule pattern 2; see ``models.py`` module docstring)
- `test_unauthenticated_request_returns_401` sends a *valid* body
  on purpose so 401 is the only thing being tested (FastAPI's body
  validation could otherwise produce 422 first)
"""

import time

import pytest
from pydantic import ValidationError

from wazzup.api import NotFound, users
from wazzup.models import UserCreate, UserDetails, UserUpdate

# ----- create -----

def test_create_with_explicit_slug(db):
    """An explicit slug is honored when there's no collision."""
    u = users.create(db, UserCreate(name="Alice", slug="alice-prime", type="human"))
    assert u.slug == "alice-prime"
    assert u.name == "Alice"
    assert u.type == "human"
    assert u.id > 0


def test_create_derives_slug_from_name(db):
    """No slug provided → server derives via slugify(name)."""
    u = users.create(db, UserCreate(name="Alice Smith", type="human"))
    assert u.slug == "alice-smith"


def test_create_collision_increments_suffix(db):
    """Second user with same auto-derived slug gets the -2 suffix."""
    a = users.create(db, UserCreate(name="Alice", type="human"))
    b = users.create(db, UserCreate(name="Alice", type="agent"))
    assert a.slug == "alice"
    assert b.slug == "alice-2"
    assert a.id != b.id


def test_create_explicit_override_collision(db):
    """Explicit override + collision → silent suffix (locked-in behavior).

    This is the design-decision-2 lock-in: ``make_slug`` always returns
    a unique slug, even when the caller passed an explicit ``slug=``.
    A future refinement (TODO #19) will distinguish explicit-override
    collision (probably 409) from auto-derived collision (suffix).
    Until then, this test pins the current behavior.
    """
    users.create(db, UserCreate(name="Alice", slug="taken", type="human"))
    other = users.create(db, UserCreate(name="Bob", slug="taken", type="human"))
    assert other.slug == "taken-2"


def test_create_with_persona_and_details(db):
    """Agent user; persona and details JSON round-trip cleanly."""
    u = users.create(db, UserCreate(
        name="Trump",
        type="agent",
        persona="You speak with tremendous confidence.",
        details=UserDetails(bio="45th US president (fictional persona)", timezone="America/New_York"),
    ))
    assert u.type == "agent"
    assert u.persona == "You speak with tremendous confidence."
    assert u.details.bio == "45th US president (fictional persona)"
    assert u.details.timezone == "America/New_York"


# ----- get / get_by_slug -----

def test_get_and_get_by_slug(db):
    """Both lookups return the same UserRead; misses return None."""
    created = users.create(db, UserCreate(name="Alice", type="human"))
    by_id = users.get(db, created.id)
    by_slug = users.get_by_slug(db, "alice")
    assert by_id is not None and by_slug is not None
    assert by_id.id == by_slug.id == created.id

    assert users.get(db, 99999) is None
    assert users.get_by_slug(db, "nope") is None


# ----- update -----

def test_update_partial_fields(db):
    """Patching only `persona` leaves `name` unchanged; updated_at advances."""
    u = users.create(db, UserCreate(name="Alice", type="agent"))
    before = u.updated_at

    # On fast hardware, the next ISO timestamp can equal the
    # previous one to the microsecond; sleep a beat to disambiguate.
    time.sleep(0.001)

    patched = users.update(db, u.id, UserUpdate(persona="cheerful"))

    # name unchanged
    assert patched.name == "Alice"
    # persona updated
    assert patched.persona == "cheerful"
    # updated_at advanced (>=, not >; plus the field actually changed)
    assert patched.updated_at >= before
    assert patched.persona != u.persona


def test_update_name_does_not_change_slug(db):
    """Patching `name` from 'Alice' to 'Alicia' leaves slug as 'alice'.

    Design decision: slugs are stable once assigned. UserUpdate has
    no `slug` field; renaming the user produces a stale-looking
    handle, which is the intended behavior.
    """
    u = users.create(db, UserCreate(name="Alice", type="human"))
    patched = users.update(db, u.id, UserUpdate(name="Alicia"))
    assert patched.name == "Alicia"
    assert patched.slug == "alice"


def test_update_missing_raises_notfound(db):
    with pytest.raises(NotFound, match="999"):
        users.update(db, 999, UserUpdate(persona="ghost"))


# ----- delete -----

def test_delete_soft_hides_from_reads(db):
    """After soft-delete, get/get_by_slug return None; row still in DB."""
    u = users.create(db, UserCreate(name="Alice", type="human"))
    users.delete(db, u.id)

    assert users.get(db, u.id) is None
    assert users.get_by_slug(db, "alice") is None

    # Row still physically present, just with deleted_at set.
    row = db.execute("SELECT id, deleted_at FROM user WHERE id = ?", (u.id,)).fetchone()
    assert row is not None
    assert row["deleted_at"] is not None


def test_delete_hard_removes_row(db):
    """Hard delete physically removes the row."""
    u = users.create(db, UserCreate(name="Alice", type="human"))
    users.delete(db, u.id, hard=True)

    row = db.execute("SELECT id FROM user WHERE id = ?", (u.id,)).fetchone()
    assert row is None


def test_delete_missing_raises_notfound(db):
    with pytest.raises(NotFound, match="999"):
        users.delete(db, 999)


# ----- query -----

def test_query_filters_by_type_and_excludes_soft_deleted(db):
    """`type` filter works; soft-deleted users don't appear."""
    a = users.create(db, UserCreate(name="Alice", type="human"))
    users.create(db, UserCreate(name="Bob", type="human"))
    users.create(db, UserCreate(name="Trump", type="agent"))
    users.create(db, UserCreate(name="Curie", type="agent"))
    users.delete(db, a.id)   # soft-delete Alice

    humans = users.query(db, type="human")
    agents = users.query(db, type="agent")
    everyone = users.query(db)

    assert {u.name for u in humans} == {"Bob"}            # Alice excluded
    assert {u.name for u in agents} == {"Trump", "Curie"}
    assert {u.name for u in everyone} == {"Bob", "Trump", "Curie"}


# ----- slug-after-soft-delete -----

def test_slug_reusable_after_soft_delete(db):
    """Soft-delete alice; create a new Alice → gets slug 'alice', not 'alice-2'.

    The partial unique index on slug WHERE deleted_at IS NULL
    permits reuse; make_slug filters live rows only. This is
    teaching-grade "soft delete really frees the handle" behavior.
    """
    a = users.create(db, UserCreate(name="Alice", type="human"))
    assert a.slug == "alice"
    users.delete(db, a.id)

    b = users.create(db, UserCreate(name="Alice", type="human"))
    assert b.slug == "alice"
    assert b.id != a.id


# ----- model-boundary defenses -----

def test_update_details_none_rejected_at_model_boundary():
    """UserUpdate(details=None) raises ValidationError at construction.

    Regression for the silent-corruption bug: previously, details=None
    round-tripped as JSON "null" → Python None, which UserRead refused
    on re-read, after the row had already been mutated. Making
    UserUpdate.details non-Optional pushes the rejection to model
    construction, before any DB write can happen.
    """
    with pytest.raises(ValidationError):
        UserUpdate(details=None)


def test_update_omitting_details_leaves_existing_unchanged(db):
    """UserUpdate() (no details field) doesn't touch the existing details.

    Confirms exclude_unset=True is doing its job: details has a default
    factory, but if it's not explicitly passed, it's not in the patch
    dict and therefore not in the SQL SET clause.
    """
    u = users.create(db, UserCreate(
        name="Alice",
        type="human",
        details=UserDetails(bio="original", timezone="America/New_York"),
    ))
    users.update(db, u.id, UserUpdate(persona="cheerful"))   # no details

    fresh = users.get(db, u.id)
    assert fresh.details.bio == "original"
    assert fresh.details.timezone == "America/New_York"
    assert fresh.persona == "cheerful"


def test_update_name_none_rejected_at_api_layer(db):
    """UserUpdate(name=None) triggers the api-layer NOT NULL defense.

    Pydantic accepts `name=None` at construction (it's typed
    `str | None = None`), so the rejection happens in `users.update`
    before SQL runs. The schema's NOT NULL is the safety net but the
    api-layer message is friendlier. See nullability rule in models.py.
    """
    u = users.create(db, UserCreate(name="Alice", type="human"))
    with pytest.raises(ValueError, match="cannot set NOT NULL field"):
        users.update(db, u.id, UserUpdate(name=None))


def test_update_type_none_rejected_at_api_layer(db):
    """Same as the name test, for the `type` field."""
    u = users.create(db, UserCreate(name="Alice", type="human"))
    with pytest.raises(ValueError, match="cannot set NOT NULL field"):
        users.update(db, u.id, UserUpdate(type=None))


def test_update_persona_none_clears_the_column(db):
    """persona is genuinely nullable in the schema — None means 'clear it'.

    Confirms rule 3 of the nullability rule: nullable scalars accept
    None as the 'clear this column' signal.
    """
    u = users.create(db, UserCreate(name="Alice", type="human", persona="cheerful"))
    assert u.persona == "cheerful"
    users.update(db, u.id, UserUpdate(persona=None))
    fresh = users.get(db, u.id)
    assert fresh.persona is None


# ----- cascade through rels (passes after #13) -----


def test_delete_user_cascades_to_rels(db):
    """When a user is soft-deleted, their rels rows are soft-deleted too.

    This test was xfail-marked through #8–#12 (cascade was deferred to
    #13). After #13 — ``api/deletion.cascade_delete`` and the funnel
    pattern in each entity's ``delete()`` — it passes naturally. The
    fuller cascade behaviors per entity live in ``test_deletion.py``;
    this one stays here because it's the original-sin test that
    motivated #13's existence.
    """
    NOW = "2026-05-06T14:00:00Z"
    u = users.create(db, UserCreate(name="Alice", type="human"))

    # Insert a rel pointing at Alice via raw SQL. We could use
    # rels.add() now (#12 landed), but rels.add validates that the tgt
    # entity exists (topic id=1 doesn't here), so we'd have to seed a
    # topic too. Raw SQL keeps the test self-contained and pins the
    # cascade behavior independently of rels.add's validation.
    db.execute(
        "INSERT INTO rels (src_id, src_type, tgt_id, tgt_type, rel_type, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (u.id, "user", 1, "topic", "member_of", NOW),
    )

    users.delete(db, u.id)

    # After cascade, the rel is soft-deleted alongside the user.
    live_rels = db.execute(
        "SELECT COUNT(*) FROM rels "
        "WHERE src_id = ? AND src_type = 'user' AND deleted_at IS NULL",
        (u.id,),
    ).fetchone()[0]
    assert live_rels == 0


# ============================================================
# ----- HTTP via TestClient -----
# ============================================================
#
# These tests use the ``client`` fixture (TestClient with get_db
# overridden to point at the per-test in-memory DB; AUTH_DISABLED
# forced on). They pin the *route surface*: status codes, error
# envelope shape, auth gate, request-id middleware.
#
# Auth posture in dev mode: every authenticated request must carry
# ``X-User-Slug: <slug>``. Tests seed the user via the api layer
# (using the same ``db`` fixture the client is wired to) before
# issuing the authenticated request — never auto-create.

AUTH_HEADER = {"X-User-Slug": "alice"}


def _seed_alice(db) -> None:
    """Seed an alice human user via the api layer.

    Used by the HTTP tests as the authenticated caller. Lives in this
    file (not conftest) because conftest.py's ``client`` fixture is
    deliberately auth-agnostic — different tests want different
    auth setups (no auth, missing user, …).
    """
    users.create(db, UserCreate(name="Alice", type="human"))


def test_post_users_creates_and_returns_201(client, db):
    """POST /users with a valid body → 201 + UserRead JSON.

    Verifies both the response (status, body shape) and the
    side-effect (row exists in the DB).
    """
    _seed_alice(db)
    resp = client.post(
        "/users",
        headers=AUTH_HEADER,
        json={"name": "Bob", "type": "human"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Bob"
    assert body["slug"] == "bob"
    assert body["type"] == "human"
    assert body["id"] > 0

    # And the row really landed.
    fresh = users.get_by_slug(db, "bob")
    assert fresh is not None
    assert fresh.id == body["id"]


def test_post_users_invalid_body_returns_422(client, db):
    """POST /users missing `name` → 422 (Pydantic body validation).

    FastAPI handles this before our route body runs; we just confirm
    the status code so a future change to the request shape is loud.
    """
    _seed_alice(db)
    resp = client.post(
        "/users",
        headers=AUTH_HEADER,
        json={"type": "human"},   # name missing
    )
    assert resp.status_code == 422


def test_get_users_slug_returns_user(client, db):
    """GET /users/{slug} for a live user → 200 + UserRead."""
    _seed_alice(db)
    resp = client.get("/users/alice", headers=AUTH_HEADER)
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "alice"
    assert body["name"] == "Alice"


def test_get_users_slug_404_when_missing(client, db):
    """GET /users/{slug} for an unknown slug → 404 with FastAPI's
    {'detail': ...} envelope (NotFound exception handler in main.py)."""
    _seed_alice(db)
    resp = client.get("/users/nope", headers=AUTH_HEADER)
    assert resp.status_code == 404
    body = resp.json()
    assert "detail" in body
    assert "nope" in body["detail"]


def test_unauthenticated_request_returns_401(client, db):
    """POST /users WITHOUT X-User-Slug header → 401, NOT 422.

    The body is valid on purpose: FastAPI's body validation could fire
    before or after the router-level ``Depends(require_auth)`` depending
    on version, and a malformed body would muddy the test by producing
    422 for the wrong reason. A valid body isolates the auth failure as
    the only thing being tested.
    """
    _seed_alice(db)
    resp = client.post(
        "/users",
        json={"name": "Bob", "type": "human"},   # valid body, no auth header
    )
    assert resp.status_code == 401


def test_get_users_returns_list_with_type_filter(client, db):
    """GET /users → live users; ?type= filters by user type.

    Also confirms soft-deleted users are excluded — a regression
    here would surface real users in admin views after deletion.
    """
    _seed_alice(db)
    bob = users.create(db, UserCreate(name="Bob", type="human"))
    users.create(db, UserCreate(name="Curie", type="agent"))
    users.delete(db, bob.id)   # soft-deleted; should NOT appear in list

    # No filter: all live users (alice + curie, not bob)
    resp = client.get("/users", headers=AUTH_HEADER)
    assert resp.status_code == 200
    slugs = {u["slug"] for u in resp.json()}
    assert slugs == {"alice", "curie"}

    # type=human
    resp = client.get("/users?type=human", headers=AUTH_HEADER)
    assert {u["slug"] for u in resp.json()} == {"alice"}

    # type=agent
    resp = client.get("/users?type=agent", headers=AUTH_HEADER)
    assert {u["slug"] for u in resp.json()} == {"curie"}


def test_get_users_pagination(client, db):
    """?limit= and ?offset= work as advertised."""
    _seed_alice(db)
    for name in ("Bob", "Charlie", "Dave"):
        users.create(db, UserCreate(name=name, type="human"))

    # First two
    resp = client.get("/users?limit=2&offset=0", headers=AUTH_HEADER)
    assert len(resp.json()) == 2
    # Skip first two, take next two
    resp = client.get("/users?limit=2&offset=2", headers=AUTH_HEADER)
    assert len(resp.json()) == 2


def test_get_users_rejects_negative_pagination(client, db):
    """``Query(ge=...)`` validation applies on /users too.

    Same regression pattern as test_messages: SQLite would silently
    treat ``LIMIT -1`` as "no limit". The HTTP boundary catches it.
    Conversations and topics share the same ``Query`` shape; pinning
    /users + /messages is enough to detect a future drift on either
    half (entities vs messages-with-required-conversation_id).
    """
    _seed_alice(db)

    assert client.get("/users?limit=-1", headers=AUTH_HEADER).status_code == 422
    assert client.get("/users?offset=-1", headers=AUTH_HEADER).status_code == 422
    assert client.get("/users?limit=0", headers=AUTH_HEADER).status_code == 422
    assert client.get("/users?limit=99999", headers=AUTH_HEADER).status_code == 422


def test_request_id_in_response_header(client, db):
    """Every response carries an X-Request-Id header (middleware proof).

    Honors an inbound X-Request-Id, else generates a fresh UUID. We
    test the generation branch here (no inbound header) — the echo
    branch is incidental and not worth its own test for #10.
    """
    resp = client.get("/healthz")   # public route; no auth needed
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
    assert len(resp.headers["x-request-id"]) > 0
