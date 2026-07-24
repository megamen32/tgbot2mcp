"""Tests for the Telegram adapter."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tgbot2mcp.models import BotInteractionResult, ButtonKind, DiscoveredButton
from tgbot2mcp.telegram.adapter import TelegramAdapter


@pytest.mark.asyncio
async def test_send_message_calls_client(adapter: TelegramAdapter, mock_telethon_client: MagicMock):
    """Test that send_message resolves entity and sends via ConversationManager."""
    mock_entity = MagicMock()
    mock_telethon_client.get_entity = AsyncMock(return_value=mock_entity)
    mock_telethon_client.get_me = AsyncMock(return_value=MagicMock())

    # Mock the ConversationManager.send_and_wait to avoid event handler complexity
    with patch.object(
        adapter.conversation_manager, "send_and_wait", new_callable=AsyncMock
    ) as mock_send_wait:
        mock_msg = MagicMock()
        mock_msg.id = 1
        mock_msg.text = "Hello!"
        mock_msg.date = None
        mock_msg.media = None
        mock_msg.buttons = None
        mock_send_wait.return_value = [mock_msg]

        result = await adapter.send_message("@TestBot", "Hi there")

    assert not result.timed_out
    assert result.messages[0]["text"] == "Hello!"


@pytest.mark.asyncio
async def test_send_command_formats_correctly(adapter: TelegramAdapter, mock_telethon_client: MagicMock):
    """Test that send_command properly formats /command args."""
    mock_entity = MagicMock()
    mock_telethon_client.get_entity = AsyncMock(return_value=mock_entity)

    with patch.object(
        adapter.conversation_manager, "send_and_wait", new_callable=AsyncMock
    ) as mock_send_wait:
        mock_send_wait.return_value = []
        await adapter.send_command("@TestBot", "start", arguments="deep_link_param")

    # Verify the text passed to send_and_wait is the formatted command
    call_args = mock_send_wait.call_args
    assert call_args[0][2] == "/start deep_link_param"  # third positional arg is text


@pytest.mark.asyncio
async def test_send_media_calls_send_file(adapter: TelegramAdapter, mock_telethon_client: MagicMock):
    """Test that send_media sends a file and collects response."""
    mock_entity = MagicMock()
    mock_telethon_client.get_entity = AsyncMock(return_value=mock_entity)

    with patch.object(
        adapter.conversation_manager, "wait_for_response", new_callable=AsyncMock
    ) as mock_wait:
        mock_wait.return_value = []
        result = await adapter.send_media("@TestBot", "/path/to/file.pdf")

    mock_telethon_client.send_file.assert_called_once_with(mock_entity, "/path/to/file.pdf", caption=None)
    assert not result.timed_out


@pytest.mark.asyncio
async def test_get_messages_returns_list(adapter: TelegramAdapter, mock_telethon_client: MagicMock):
    """Test that get_messages returns formatted message dicts."""
    mock_entity = MagicMock()
    mock_telethon_client.get_entity = AsyncMock(return_value=mock_entity)

    mock_msg = MagicMock()
    mock_msg.id = 42
    mock_msg.text = "Bot response"
    mock_msg.date = None
    mock_msg.out = False
    mock_msg.media = None
    mock_msg.buttons = None

    mock_telethon_client.get_messages = AsyncMock(return_value=[mock_msg])

    messages = await adapter.get_messages("@TestBot", limit=5)
    assert len(messages) == 1
    assert messages[0]["id"] == 42
    assert messages[0]["text"] == "Bot response"


@pytest.mark.asyncio
async def test_click_button_not_found(adapter: TelegramAdapter, mock_telethon_client: MagicMock):
    """Test that clicking a non-existent button returns an error."""
    mock_entity = MagicMock()
    mock_telethon_client.get_entity = AsyncMock(return_value=mock_entity)

    mock_msg = MagicMock()
    mock_msg.buttons = []  # No buttons on this message
    mock_telethon_client.get_messages = AsyncMock(return_value=mock_msg)

    result = await adapter.click_button("@TestBot", message_id=42, button_text="Missing")
    assert result.error is not None
    assert "No buttons" in result.error


@pytest.mark.asyncio
async def test_per_bot_lock_serialization(adapter: TelegramAdapter):
    """Test that operations on the same bot are serialized via lock."""
    lock = adapter._get_lock("@TestBot")
    assert isinstance(lock, asyncio.Lock)

    # Same bot should return the same lock
    lock2 = adapter._get_lock("@testbot")
    assert lock is lock2

    # Different bot should get a different lock
    lock3 = adapter._get_lock("@OtherBot")
    assert lock3 is not lock


def test_reset_conversation(adapter: TelegramAdapter):
    """Test that reset_conversation replaces the lock."""
    old_lock = adapter._get_lock("@TestBot")
    adapter.reset_conversation("@TestBot")
    new_lock = adapter._get_lock("@TestBot")
    assert old_lock is not new_lock
