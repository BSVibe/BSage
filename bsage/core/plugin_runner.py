"""PluginRunner — executes @plugin-decorated Python functions with context injection."""

from __future__ import annotations

import structlog

from bsage.core.exceptions import CredentialNotFoundError, PluginRunError

if __import__("typing").TYPE_CHECKING:
    from bsage.core.credential_store import CredentialStore
    from bsage.core.plugin_loader import PluginMeta
    from bsage.core.skill_context import SkillContext

logger = structlog.get_logger(__name__)


class PluginRunner:
    """Executes plugins by calling their @plugin-decorated execute/notify functions."""

    def __init__(self, credential_store: CredentialStore | None = None) -> None:
        self._credential_store = credential_store

    async def run(self, meta: PluginMeta, context: SkillContext) -> dict:
        """Execute a plugin's main entrypoint and return the result dict.

        Raises:
            PluginRunError: On execution failure.
        """
        logger.info("plugin_run_start", name=meta.name, category=meta.category)

        await self._auto_inject_credentials(meta.name, context)

        if meta._execute_fn is None:
            raise PluginRunError(f"Plugin '{meta.name}' has no execute function")

        try:
            result = await meta._execute_fn(context)
        except PluginRunError:
            raise
        except Exception as exc:
            raise PluginRunError(f"Plugin '{meta.name}' execution failed: {exc}") from exc

        logger.info("plugin_run_complete", name=meta.name)
        return result

    async def run_notify(self, meta: PluginMeta, context: SkillContext) -> dict:
        """Execute a plugin's notification handler.

        Raises:
            PluginRunError: If the plugin has no notify function or execution fails.
        """
        if meta._notify_fn is None:
            raise PluginRunError(f"Plugin '{meta.name}' has no notification handler")

        logger.info("plugin_notify_start", name=meta.name)

        await self._auto_inject_credentials(meta.name, context)

        try:
            result = await meta._notify_fn(context)
        except PluginRunError:
            raise
        except Exception as exc:
            raise PluginRunError(f"Plugin '{meta.name}' notification failed: {exc}") from exc

        logger.info("plugin_notify_complete", name=meta.name)
        return result

    async def _auto_inject_credentials(self, plugin_name: str, context: SkillContext) -> None:
        """Inject credentials into context.credentials if available."""
        if self._credential_store is None:
            return
        try:
            creds = await self._credential_store.get(plugin_name)
            context.credentials = dict(creds)
        except CredentialNotFoundError:
            pass
