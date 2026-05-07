"""Logging configuration + the ``deviation()`` helper — §11.

Two pieces:

1. **``configure_logging()``** sets up the root logger with a single-
   line JSON formatter (``JSONLineFormatter``) and a streaming
   handler. Idempotent — repeated calls (tests, ``uvicorn`` reload,
   ``wazzup.http.main`` import) are no-ops after the first.

2. **``deviation(msg, **kwargs)``** is the canonical way to mark
   unexpected paths in business logic. In **lax mode** (default) it
   logs ``WARNING``; in **strict mode** (``STRICT_MODE=1`` env) it
   raises ``UnexpectedDeviation``. CI runs both legs (#17): lax to
   verify the app doesn't crash on a bad path, strict to surface
   bad paths so they get fixed.

----------------------------------------------------------------------
REQUEST-ID PROPAGATION VIA CONTEXTVARS
----------------------------------------------------------------------

Log lines need to carry the per-request UUID so a multi-request log
stream can be untangled. We use ``contextvars.ContextVar`` (not
thread-local) because:

- It's async-safe — works with FastAPI's threadpool *and* a future
  fully-async route handler.
- It scopes naturally to a single ``await`` chain. The middleware
  in ``http/main.py`` ``set()``s the var on entry and ``reset()``s
  on exit, so leakage between requests is impossible.

Default value is ``"-"`` (literal dash) for log lines emitted
outside any request context (startup, scripts, tests). That's a
readable signal that no request is in flight.

----------------------------------------------------------------------
STRICT_MODE — READ AT MODULE IMPORT, NOT PER-CALL
----------------------------------------------------------------------

``STRICT_MODE`` is evaluated once when this module is imported. To
override in tests, monkeypatch the *module attribute* (and ideally
the env var too, for any subprocess that re-imports). Reading the
env var on every ``deviation()`` call would be cleaner but adds
per-call overhead for a flag that's effectively constant in
practice; the test ergonomics are slightly worse but acceptable.
"""

import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler

# Per-request UUID. Middleware in http/main.py sets and resets it;
# log lines emitted during the request pick it up automatically via
# JSONLineFormatter. Default "-" is for log lines emitted outside any
# request context (startup, scripts, tests).
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


# Read once at import. See module docstring for the testing implication.
STRICT_MODE = os.environ.get("STRICT_MODE", "0") == "1"


class UnexpectedDeviation(RuntimeError):
    """Raised by ``deviation()`` when ``STRICT_MODE=1``.

    Lax-mode callers see a WARNING log; strict-mode callers see this
    exception. Catching it in production would mask a real bug —
    don't.
    """


class JSONLineFormatter(logging.Formatter):
    """One-log-record-per-line JSON formatter. stdlib only.

    Fields:
      - ``ts`` — ISO-8601 timestamp in UTC, with explicit ``+00:00``
        offset (e.g. ``2026-05-07T12:00:00+00:00``). Computed via
        ``datetime.fromtimestamp(record.created, tz=UTC).isoformat()``,
        NOT via ``logging.Formatter.formatTime`` (which would default
        to local time and emit no offset — host-TZ-ambiguous).
      - ``level`` — DEBUG / INFO / WARNING / ERROR / CRITICAL.
      - ``logger`` — the logger's name.
      - ``request_id`` — from the contextvar (or ``"-"``).
      - ``msg`` — the formatted message.
      - ``exc`` — only if there's an exception in flight.
      - **caller-supplied extras** — anything passed via ``extra=`` on
        the logger call (or via ``deviation()``'s ``**kwargs``) appears
        as top-level fields. The stdlib stores those as attributes on
        the ``LogRecord``; we emit any attribute that isn't part of the
        standard ``LogRecord`` shape. Stdlib protection prevents
        callers from shadowing standard attribute names.

    ``json.dumps(default=str)`` falls back to ``str(value)`` for non-
    JSON-serializable extras (datetimes, sets, custom objects), so a
    bad extra never crashes the logger.
    """

    # Attributes that every ``LogRecord`` carries by construction.
    # Anything else on the record came from a caller's ``extra=``.
    # (Includes ``taskName`` — added by Python 3.12 for asyncio
    # context — and ``message``/``asctime`` — set during formatting.)
    _STANDARD_ATTRS = frozenset({
        "name", "msg", "args", "levelname", "levelno",
        "pathname", "filename", "module",
        "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process",
        "message", "asctime", "taskName",
    })

    def format(self, record: logging.LogRecord) -> str:
        # UTC with explicit offset. Bypass ``self.formatTime`` because
        # its default ``converter=time.localtime`` would emit
        # host-TZ-dependent local time with no offset — ambiguous to
        # downstream log readers shipped across hosts.
        ts = datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="seconds")
        payload: dict = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        # Caller-supplied extras: anything on the record beyond the
        # standard set, skipping private attrs (``_*``). If a caller's
        # extra collides with a payload key (``ts``, ``level``, …) the
        # extra wins — that's the structured-logging contract.
        for key, value in record.__dict__.items():
            if key in self._STANDARD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value

        return json.dumps(payload, default=str)


_configured = False


def configure_logging(level: int | str | None = None) -> None:
    """Set up the root logger with a JSON line formatter. Idempotent.

    Called at module import in ``http/main.py``; tests can call
    directly. ``level`` defaults to the ``LOG_LEVEL`` env var, then
    ``INFO``.

    **Sinks:**
    - Always: stderr (uvicorn's terminal output). One JSON record per
      line via ``JSONLineFormatter``.
    - Optional: a rotating file at ``$LOG_FILE_PATH`` if that env var
      is set. Same formatter, so the file is grep/jq-able with the same
      shape as stderr. Rotation is size-based: ``maxBytes=10 MB``,
      ``backupCount=5`` (≤ 50 MB on disk). Parent directory is created
      on demand. Opt-in via env so tests don't accidentally write log
      files; the seeded ``.env.example`` enables it for the demo.
    """
    global _configured
    if _configured:
        return

    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO")

    formatter = JSONLineFormatter()

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)

    root = logging.getLogger()
    # Replace any existing handlers (basicConfig from a previous import,
    # pytest's caplog plugin attachments, …) so we get a single,
    # known-shape stream.
    root.handlers.clear()
    root.addHandler(stderr_handler)

    log_file_path = os.environ.get("LOG_FILE_PATH")
    if log_file_path:
        # Auto-create the parent directory; rotating-file handler doesn't.
        parent = os.path.dirname(os.path.abspath(log_file_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=10 * 1024 * 1024,    # 10 MB per file
            backupCount=5,                # → 5 rolled files = 50 MB ceiling
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    root.setLevel(level)

    _configured = True


def deviation(msg: str, **kwargs) -> None:
    """Mark an unexpected path. Logs WARNING normally; raises in strict mode.

    Usage:

        deviation("delete: no row matched", user_id=user_id)

    The kwargs are passed as ``extra`` to the logger so structured
    consumers can read them as fields. In strict mode, kwargs are
    formatted into the exception message for visibility.
    """
    if STRICT_MODE:
        raise UnexpectedDeviation(f"{msg} | {kwargs}" if kwargs else msg)
    logging.getLogger("wazzup.deviation").warning(msg, extra=kwargs)
