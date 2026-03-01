"""NotificationInterface — protocol and router for sending user notifications."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

from bsage.core.protocols import ContextBuilderLike, NotifyRunnerLike

if TYPE_CHECKING:
    from bsage.core.plugin_loader import PluginMeta

logger = structlog.get_logger(__name__)


@runtime_checkable
class NotificationInterface(Protocol):
    """Interface for delivering messages to the user."""

    async def send(self, message: str, level: str = "info") -> None: ...


class NotificationRouter:
    """Routes notifications through plugins that have a notification handler.

    Input plugins with a ``_notify_fn`` (registered via ``@execute.notify``) can
    send messages back through the same channel they receive from.
    Example: a Telegram input plugin can also send notifications via the same bot.

    Auto-discovers notification-capable plugins from the registry during setup().
    """

    def __init__(self) -> None:
        self._plugins: list[PluginMeta] = []
        self._runner: NotifyRunnerLike | None = None
        self._context_builder: ContextBuilderLike | None = None

    def setup(
        self,
        registry: Mapping[str, object],
        runner: NotifyRunnerLike,
        context_builder: ContextBuilderLike,
    ) -> None:
        """Auto-discover notification-capable plugins from the unified registry.

        Args:
            registry: Full plugin+skill registry to scan.
            runner: Runner instance with run_notify support.
            context_builder: Callable(input_data=dict) -> SkillContext.
        """
        from bsage.core.plugin_loader import PluginMeta

        self._plugins = [
            meta
            for meta in registry.values()
            if isinstance(meta, PluginMeta) and meta._notify_fn is not None
        ]
        self._runner = runner
        self._context_builder = context_builder
        if self._plugins:
            logger.info(
                "notification_channels_discovered",
                plugins=[m.name for m in self._plugins],
            )

    async def send(self, message: str, level: str = "info") -> None:
        """Send a notification through discovered notification plugins.

        Falls back silently (log only) when no plugins are available.
        """
        if not self._plugins or not self._runner or not self._context_builder:
            logger.info("notification_no_channel", level=level)
            return

        for meta in self._plugins:
            try:
                ctx = self._context_builder(
                    input_data={"message": message, "level": level},
                )
                # Prevent recursion: notification plugins cannot send notifications
                ctx.notify = None
                await self._runner.run_notify(meta, ctx)
                logger.info("notification_sent", plugin=meta.name, level=level)
            except Exception:
                logger.warning(
                    "notification_plugin_failed",
                    plugin=meta.name,
                    exc_info=True,
                )
