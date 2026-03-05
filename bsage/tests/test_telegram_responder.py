"""Tests for the telegram-responder plugin."""

from unittest.mock import AsyncMock, MagicMock


def _make_context(input_data=None):
    ctx = MagicMock()
    ctx.input_data = input_data
    ctx.llm = AsyncMock()
    ctx.llm.chat = AsyncMock(return_value="Hello! How can I help?")
    ctx.notify = AsyncMock()
    ctx.notify.send = AsyncMock()
    ctx.garden = AsyncMock()
    ctx.garden.write_action = AsyncMock()
    return ctx


def _load_plugin():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "telegram_responder", "plugins/telegram-responder/plugin.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.execute


async def test_replies_to_messages() -> None:
    execute_fn = _load_plugin()
    ctx = _make_context(input_data={"messages": [{"text": "Hi there"}]})
    result = await execute_fn(ctx)

    assert result["replied"] == 1
    ctx.llm.chat.assert_awaited_once()
    ctx.notify.send.assert_awaited_once_with("Hello! How can I help?")
    ctx.garden.write_action.assert_awaited_once()


async def test_replies_to_multiple_messages() -> None:
    execute_fn = _load_plugin()
    ctx = _make_context(input_data={"messages": [{"text": "Hello"}, {"text": "World"}]})
    result = await execute_fn(ctx)

    assert result["replied"] == 2
    # Both messages combined into one LLM call
    call_args = ctx.llm.chat.call_args
    assert "Hello\nWorld" in call_args[1]["messages"][0]["content"]


async def test_no_messages() -> None:
    execute_fn = _load_plugin()
    ctx = _make_context(input_data={"messages": []})
    result = await execute_fn(ctx)

    assert result == {"replied": 0}
    ctx.llm.chat.assert_not_awaited()


async def test_no_input_data() -> None:
    execute_fn = _load_plugin()
    ctx = _make_context(input_data=None)
    result = await execute_fn(ctx)

    assert result == {"replied": 0}


async def test_skips_messages_without_text() -> None:
    execute_fn = _load_plugin()
    ctx = _make_context(input_data={"messages": [{"photo": "abc"}, {"text": "Hi"}]})
    result = await execute_fn(ctx)

    assert result["replied"] == 1


async def test_no_notify_available() -> None:
    execute_fn = _load_plugin()
    ctx = _make_context(input_data={"messages": [{"text": "Hi"}]})
    ctx.notify = None
    result = await execute_fn(ctx)

    assert result["replied"] == 1
    # Should not crash when notify is None


async def test_empty_llm_response() -> None:
    execute_fn = _load_plugin()
    ctx = _make_context(input_data={"messages": [{"text": "Hi"}]})
    ctx.llm.chat = AsyncMock(return_value="   ")
    result = await execute_fn(ctx)

    assert result["replied"] == 1
    ctx.notify.send.assert_not_awaited()  # Empty response not sent
