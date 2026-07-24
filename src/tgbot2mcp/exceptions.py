"""Custom exception types for tgbot2mcp."""

from __future__ import annotations


class TgBot2MCPError(Exception):
    """Base exception for all tgbot2mcp errors."""


class BotNotAccessibleError(TgBot2MCPError):
    """Raised when the target bot cannot be reached (doesn't exist, blocked user, etc.)."""

    def __init__(self, bot_username: str, reason: str = "") -> None:
        self.bot_username = bot_username
        self.reason = reason
        super().__init__(f"Bot {bot_username} is not accessible: {reason}" if reason else f"Bot {bot_username} is not accessible.")


class ConversationTimeoutError(TgBot2MCPError):
    """Raised when a bot does not respond within the expected timeout."""

    def __init__(self, bot_username: str, timeout: float) -> None:
        self.bot_username = bot_username
        self.timeout = timeout
        super().__init__(f"Bot {bot_username} did not respond within {timeout}s.")


class BotDiscoveryError(TgBot2MCPError):
    """Raised when bot discovery fails or produces unusable results."""

    def __init__(self, bot_username: str, reason: str = "") -> None:
        self.bot_username = bot_username
        self.reason = reason
        super().__init__(f"Discovery failed for {bot_username}: {reason}" if reason else f"Discovery failed for {bot_username}.")


class SessionError(TgBot2MCPError):
    """Raised when there is a problem with the Telegram session."""


class ButtonNotFoundError(TgBot2MCPError):
    """Raised when a requested button cannot be found on a message."""

    def __init__(self, message_id: int, button_text: str | None = None, button_index: int | None = None) -> None:
        self.message_id = message_id
        self.button_text = button_text
        self.button_index = button_index
        detail = f"text='{button_text}'" if button_text is not None else f"index={button_index}"
        super().__init__(f"Button not found on message {message_id}: {detail}")
