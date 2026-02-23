"""Chat service — vault-aware conversational AI for BSage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from bsage.core.llm import LiteLLMClient
    from bsage.garden.writer import GardenWriter

logger = structlog.get_logger(__name__)

DEFAULT_CONTEXT_PATHS: list[str] = ["garden/idea", "garden/insight"]
_MAX_CONTEXT_CHARS = 16_000

_SYSTEM_PROMPT_TEMPLATE = """\
You are BSage, a personal AI assistant that manages a 2nd Brain (Obsidian Vault).
You help the user think, reflect, connect ideas, and find insights \
in their knowledge base.

When answering:
- Reference relevant notes from the knowledge base when applicable.
- Help the user see connections between their ideas.
- Be thoughtful and concise.
- If asked about something not in the knowledge base, say so and still help.

---

{context_section}"""


async def gather_vault_context(
    garden_writer: GardenWriter,
    context_paths: list[str],
    max_chars: int = _MAX_CONTEXT_CHARS,
) -> str:
    """Read recent vault notes and concatenate them up to *max_chars*.

    Notes are read most-recent-first (reversed filename sort).
    """
    segments: list[str] = []
    total = 0

    for subdir in context_paths:
        try:
            note_paths = await garden_writer.read_notes(subdir)
        except Exception:
            logger.debug("vault_context_skip_dir", subdir=subdir)
            continue

        for path in reversed(note_paths):
            if total >= max_chars:
                break
            try:
                content = await garden_writer.read_note_content(path)
            except Exception:
                continue
            segment = f"## {path.name}\n{content}\n"
            segments.append(segment)
            total += len(segment)

        if total >= max_chars:
            break

    result = "\n".join(segments)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n...(truncated)"
    return result


def build_system_prompt(vault_context: str) -> str:
    """Build the system prompt with vault context injected."""
    if vault_context.strip():
        section = f"Your knowledge base contains these notes:\n\n{vault_context}"
    else:
        section = "The knowledge base is currently empty. Help the user get started."
    return _SYSTEM_PROMPT_TEMPLATE.format(context_section=section)


async def handle_chat(
    message: str,
    history: list[dict[str, Any]],
    llm_client: LiteLLMClient,
    garden_writer: GardenWriter,
    context_paths: list[str] | None = None,
) -> str:
    """Process a chat request: gather context, call LLM, log, return."""
    paths = context_paths or DEFAULT_CONTEXT_PATHS
    vault_context = await gather_vault_context(garden_writer, paths)
    system = build_system_prompt(vault_context)

    messages = [*history, {"role": "user", "content": message}]
    response = await llm_client.chat(system=system, messages=messages)

    summary = f"User: {message[:80]} | Assistant: {response[:80]}"
    await garden_writer.write_action("chat", summary)

    return response
