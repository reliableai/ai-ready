"""Logging tests — task #14.

Five smoke tests that pin the §11 logging story:

- ``deviation()`` logs WARNING in lax mode, raises in strict mode
- log lines are JSON and carry the request_id from the contextvar
- the contextvar default ("-") shows up outside any request context
- ``configure_logging()`` is idempotent

The strict-mode test patches the *module attribute* of
``logging_setup.STRICT_MODE`` directly, since the constant is read
once at module import (see the module docstring). Patching only the
env var would have no effect on the already-imported module.
"""

import json
import logging

import pytest

from wazzup import logging_setup
from wazzup.logging_setup import (
    JSONLineFormatter,
    UnexpectedDeviation,
    configure_logging,
    deviation,
    request_id_var,
)

# ----- deviation() in both modes -----


def test_deviation_logs_warning_in_lax_mode(monkeypatch, caplog):
    """Lax mode (default): deviation logs WARNING and continues."""
    monkeypatch.setattr(logging_setup, "STRICT_MODE", False)

    with caplog.at_level(logging.WARNING, logger="wazzup.deviation"):
        deviation("a thing happened", user_id=42)

    # One WARNING record exists; no exception was raised.
    assert any(
        r.levelname == "WARNING" and "a thing happened" in r.message
        for r in caplog.records
    )


def test_deviation_raises_in_strict_mode(monkeypatch):
    """Strict mode: deviation raises UnexpectedDeviation. CI gates this."""
    monkeypatch.setattr(logging_setup, "STRICT_MODE", True)

    with pytest.raises(UnexpectedDeviation, match="oops"):
        deviation("oops", user_id=42)


# ----- request_id propagation through the formatter -----


def test_log_line_includes_request_id_from_contextvar():
    """The formatter reads ``request_id_var`` at format time."""
    formatter = JSONLineFormatter()
    record = logging.LogRecord(
        name="wazzup.test", level=logging.INFO, pathname="x.py", lineno=1,
        msg="hello", args=(), exc_info=None,
    )

    token = request_id_var.set("abc-123")
    try:
        line = formatter.format(record)
    finally:
        request_id_var.reset(token)

    payload = json.loads(line)
    assert payload["request_id"] == "abc-123"
    assert payload["msg"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "wazzup.test"


def test_log_line_default_request_id_dash_outside_context():
    """No request in flight → request_id is the default dash."""
    formatter = JSONLineFormatter()
    record = logging.LogRecord(
        name="wazzup.test", level=logging.INFO, pathname="x.py", lineno=1,
        msg="hello from a script", args=(), exc_info=None,
    )

    payload = json.loads(formatter.format(record))
    assert payload["request_id"] == "-"


def test_log_line_includes_caller_supplied_extras():
    """Caller-supplied ``extra=`` fields appear as top-level JSON keys.

    Regression for the structured-logging contract: ``deviation()``
    accepts ``**kwargs`` and passes them as ``extra=`` to the logger;
    those become attributes on the ``LogRecord``. The formatter must
    emit any non-standard attribute as a top-level field so log
    consumers can read structured context.

    Without this, ``deviation("retry exhausted", attempts=3)`` would
    log "retry exhausted" but lose the ``attempts=3`` context — making
    structured logs no better than plain strings.
    """
    formatter = JSONLineFormatter()
    record = logging.LogRecord(
        name="wazzup.test", level=logging.INFO, pathname="x.py", lineno=1,
        msg="hello", args=(), exc_info=None,
    )
    # Simulate ``logger.X(msg, extra={"user_id": 42, "topic": "eng"})``
    # — the stdlib stores these as attributes on the record.
    record.user_id = 42
    record.topic = "eng"

    payload = json.loads(formatter.format(record))
    assert payload["user_id"] == 42
    assert payload["topic"] == "eng"
    # Standard fields are still there alongside the extras.
    assert payload["msg"] == "hello"
    assert payload["level"] == "INFO"


def test_log_line_ts_is_utc_with_explicit_offset():
    """``ts`` is UTC and carries an explicit ``+00:00`` offset.

    Regression for the host-TZ ambiguity bug: previously, the
    formatter used ``self.formatTime`` whose default converter is
    ``time.localtime``, producing host-dependent local time with no
    offset. Logs aggregated across hosts would have been ambiguous
    (was that 14:00 NYC or 14:00 Berlin?).

    Pinning a known UTC moment and asserting the exact emitted string
    catches both halves of the bug — the wrong TZ AND the missing
    offset.
    """
    from datetime import UTC, datetime

    formatter = JSONLineFormatter()
    record = logging.LogRecord(
        name="wazzup.test", level=logging.INFO, pathname="x.py", lineno=1,
        msg="hi", args=(), exc_info=None,
    )
    # Override created at a known UTC moment so the assertion is
    # deterministic regardless of the host's timezone.
    record.created = datetime(2026, 5, 7, 12, 0, 0, tzinfo=UTC).timestamp()

    payload = json.loads(formatter.format(record))
    assert payload["ts"] == "2026-05-07T12:00:00+00:00"


def test_log_line_serializes_non_jsonable_extras_via_str_fallback():
    """Non-JSON-serializable extras (datetimes, sets, custom objects)
    fall back to ``str(value)`` rather than crashing the logger.

    A formatter that crashes mid-record is much worse than one that
    serializes a value imperfectly.
    """
    from datetime import datetime

    formatter = JSONLineFormatter()
    record = logging.LogRecord(
        name="wazzup.test", level=logging.INFO, pathname="x.py", lineno=1,
        msg="event", args=(), exc_info=None,
    )
    record.when = datetime(2026, 5, 7, 12, 0, 0)
    record.tags = {"alpha", "beta"}

    payload = json.loads(formatter.format(record))
    # ``str(datetime)`` is the ISO-ish representation; ``str(set)`` is
    # the repr-like braces. We only check that they're present and
    # string-typed — exact format is whatever Python produces.
    assert isinstance(payload["when"], str)
    assert "2026" in payload["when"]
    assert isinstance(payload["tags"], str)


# ----- configure_logging idempotency -----


def test_configure_logging_is_idempotent(monkeypatch):
    """Repeated calls don't accumulate handlers.

    Forces a clean slate by resetting the module's ``_configured`` flag,
    then calls ``configure_logging`` twice and asserts the root logger
    has exactly one handler attached afterward.
    """
    monkeypatch.setattr(logging_setup, "_configured", False)
    # Save & restore root logger handlers across this test so we don't
    # leak our handler config to other tests in the run.
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    try:
        configure_logging()
        configure_logging()
        assert len([h for h in root.handlers if isinstance(h.formatter, JSONLineFormatter)]) == 1
    finally:
        root.handlers = original_handlers
