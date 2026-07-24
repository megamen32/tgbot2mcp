"""
Per-bot conversation state management and serialization.

Ensures that only one conversation is active per bot at any time,
handles multi-step conversations, edited messages, and timeouts.

Adapted from TgTestKit's collector and BotController patterns.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from telethon import TelegramClient
from telethon.events import MessageEdited, NewMessage
from telethon.hints import EntityLike
from telethon.tl.custom.message import Message

from tgbot2mcp.config import AppConfig
from tgbot2mcp.exceptions import ConversationTimeoutError
from tgbot2mcp.utils import extract_text_from_message

logger = logging.getLogger("tgbot2mcp.telegram.conversation")


@dataclass
class ConversationState:
    """Tracks the state of an active conversation with a bot."""

    bot_username: str
    bot_entity: EntityLike
    messages_received: list[Message] = field(default_factory=list)
    is_active: bool = False
    last_response_ts: float | None = None


class ConversationManager:
    """
    Manages per-bot conversation serialization and state.

    Each bot gets its own asyncio.Lock to ensure only one conversation
    is active at a time. This prevents interleaved messages when multiple
    MCP tools try to interact with the same bot concurrently.

    Key features:
    - Per-bot asyncio.Lock for serialization
    - send_and_wait: send a message and collect the bot's response
    - Handles edited messages (some bots edit instead of sending new)
    - Configurable timeouts with ConversationTimeoutError
    - Track conversation state per bot
    """

    def __init__(self, client: TelegramClient, config: AppConfig) -> None:
        self.client = client
        self.config = config
        self._locks: dict[str, asyncio.Lock] = {}
        self._states: dict[str, ConversationState] = {}

    def _normalize_key(self, bot_username: str) -> str:
        return bot_username.lower().lstrip("@")

    def get_lock(self, bot_username: str) -> asyncio.Lock:
        """Get or create the per-bot lock."""
        key = self._normalize_key(bot_username)
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def get_state(self, bot_username: str) -> ConversationState | None:
        """Get the current conversation state for a bot, if any."""
        key = self._normalize_key(bot_username)
        return self._states.get(key)

    def reset(self, bot_username: str) -> None:
        """Reset the conversation state and lock for a bot."""
        key = self._normalize_key(bot_username)
        self._locks[key] = asyncio.Lock()
        self._states.pop(key, None)
        logger.info(f"Reset conversation state for {bot_username}")

    async def send_and_wait(
        self,
        bot_username: str,
        bot_entity: EntityLike,
        text: str,
        timeout: float | None = None,
    ) -> list[Message]:
        """
        Send a message to the bot and wait for its response.

        This is the core conversation primitive. It:
        1. Registers event handlers for new messages and edited messages
        2. Sends the text
        3. Waits for the first response (up to `timeout`)
        4. Continues waiting for consecutive messages (bots often send multiple)
        5. Returns all collected messages

        Handles the case where bots edit their response instead of sending
        a new message (common with callback buttons).
        """
        timeout = timeout or self.config.default_timeout
        wait_consecutive = self.config.wait_consecutive
        bot_id = getattr(bot_entity, "id", None)

        collected: list[Message] = []
        event = asyncio.Event()

        async def _handler(update: Any) -> None:
            msg = getattr(update, "message", None)
            if msg is None:
                msg = update
            if hasattr(msg, "sender_id") and msg.sender_id == bot_id:
                collected.append(msg)
                event.set()

        # Register handlers for new + edited messages
        new_msg_event = NewMessage(chats=[bot_id], incoming=True)
        edited_msg_event = MessageEdited(chats=[bot_id], incoming=True)
        self.client.add_event_handler(_handler, new_msg_event)
        self.client.add_event_handler(_handler, edited_msg_event)

        try:
            # Send the message
            if text:
                await self.client.send_message(bot_entity, text)

            # Wait for first response
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                raise ConversationTimeoutError(bot_username, timeout)

            # Wait for consecutive messages
            while True:
                event.clear()
                try:
                    await asyncio.wait_for(event.wait(), timeout=wait_consecutive)
                except asyncio.TimeoutError:
                    break

        finally:
            self.client.remove_event_handler(_handler, new_msg_event)
            self.client.remove_event_handler(_handler, edited_msg_event)

        # Update conversation state
        key = self._normalize_key(bot_username)
        state = ConversationState(
            bot_username=bot_username,
            bot_entity=bot_entity,
            messages_received=collected,
            is_active=False,
        )
        self._states[key] = state

        return collected

    async def wait_for_response(
        self,
        bot_username: str,
        bot_entity: EntityLike,
        timeout: float | None = None,
    ) -> list[Message]:
        """
        Wait for the bot to send a message without sending anything first.

        Useful for waiting for delayed responses or multi-step interactions.
        """
        timeout = timeout or self.config.default_timeout
        wait_consecutive = self.config.wait_consecutive
        bot_id = getattr(bot_entity, "id", None)

        collected: list[Message] = []
        event = asyncio.Event()

        async def _handler(update: Any) -> None:
            msg = getattr(update, "message", None)
            if msg is None:
                msg = update
            if hasattr(msg, "sender_id") and msg.sender_id == bot_id:
                collected.append(msg)
                event.set()

        new_msg_event = NewMessage(chats=[bot_id], incoming=True)
        edited_msg_event = MessageEdited(chats=[bot_id], incoming=True)
        self.client.add_event_handler(_handler, new_msg_event)
        self.client.add_event_handler(_handler, edited_msg_event)

        try:
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                raise ConversationTimeoutError(bot_username, timeout)

            while True:
                event.clear()
                try:
                    await asyncio.wait_for(event.wait(), timeout=wait_consecutive)
                except asyncio.TimeoutError:
                    break
        finally:
            self.client.remove_event_handler(_handler, new_msg_event)
            self.client.remove_event_handler(_handler, edited_msg_event)

        return collected
