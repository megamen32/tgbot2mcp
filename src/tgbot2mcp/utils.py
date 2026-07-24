"""Utility functions: FloodWait handling, media helpers, logging."""

from __future__ import annotations

import asyncio
import functools
import logging
import sys
from typing import Any, Callable, TypeVar

from telethon.errors import FloodWaitError

F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger("tgbot2mcp")


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    logging.basicConfig(
        format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        stream=sys.stderr,
    )


def flood_wait_guard(max_retries: int = 3) -> Callable[[F], F]:
    """Decorator that catches FloodWaitError and sleeps before retrying."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: FloodWaitError | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except FloodWaitError as e:
                    last_exc = e
                    wait_secs = e.seconds + 1
                    logger.warning(
                        f"FloodWait in {func.__name__}: "
                        f"sleeping {wait_secs}s (attempt {attempt + 1}/{max_retries + 1})"
                    )
                    await asyncio.sleep(wait_secs)
            raise last_exc  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


def extract_text_from_message(msg: Any) -> str:
    """Extract text content from a Telethon message, handling various types."""
    if msg is None:
        return ""
    if hasattr(msg, "text") and msg.text:
        return msg.text
    if hasattr(msg, "message") and msg.message:
        return msg.message
    if hasattr(msg, "caption") and msg.caption:
        return msg.caption
    return ""


def extract_commands_from_text(text: str) -> list[str]:
    """Parse slash commands from message text (e.g. '/start - Begin interaction')."""
    import re

    commands = []
    for match in re.finditer(r"/([a-zA-Z]\w+)", text):
        commands.append(match.group(1))
    return commands
