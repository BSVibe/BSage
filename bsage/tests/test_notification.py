"""Tests for bsage.core.notification — NotificationRouter plugin routing."""

from unittest.mock import AsyncMock, MagicMock

from bsage.core.notification import NotificationRouter
from bsage.core.plugin_loader import PluginMeta


def _make_notify_fn():
    return AsyncMock(return_value={"sent": True})


def _make_plugin_meta(**overrides) -> PluginMeta:
    defaults = {
        "name": "telegram-input",
        "version": "1.0.0",
        "category": "input",
        "is_dangerous": False,
        "description": "Receive and send messages via Telegram",
    }
    defaults.update(overrides)
    meta = PluginMeta(**defaults)
    return meta


class TestNotificationRouterSetup:
    """Test auto-discovery from registry."""

    def test_setup_discovers_notification_capable_plugins(self) -> None:
        router = NotificationRouter()
        tg_meta = _make_plugin_meta()
        tg_meta._notify_fn = _make_notify_fn()
        cal_meta = _make_plugin_meta(name="calendar-input", description="Fetch calendar events")
        # calendar-input has no _notify_fn

        registry = {
            "telegram-input": tg_meta,
            "calendar-input": cal_meta,
        }
        router.setup(registry, MagicMock(), MagicMock())
        assert len(router._plugins) == 1
        assert router._plugins[0].name == "telegram-input"

    def test_setup_finds_multiple_channels(self) -> None:
        router = NotificationRouter()
        tg_meta = _make_plugin_meta()
        tg_meta._notify_fn = _make_notify_fn()
        slack_meta = _make_plugin_meta(name="slack-input", description="Slack")
        slack_meta._notify_fn = _make_notify_fn()

        registry = {
            "telegram-input": tg_meta,
            "slack-input": slack_meta,
        }
        router.setup(registry, MagicMock(), MagicMock())
        assert len(router._plugins) == 2

    def test_setup_with_no_notification_plugins(self) -> None:
        router = NotificationRouter()
        cal_meta = _make_plugin_meta(name="calendar-input")
        # no _notify_fn

        registry = {"calendar-input": cal_meta}
        router.setup(registry, MagicMock(), MagicMock())
        assert len(router._plugins) == 0

    def test_setup_ignores_skill_meta_entries(self) -> None:
        from bsage.core.skill_loader import SkillMeta

        router = NotificationRouter()
        skill = SkillMeta(
            name="weekly-digest",
            version="1.0.0",
            category="process",
            is_dangerous=False,
            description="Weekly digest",
        )
        registry = {"weekly-digest": skill}
        router.setup(registry, MagicMock(), MagicMock())
        assert len(router._plugins) == 0


class TestNotificationRouterSend:
    """Test notification delivery through plugins."""

    async def test_send_calls_run_notify(self) -> None:
        router = NotificationRouter()
        runner = MagicMock()
        runner.run_notify = AsyncMock(return_value={"sent": True})
        ctx = MagicMock()
        builder = MagicMock(return_value=ctx)

        meta = _make_plugin_meta()
        meta._notify_fn = _make_notify_fn()

        registry = {"telegram-input": meta}
        router.setup(registry, runner, builder)
        await router.send("Hello!", level="info")

        runner.run_notify.assert_called_once()
        builder.assert_called_once_with(
            input_data={"message": "Hello!", "level": "info"},
        )

    async def test_send_sets_notify_none_to_prevent_recursion(self) -> None:
        router = NotificationRouter()
        runner = MagicMock()
        runner.run_notify = AsyncMock(return_value={})
        ctx = MagicMock()
        ctx.notify = router  # would cause recursion if not cleared
        builder = MagicMock(return_value=ctx)

        meta = _make_plugin_meta()
        meta._notify_fn = _make_notify_fn()

        registry = {"telegram-input": meta}
        router.setup(registry, runner, builder)
        await router.send("test")

        assert ctx.notify is None

    async def test_send_executes_multiple_channels(self) -> None:
        router = NotificationRouter()
        runner = MagicMock()
        runner.run_notify = AsyncMock(return_value={})
        builder = MagicMock(return_value=MagicMock())

        tg_meta = _make_plugin_meta()
        tg_meta._notify_fn = _make_notify_fn()
        slack_meta = _make_plugin_meta(name="slack-input", description="Slack")
        slack_meta._notify_fn = _make_notify_fn()

        registry = {
            "telegram-input": tg_meta,
            "slack-input": slack_meta,
        }
        router.setup(registry, runner, builder)
        await router.send("broadcast")

        assert runner.run_notify.call_count == 2

    async def test_send_continues_on_plugin_failure(self) -> None:
        router = NotificationRouter()
        runner = MagicMock()
        runner.run_notify = AsyncMock(
            side_effect=[RuntimeError("fail"), {"sent": True}],
        )
        builder = MagicMock(return_value=MagicMock())

        broken_meta = _make_plugin_meta(name="broken-input", description="Broken")
        broken_meta._notify_fn = _make_notify_fn()
        working_meta = _make_plugin_meta(name="working-input", description="Working")
        working_meta._notify_fn = _make_notify_fn()

        registry = {
            "broken-input": broken_meta,
            "working-input": working_meta,
        }
        router.setup(registry, runner, builder)
        await router.send("test")

        assert runner.run_notify.call_count == 2


class TestNotificationRouterFallback:
    """Test silent fallback when no channels available."""

    async def test_send_without_setup_does_not_raise(self) -> None:
        router = NotificationRouter()
        await router.send("hello")

    async def test_send_with_no_channels_does_not_raise(self) -> None:
        router = NotificationRouter()
        router.setup({}, MagicMock(), MagicMock())
        await router.send("hello")
