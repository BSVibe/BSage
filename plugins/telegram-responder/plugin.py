"""Telegram responder Plugin — auto-replies to incoming Telegram messages via LLM."""

from bsage.plugin import plugin


@plugin(
    name="telegram-responder",
    version="1.0.0",
    category="process",
    description="Generate LLM responses to incoming Telegram messages and send them back",
    trigger={"type": "on_input", "sources": ["telegram-input"]},
)
async def execute(context) -> dict:
    """Generate an LLM reply for each incoming Telegram message and send via notify."""
    raw = context.input_data or {}
    messages = raw.get("messages", [])
    if not messages:
        return {"replied": 0}

    # Build conversation from incoming messages
    user_texts = [m.get("text", "") for m in messages if m.get("text")]
    if not user_texts:
        return {"replied": 0}

    combined = "\n".join(user_texts)
    reply = await context.llm.chat(
        system=(
            "You are BSage, a helpful personal AI assistant communicating via Telegram. "
            "Keep responses concise and friendly. Reply in the same language as the user's message."
        ),
        messages=[{"role": "user", "content": combined}],
    )

    if context.notify and reply.strip():
        await context.notify.send(reply.strip())

    await context.garden.write_action(
        "telegram-responder",
        f"Replied to {len(user_texts)} message(s)",
    )
    return {"replied": len(user_texts), "response_length": len(reply)}
