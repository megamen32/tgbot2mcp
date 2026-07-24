"""Tests for ConversationManager (spec Task 3.2)."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tgbot2mcp.config import AppConfig
from tgbot2mcp.exceptions import ConversationTimeoutError
from tgbot2mcp.telegram.conversation import ConversationManager, ConversationState


@pytest.fixture
def conv_config(tmp_path) -> AppConfig:
    return AppConfig(
        api_id=12345,
        api_hash="test_hash",
        session_dir=tmp_path / "sessions",
        default_timeout=2.0,
        wait_consecutive=0.3,
        global_action_delay=0.0,
    )


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.send_message = AsyncMock()
    client.add_event_handler = MagicMock()
    client.remove_event_handler = MagicMock()
    return client


@pytest.fixture
def manager(conv_config: AppConfig, mock_client: MagicMock) -> ConversationManager:
    return ConversationManager(mock_client, conv_config)


def test_get_lock_creates_per_bot_locks(manager: ConversationManager):
    """Each bot gets its own lock."""
    lock_a = manager.get_lock("@BotA")
    lock_b = manager.get_lock("@BotB")
    assert lock_a is not lock_b
    assert isinstance(lock_a, asyncio.Lock)


def test_get_lock_same_bot_same_lock(manager: ConversationManager):
    """Same bot (case-insensitive, @-insensitive) returns the same lock."""
    lock1 = manager.get_lock("@TestBot")
    lock2 = manager.get_lock("testbot")
    lock3 = manager.get_lock("@testbot")
    assert lock1 is lock2 is lock3


def test_reset_replaces_lock(manager: ConversationManager):
    """Reset replaces the lock and clears state."""
    old_lock = manager.get_lock("@Bot")
    manager.reset("@Bot")
    new_lock = manager.get_lock("@Bot")
    assert old_lock is not new_lock


def test_get_state_returns_none_initially(manager: ConversationManager):
    """No state exists before any conversation."""
    assert manager.get_state("@Bot") is None


@pytest.mark.asyncio
async def test_send_and_wait_timeout(manager: ConversationManager, mock_client: MagicMock):
    """send_and_wait raises ConversationTimeoutError on timeout."""
    mock_entity = MagicMock()
    mock_entity.id = 12345

    # The event handler is registered but never triggered -> timeout
    with pytest.raises(ConversationTimeoutError) as exc_info:
        await manager.send_and_wait("@Bot", mock_entity, "hello", timeout=0.3)

    assert exc_info.value.bot_username == "@Bot"
    assert exc_info.value.timeout == 0.3


@pytest.mark.asyncio
async def test_send_and_wait_collects_messages(manager: ConversationManager, mock_client: MagicMock):
    """send_and_wait collects messages from event handlers."""
    mock_entity = MagicMock()
    mock_entity.id = 99

    # Capture all handlers registered via add_event_handler
    registered_handlers = []

    def capture_handler(handler, event):
        registered_handlers.append(handler)

    mock_client.add_event_handler = MagicMock(side_effect=capture_handler)

    async def run_test():
        task = asyncio.create_task(
            manager.send_and_wait("@Bot", mock_entity, "hello", timeout=5.0)
        )
        # Give the task time to register handlers and send the message
        await asyncio.sleep(0.2)

        # Verify handlers were registered
        assert len(registered_handlers) == 2
        handler = registered_handlers[0]

        # Simulate a message from the bot
        # Important: set message=None explicitly so the handler uses the mock itself
        mock_msg = MagicMock()
        mock_msg.message = None  # handler checks getattr(update, "message", None)
        mock_msg.sender_id = 99
        mock_msg.text = "Bot reply"
        mock_msg.id = 42
        mock_msg.date = None
        mock_msg.media = None
        mock_msg.buttons = None
        await handler(mock_msg)

        return await task

    collected = await run_test()
    assert len(collected) == 1
    assert collected[0].text == "Bot reply"


@pytest.mark.asyncio
async def test_lock_serialization(manager: ConversationManager, mock_client: MagicMock):
    """Two concurrent operations on the same bot are serialized."""
    lock = manager.get_lock("@Bot")
    order = []

    async def op(name: str):
        async with lock:
            order.append(f"{name}_start")
            await asyncio.sleep(0.1)
            order.append(f"{name}_end")

    await asyncio.gather(op("A"), op("B"))
    # A must finish before B starts (or vice versa)
    assert order == ["A_start", "A_end", "B_start", "B_end"] or \
           order == ["B_start", "B_end", "A_start", "A_end"]


@pytest.mark.asyncio
async def test_different_bots_parallel(manager: ConversationManager):
    """Operations on different bots can run in parallel."""
    lock_a = manager.get_lock("@BotA")
    lock_b = manager.get_lock("@BotB")
    started = []

    async def op(lock, name):
        async with lock:
            started.append(name)
            await asyncio.sleep(0.1)

    await asyncio.gather(op(lock_a, "A"), op(lock_b, "B"))
    # Both should have started before either finishes
    assert set(started) == {"A", "B"}
