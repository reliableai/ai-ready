"""Internal Python API — the only layer that touches SQL.

Section 6 of the lesson. Every named entity gets the same five
operations (``create``, ``get``, ``get_by_slug``, ``update``,
``delete``, ``query``); rels has its own three (``add``, ``remove``,
``list``). Both ``http/`` and (in lesson 3) ``mcp/`` sit on top.

Error conventions (see CLAUDE.md):
- ``get`` / ``get_by_slug`` → returns ``None`` on not found
- ``create`` → raises ``sqlite3.IntegrityError`` on slug / FK conflict
- ``update`` / ``delete`` → raise ``NotFound`` on missing row, ``IntegrityError`` on conflict
"""


class NotFound(Exception):
    """Raised by api/ functions when a row by id doesn't exist."""
