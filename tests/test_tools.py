"""Tests for MCP server tools."""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tgbot2mcp.config import AppConfig
from tgbot2mcp.models import BotInteractionResult, ButtonKind, DiscoveredBot, DiscoveredButton, DiscoveredCommand
from tgbot2mcp.mcp_server.server import (
    create_mcp_server,
    _format_result,
    _format_discovered_bot,
    _sanitize_tool_name,
)


def test_format_result_ok():
    """Test formatting a successful interaction result."""
    result = BotInteractionResult(
        messages=[{"id": 1, "text": "Hello!"}],
        buttons=[DiscoveredButton(text="OK", kind=ButtonKind.REPLY)],
    )
    formatted = _format_result(result)
    data = json.loads(formatted)
    assert data["status"] == "ok"
    assert len(data["messages"]) == 1
    assert len(data["buttons"]) == 1


def test_format_result_timeout():
    """Test formatting a timeout result."""
    result = BotInteractionResult(timed_out=True)
    formatted = _format_result(result)
    data = json.loads(formatted)
    assert data["status"] == "timeout"


def test_format_result_error():
    """Test formatting an error result."""
    result = BotInteractionResult(error="Button not found")
    formatted = _format_result(result)
    data = json.loads(formatted)
    assert data["status"] == "error"
    assert "Button not found" in data["message"]


def test_format_discovered_bot():
    """Test formatting a discovered bot result."""
    bot = DiscoveredBot(
        username="@TestBot",
        commands=[DiscoveredCommand(command="start", description="Start the bot")],
        buttons=[DiscoveredButton(text="Menu", kind=ButtonKind.REPLY)],
        start_text="Welcome!",
        help_text="Help text here",
    )
    formatted = _format_discovered_bot(bot)
    data = json.loads(formatted)
    assert data["username"] == "@TestBot"
    assert len(data["commands"]) == 1
    assert data["commands"][0]["command"] == "/start"
    assert len(data["buttons"]) == 1


def test_sanitize_tool_name():
    """Test converting button text to valid Python function names."""
    assert _sanitize_tool_name("Click Me") == "click_me"
    assert _sanitize_tool_name("Settings") == "settings"
    assert _sanitize_tool_name("123 Start") == "btn_123_start"
    assert _sanitize_tool_name("OK!") == "ok"
    assert _sanitize_tool_name("") == ""


def test_create_mcp_server_returns_fastmcp():
    """Test that create_mcp_server returns a FastMCP instance."""
    from mcp.server.fastmcp import FastMCP

    mock_adapter = MagicMock()
    config = AppConfig(api_id=1, api_hash="test")

    mcp = create_mcp_server(mock_adapter, config, "@TestBot")
    assert isinstance(mcp, FastMCP)
    assert "TestBot" in mcp.name


def test_create_mcp_server_with_discovered_bot():
    """Test that dynamic tools are registered when discovery data is provided."""
    from mcp.server.fastmcp import FastMCP

    mock_adapter = MagicMock()
    config = AppConfig(api_id=1, api_hash="test")

    discovered = DiscoveredBot(
        username="@TestBot",
        commands=[
            DiscoveredCommand(command="start", description="Start"),
            DiscoveredCommand(command="help", description="Help"),
        ],
        buttons=[
            DiscoveredButton(text="Menu", kind=ButtonKind.REPLY),
        ],
    )

    mcp = create_mcp_server(mock_adapter, config, "@TestBot", discovered_bot=discovered)
    assert isinstance(mcp, FastMCP)
