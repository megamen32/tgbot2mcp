"""Tests for bot discovery."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tgbot2mcp.config import AppConfig
from tgbot2mcp.models import BotInteractionResult, ButtonKind, DiscoveredButton
from tgbot2mcp.telegram.adapter import TelegramAdapter
from tgbot2mcp.telegram.discovery import BotDiscovery
from tgbot2mcp.utils import extract_commands_from_text


def test_extract_commands_from_text():
    """Test parsing slash commands from message text."""
    text = "Available commands: /start - begin, /help - show help, /settings - configure"
    commands = extract_commands_from_text(text)
    assert "start" in commands
    assert "help" in commands
    assert "settings" in commands


def test_extract_commands_empty_text():
    """Test that empty text returns no commands."""
    assert extract_commands_from_text("") == []
    assert extract_commands_from_text("No commands here") == []


@pytest.mark.asyncio
async def test_discovery_calls_send_command(adapter: TelegramAdapter):
    """Test that discovery sends /start and /help commands."""
    config = adapter.config
    discovery = BotDiscovery(adapter, config, "@TestBot", max_depth=0)

    # Mock adapter methods
    with (
        patch.object(adapter, "send_command", new_callable=AsyncMock) as mock_cmd,
        patch.object(adapter, "get_bot_commands", new_callable=AsyncMock) as mock_cmds,
    ):
        mock_cmd.return_value = BotInteractionResult(
            messages=[{"id": 1, "text": "Welcome!"}],
            buttons=[],
        )
        mock_cmds.return_value = []

        result = await discovery.discover()

    # Should have called /start and /help
    assert mock_cmd.call_count == 2
    calls = [call.args[1] for call in mock_cmd.call_args_list]
    assert "start" in calls
    assert "help" in calls


@pytest.mark.asyncio
async def test_discovery_collects_commands_from_profile(adapter: TelegramAdapter):
    """Test that discovery fetches commands from bot profile."""
    config = adapter.config
    discovery = BotDiscovery(adapter, config, "@TestBot", max_depth=0)

    mock_bot_cmd = MagicMock()
    mock_bot_cmd.command = "translate"
    mock_bot_cmd.description = "Translate text"

    with (
        patch.object(adapter, "send_command", new_callable=AsyncMock) as mock_cmd,
        patch.object(adapter, "get_bot_commands", new_callable=AsyncMock) as mock_cmds,
    ):
        mock_cmd.return_value = BotInteractionResult()
        mock_cmds.return_value = [mock_bot_cmd]

        result = await discovery.discover()

    assert any(c.command == "translate" for c in result.commands)
    assert any(c.description == "Translate text" for c in result.commands)


@pytest.mark.asyncio
async def test_discovery_extracts_buttons(adapter: TelegramAdapter):
    """Test that discovery collects buttons from bot responses."""
    config = adapter.config
    discovery = BotDiscovery(adapter, config, "@TestBot", max_depth=0)

    btn1 = DiscoveredButton(text="Menu", kind=ButtonKind.REPLY, message_id=1)
    btn2 = DiscoveredButton(text="Settings", kind=ButtonKind.INLINE, message_id=1, callback_data="settings")

    with (
        patch.object(adapter, "send_command", new_callable=AsyncMock) as mock_cmd,
        patch.object(adapter, "get_bot_commands", new_callable=AsyncMock) as mock_cmds,
    ):
        mock_cmd.return_value = BotInteractionResult(
            messages=[{"id": 1, "text": "Choose an option:"}],
            buttons=[btn1, btn2],
        )
        mock_cmds.return_value = []

        result = await discovery.discover()

    assert len(result.buttons) >= 2
    button_texts = [b.text for b in result.buttons]
    assert "Menu" in button_texts
    assert "Settings" in button_texts


def test_state_signature_deduplication(adapter: TelegramAdapter):
    """Test that identical responses produce the same state signature."""
    config = adapter.config
    discovery = BotDiscovery(adapter, config, "@TestBot")

    result1 = BotInteractionResult(
        messages=[{"id": 1, "text": "Hello"}],
        buttons=[DiscoveredButton(text="OK", kind=ButtonKind.REPLY)],
    )
    result2 = BotInteractionResult(
        messages=[{"id": 99, "text": "Hello"}],
        buttons=[DiscoveredButton(text="OK", kind=ButtonKind.REPLY)],
    )

    sig1 = discovery._state_signature(result1)
    sig2 = discovery._state_signature(result2)
    assert sig1 == sig2  # Same text + buttons = same signature
