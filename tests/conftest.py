"""Test fixtures for tgbot2mcp."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tgbot2mcp.config import AppConfig
from tgbot2mcp.telegram.adapter import TelegramAdapter


@pytest.fixture
def config(tmp_path: Path) -> AppConfig:
    """Create a test configuration with a temporary session directory."""
    return AppConfig(
        api_id=12345,
        api_hash="test_api_hash_0123456789",
        session_dir=tmp_path / "sessions",
        default_timeout=5.0,
        wait_consecutive=0.5,
        global_action_delay=0.0,  # No delay in tests
        log_level="DEBUG",
    )


@pytest.fixture
def mock_telethon_client() -> MagicMock:
    """Create a mock Telethon TelegramClient."""
    client = MagicMock()
    client.is_connected = AsyncMock(return_value=True)
    client.get_me = AsyncMock()
    client.get_entity = AsyncMock()
    client.send_message = AsyncMock()
    client.send_file = AsyncMock()
    client.get_messages = AsyncMock(return_value=[])
    client.add_event_handler = MagicMock()
    client.remove_event_handler = MagicMock()
    return client


@pytest.fixture
def adapter(config: AppConfig, mock_telethon_client: MagicMock) -> TelegramAdapter:
    """Create a TelegramAdapter with a mocked Telethon client."""
    return TelegramAdapter(mock_telethon_client, config)
