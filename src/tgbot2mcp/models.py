"""Shared data models for tgbot2mcp."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ButtonKind(str, Enum):
    INLINE = "inline"
    REPLY = "reply"


class DiscoveredButton(BaseModel):
    """A button discovered from bot responses."""

    text: str
    kind: ButtonKind
    message_id: int | None = None
    callback_data: str | None = None
    url: str | None = None


class DiscoveredCommand(BaseModel):
    """A slash command discovered from bot profile or responses."""

    command: str  # e.g. "start" (without /)
    description: str = ""
    source: str = "profile"  # "profile", "start_text", "help_text"


class DiscoveredState(BaseModel):
    """A state in the bot's interaction graph."""

    state_id: int
    text: str = ""
    media_path: str | None = None
    buttons: list[DiscoveredButton] = Field(default_factory=list)
    outgoing_actions: list[str] = Field(default_factory=list)  # descriptions of actions
    status: str = "ok"  # "ok", "timeout", "error"


class DiscoveredBot(BaseModel):
    """Complete discovery result for a Telegram bot."""

    username: str
    commands: list[DiscoveredCommand] = Field(default_factory=list)
    buttons: list[DiscoveredButton] = Field(default_factory=list)
    states: list[DiscoveredState] = Field(default_factory=list)
    start_text: str = ""
    help_text: str = ""
    description: str = ""

    # Graph edges: (from_state_id, action_description, to_state_id)
    transitions: list[tuple[int, str, int]] = Field(default_factory=list)


class BotInteractionResult(BaseModel):
    """Result of a single interaction with a bot."""

    messages: list[dict[str, Any]] = Field(default_factory=list)
    buttons: list[DiscoveredButton] = Field(default_factory=list)
    timed_out: bool = False
    error: str | None = None
