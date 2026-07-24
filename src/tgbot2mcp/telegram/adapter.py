"""
High-level Telegram bot interaction adapter.

Adapted from TgTestKit's BotController patterns.
Provides send_message, send_command, click_button, get_messages, send_media, etc.
All operations are serialized per-bot via ConversationManager.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from telethon import TelegramClient
from telethon.hints import EntityLike
from telethon.tl.custom.message import Message
from telethon.tl.custom.messagebutton import MessageButton
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import BotCommand, User

from tgbot2mcp.config import AppConfig
from tgbot2mcp.exceptions import ButtonNotFoundError, ConversationTimeoutError
from tgbot2mcp.models import BotInteractionResult, ButtonKind, DiscoveredButton
from tgbot2mcp.telegram.conversation import ConversationManager
from tgbot2mcp.utils import extract_text_from_message, flood_wait_guard

logger = logging.getLogger("tgbot2mcp.telegram.adapter")


class TelegramAdapter:
    """
    High-level interface for interacting with a specific Telegram bot.

    Inspired by TgTestKit's BotController, adapted for MCP tool usage.
    All operations are serialized per-bot via ConversationManager.
    """

    def __init__(
        self,
        client: TelegramClient,
        config: AppConfig,
    ) -> None:
        self.client = client
        self.config = config
        self._conversation = ConversationManager(client, config)
        self._entities: dict[str, EntityLike] = {}
        self._me: User | None = None

    @property
    def conversation_manager(self) -> ConversationManager:
        """Access the underlying ConversationManager."""
        return self._conversation

    async def _get_me(self) -> User:
        if self._me is None:
            self._me = await self.client.get_me()
        return self._me

    def _get_lock(self, bot_username: str) -> asyncio.Lock:
        """Get or create a per-bot lock for conversation serialization."""
        return self._conversation.get_lock(bot_username)

    async def _resolve_entity(self, bot_username: str) -> EntityLike:
        """Resolve and cache a bot entity."""
        key = bot_username.lower().lstrip("@")
        if key not in self._entities:
            self._entities[key] = await self.client.get_entity(bot_username)
        return self._entities[key]

    def _messages_to_result(
        self,
        collected: list[Message],
        timed_out: bool = False,
        error: str | None = None,
    ) -> BotInteractionResult:
        """Convert collected Telethon messages to a BotInteractionResult."""
        result = BotInteractionResult(timed_out=timed_out, error=error)

        for msg in collected:
            text = extract_text_from_message(msg)
            msg_dict: dict[str, Any] = {
                "id": msg.id,
                "text": text,
                "date": str(msg.date) if msg.date else None,
            }

            if msg.media:
                msg_dict["has_media"] = True
                msg_dict["media_type"] = type(msg.media).__name__

            result.messages.append(msg_dict)

            if msg.buttons:
                for row in msg.buttons:
                    for btn in row:
                        discovered_btn = DiscoveredButton(
                            text=btn.text,
                            kind=ButtonKind.INLINE if (btn.data or btn.url) else ButtonKind.REPLY,
                            message_id=msg.id,
                            callback_data=btn.data.hex() if isinstance(btn.data, bytes) else (btn.data if btn.data else None),
                            url=btn.url,
                        )
                        result.buttons.append(discovered_btn)

        return result

    @flood_wait_guard(max_retries=3)
    async def send_message(
        self,
        bot_username: str,
        text: str,
        files: list[str] | None = None,
        timeout: float | None = None,
    ) -> BotInteractionResult:
        """Send a text message (and optional files) to the bot and return the response."""
        lock = self._get_lock(bot_username)
        async with lock:
            entity = await self._resolve_entity(bot_username)

            # Respect global action delay
            await asyncio.sleep(self.config.global_action_delay)

            # Send files first if present
            if files:
                await self.client.send_file(entity, files)

            # Send text and collect response via ConversationManager
            try:
                collected = await self._conversation.send_and_wait(
                    bot_username, entity, text, timeout=timeout,
                )
                return self._messages_to_result(collected)
            except ConversationTimeoutError:
                return BotInteractionResult(timed_out=True)

    @flood_wait_guard(max_retries=3)
    async def send_command(
        self,
        bot_username: str,
        command: str,
        arguments: str | None = None,
        timeout: float | None = None,
    ) -> BotInteractionResult:
        """Send a slash command to the bot and return the response."""
        text = f"/{command.lstrip('/')}"
        if arguments:
            text += f" {arguments}"
        return await self.send_message(bot_username, text, timeout=timeout)

    @flood_wait_guard(max_retries=3)
    async def send_media(
        self,
        bot_username: str,
        file_path: str,
        caption: str | None = None,
        timeout: float | None = None,
    ) -> BotInteractionResult:
        """Send a document/photo to the bot and return the response."""
        lock = self._get_lock(bot_username)
        async with lock:
            entity = await self._resolve_entity(bot_username)
            await asyncio.sleep(self.config.global_action_delay)

            await self.client.send_file(entity, file_path, caption=caption)

            try:
                collected = await self._conversation.wait_for_response(
                    bot_username, entity, timeout=timeout,
                )
                return self._messages_to_result(collected)
            except ConversationTimeoutError:
                return BotInteractionResult(timed_out=True)

    @flood_wait_guard(max_retries=3)
    async def click_button(
        self,
        bot_username: str,
        message_id: int,
        button_text: str | None = None,
        button_index: int | None = None,
        timeout: float | None = None,
    ) -> BotInteractionResult:
        """Click an inline or reply button on a specific message."""
        lock = self._get_lock(bot_username)
        async with lock:
            entity = await self._resolve_entity(bot_username)

            # Fetch the message to get its buttons
            msg = await self.client.get_messages(entity, ids=message_id)
            if msg is None:
                return BotInteractionResult(error=f"Message {message_id} not found")

            if not msg.buttons:
                return BotInteractionResult(error=f"No buttons on message {message_id}")

            # Find the button
            target_btn: MessageButton | None = None
            if button_text is not None:
                for row in msg.buttons:
                    for btn in row:
                        if btn.text == button_text:
                            target_btn = btn
                            break
                    if target_btn:
                        break
            elif button_index is not None:
                flat_buttons = [btn for row in msg.buttons for btn in row]
                if 0 <= button_index < len(flat_buttons):
                    target_btn = flat_buttons[button_index]

            if target_btn is None:
                return BotInteractionResult(
                    error=f"Button not found: text={button_text}, index={button_index}"
                )

            await asyncio.sleep(self.config.global_action_delay)
            await target_btn.click()

            try:
                collected = await self._conversation.wait_for_response(
                    bot_username, entity, timeout=timeout,
                )
                return self._messages_to_result(collected)
            except ConversationTimeoutError:
                return BotInteractionResult(timed_out=True)

    async def get_messages(
        self,
        bot_username: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch recent messages from the bot's chat."""
        lock = self._get_lock(bot_username)
        async with lock:
            entity = await self._resolve_entity(bot_username)
            messages = await self.client.get_messages(entity, limit=limit)

            result = []
            for msg in messages:
                text = extract_text_from_message(msg)
                msg_dict: dict[str, Any] = {
                    "id": msg.id,
                    "text": text,
                    "out": msg.out,
                    "date": str(msg.date) if msg.date else None,
                }
                if msg.media:
                    msg_dict["has_media"] = True
                    msg_dict["media_type"] = type(msg.media).__name__
                result.append(msg_dict)
            return result

    async def get_bot_commands(self, bot_username: str) -> list[BotCommand]:
        """Get the bot's registered commands via the Telegram API."""
        entity = await self._resolve_entity(bot_username)
        try:
            full_user = await self.client(GetFullUserRequest(entity))
            if full_user.full_user.bot_info:
                return full_user.full_user.bot_info.commands or []
        except Exception as e:
            logger.warning(f"Could not fetch bot commands for {bot_username}: {e}")
        return []

    def reset_conversation(self, bot_username: str) -> None:
        """Reset the conversation lock and state for a bot."""
        self._conversation.reset(bot_username)
