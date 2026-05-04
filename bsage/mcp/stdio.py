"""Stdio transport for the BSage MCP server.

Entry point for the ``bsage-mcp`` console script. Runs an MCP server
over stdin/stdout — the protocol Claude Desktop uses.

CRITICAL: stdio MCP uses stdout for JSON-RPC framing. Any library that
prints to stdout (structlog defaults, click banners, etc.) corrupts the
stream. ``_configure_stdio_logging`` redirects all logging to stderr
before the server starts.
"""

from __future__ import annotations

import asyncio
import logging
import sys

import structlog


def _configure_stdio_logging() -> None:
    """Send all logs to stderr so the JSON-RPC stdout channel stays clean."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)
    root = logging.getLogger()
    # Replace any existing handlers — some test runners or env loaders
    # may have wired stdout handlers already.
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    structlog.configure(
        processors=[structlog.processors.JSONRenderer()],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )


async def run_stdio_server() -> None:
    """Bring up the MCP stdio server with a fully wired AppState."""
    from mcp.server.stdio import stdio_server

    from bsage.core.config import get_settings
    from bsage.gateway.dependencies import AppState
    from bsage.mcp.server import build_server

    _configure_stdio_logging()

    state = AppState(get_settings())
    await state.initialize()
    try:
        server = build_server(state)
        async with stdio_server() as (read_stream, write_stream):
            init_options = server.create_initialization_options()
            await server.run(read_stream, write_stream, init_options)
    finally:
        await state.shutdown()


def main() -> None:
    """Console-script entry point — `bsage-mcp`."""
    try:
        asyncio.run(run_stdio_server())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
