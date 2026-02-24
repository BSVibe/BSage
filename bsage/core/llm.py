"""LiteLLM client — unified LLM interface via litellm.acompletion."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import litellm
import structlog
from litellm.types.utils import Choices, Message, ModelResponse

from bsage.core.skill_context import ToolHandler

if TYPE_CHECKING:
    from bsage.core.runtime_config import RuntimeConfig

logger = structlog.get_logger(__name__)


class LiteLLMClient:
    """Wrapper around litellm.acompletion that reads config per-call.

    Holds a reference to a RuntimeConfig instance so that LLM model,
    API key, and API base can be changed at runtime without restart.
    """

    def __init__(self, runtime_config: RuntimeConfig) -> None:
        self._config = runtime_config

    async def chat(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_handler: ToolHandler | None = None,
        max_rounds: int = 10,
    ) -> str:
        """Send a chat completion request via litellm.

        When ``tools`` and ``tool_handler`` are provided, runs a tool-use
        loop: the LLM can return tool_calls which are executed via
        ``tool_handler`` and fed back until a final text response.

        Args:
            system: System prompt.
            messages: List of message dicts (role + content).
            tools: Optional OpenAI-format tool definitions.
            tool_handler: Optional async callback (tool_call_id, name, args) -> result JSON.
            max_rounds: Max tool-use round-trips (only used with tools).

        Returns:
            The assistant's response text.
        """
        work_messages = [{"role": "system", "content": system}, *messages]

        if not tools or not tool_handler:
            logger.info(
                "llm_request", model=self._config.llm_model, message_count=len(work_messages)
            )
            msg = await self._complete(work_messages)
            text = msg.content or ""
            logger.info("llm_response", model=self._config.llm_model, length=len(text))
            return text

        for round_num in range(max_rounds):
            logger.info(
                "llm_tool_request",
                model=self._config.llm_model,
                round=round_num,
                message_count=len(work_messages),
            )
            assistant_msg = await self._complete(work_messages, tools=tools)

            tool_calls = assistant_msg.tool_calls
            if not tool_calls:
                text = assistant_msg.content or ""
                logger.info("llm_tool_response", model=self._config.llm_model, length=len(text))
                return text

            work_messages.append(assistant_msg.model_dump())

            for tc in tool_calls:
                tc_id = tc.id or ""
                fn_name = tc.function.name or ""
                try:
                    fn_args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    fn_args = {}

                logger.info("tool_call", name=fn_name, tool_call_id=tc_id)
                result = await tool_handler(tc_id, fn_name, fn_args)
                work_messages.append({"role": "tool", "tool_call_id": tc_id, "content": result})

        logger.warning("tool_max_rounds_exceeded", max_rounds=max_rounds)
        last_text = ""
        for msg_dict in reversed(work_messages):
            if isinstance(msg_dict, dict) and msg_dict.get("role") == "assistant":
                last_text = msg_dict.get("content") or ""
                break
        return last_text

    async def _complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
    ) -> Message:
        """Call litellm.acompletion and return the first choice's message."""
        model: str = self._config.llm_model
        api_key: str = self._config.llm_api_key
        api_base: str | None = self._config.llm_api_base

        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base
        if tools:
            kwargs["tools"] = tools

        response = cast(ModelResponse, await litellm.acompletion(**kwargs))

        if not response.choices:
            raise RuntimeError("LLM returned empty choices")

        return cast(Choices, response.choices[0]).message
