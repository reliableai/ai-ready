"""FastAPI app assembly — section 8 of the lesson.

This module is the *one* place where middleware order, exception
handlers, and router mounts are visible together. Keeping it centralized
makes the app's HTTP surface readable in a single screen.

Order matters:
1. Lifespan — startup/shutdown hooks (e.g., optional schema init).
2. CORS middleware — must wrap everything else so preflights work.
3. Request-id middleware — sets the per-request UUID *before* any
   route runs, so route handlers can read ``request.state.request_id``.
4. Exception handlers — translate api-layer exceptions to HTTP status.
5. Routes (``/healthz``) and routers.

Why a lifespan context manager and not ``@app.on_event("startup")``?
``on_event`` is deprecated in modern FastAPI and emits a
``DeprecationWarning``. ``pyproject.toml`` has ``filterwarnings = ["error"]``
under ``[tool.pytest.ini_options]``, which would turn that warning into
a test failure. Lifespan is the supported replacement.
"""

import os
import uuid
from contextlib import asynccontextmanager
from sqlite3 import IntegrityError

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from wazzup.api import NotFound
from wazzup.db import connect, init_schema
from wazzup.http.auth import router as auth_router
from wazzup.http.conversations import router as conversations_router
from wazzup.http.dms import router as dms_router
from wazzup.http.messages import router as messages_router
from wazzup.http.topics import router as topics_router
from wazzup.http.users import router as users_router
from wazzup.logging_setup import configure_logging, request_id_var

configure_logging()


# 1. Lifespan — modern replacement for the deprecated @app.on_event hooks.
# Optional schema init for the teaching quickstart: production deployments
# should NOT auto-mutate the DB on every boot, so this is opt-in.
@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("WAZZUP_INIT_SCHEMA") == "1":
        db = connect()
        try:
            init_schema(db)
            db.commit()
        finally:
            db.close()
    yield


app = FastAPI(title="wazzup", version="0.1.0", lifespan=lifespan)


# 2. CORS for the UI dev origin (section 13).
# Hardcoded for the teaching app; production-readiness (env-driven origins)
# is deferred to a later TODO.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 3. Request-id middleware — attaches a per-request UUID to request.state,
# sets the logging contextvar (so log lines automatically carry the id —
# see logging_setup.JSONLineFormatter), and echoes the id back in the
# response header. Honors an inbound X-Request-Id (so an upstream proxy /
# client can supply its own); else generates a fresh UUID.
#
# The contextvar token is reset in ``finally`` so request scoping is
# rigorous even if the route raises — leaks across requests would be a
# correctness bug, not a stylistic one.
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = rid
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["x-request-id"] = rid
    return response


# 4. Exception handlers — translate api-layer exceptions to HTTP status.
#
# NOTE: ``IntegrityError`` is sqlite3-specific. If we ever swap drivers
# (psycopg, asyncpg, …), this handler must widen to the new driver's
# constraint exception class — or move behind a thin abstraction.
@app.exception_handler(NotFound)
async def handle_not_found(request: Request, exc: NotFound) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=404)


@app.exception_handler(IntegrityError)
async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse({"detail": f"constraint violation: {exc}"}, status_code=409)


# 5. Routes
@app.get("/healthz")
def healthz() -> dict:
    """Liveness probe. Required by every load balancer."""
    return {"ok": True}


app.include_router(users_router)
app.include_router(conversations_router)
app.include_router(topics_router)
app.include_router(dms_router)
app.include_router(messages_router)
app.include_router(auth_router)
# rels router lands in #12
