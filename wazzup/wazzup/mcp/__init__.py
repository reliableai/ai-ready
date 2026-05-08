"""MCP server — exposes a curated subset of ``wazzup.api`` as agent tools.

This package is the lesson-3 adapter: a ``@mcp.tool()`` per agent-exposed
operation, calling ``wazzup.api.*`` directly (in-process — no HTTP). The
tool surface is a deliberate subset: read operations are open; write
operations take an explicit ``as_user_slug`` arg so the caller picks
identity (no auth in this v0.3 demo); destructive operations (clear
chat) are deliberately *not* exposed.

Run with::

    uv run python -m wazzup.mcp.server
"""
