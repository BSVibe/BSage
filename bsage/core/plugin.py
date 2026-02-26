"""@plugin decorator — Plugin 메타데이터를 Python에 직접 선언."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def plugin(
    *,
    name: str,
    category: str,
    version: str = "0.1.0",
    description: str = "",
    author: str = "",
    trigger: dict[str, Any] | None = None,
    credentials: list[dict[str, Any]] | None = None,
    input_schema: dict[str, Any] | None = None,
) -> Callable:
    """Plugin 메타데이터를 execute 함수에 부착하는 decorator.

    Only ``name`` and ``category`` are required.  Everything else has a
    sensible default so minimal plugins stay concise::

        from bsage.plugin import plugin

        @plugin(name="my-plugin", category="input")
        async def execute(context):
            \"\"\"Docstring becomes the description when none is given.\"\"\"
            ...

        @execute.notify
        async def notify(context):
            ...

    The decorator attaches a ``__plugin__`` dict to the function and adds
    a ``.notify`` helper for registering the bidirectional notification handler.
    If ``description`` is empty the function's docstring is used instead.

    Note: ``is_dangerous`` is no longer declared by the author. It is
    auto-computed by ``DangerAnalyzer`` at load time via static code analysis.
    """

    def decorator(fn: Callable) -> Callable:
        fn.__plugin__ = {
            "name": name,
            "version": version,
            "category": category,
            "description": description or (fn.__doc__ or "").strip(),
            "author": author,
            "trigger": trigger,
            "credentials": credentials,
            "input_schema": input_schema,
        }

        def _attach_notify(notify_fn: Callable) -> Callable:
            """Register a notification handler on this plugin's execute function."""
            fn.__notify__ = notify_fn
            return notify_fn

        fn.notify = _attach_notify
        return fn

    return decorator
