"""
MCP server with universal tools for interacting with Telegram bots.

Exposes these tools via the Model Context Protocol:
- telegram_bot_send
- telegram_bot_command
- telegram_bot_click_button
- telegram_bot_get_messages
- telegram_bot_wait_for_response
- telegram_bot_reset_session
- telegram_bot_get_discovered_actions
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from tgbot2mcp.config import AppConfig
from tgbot2mcp.models import BotInteractionResult, DiscoveredBot
from tgbot2mcp.telegram.adapter import TelegramAdapter
from tgbot2mcp.telegram.discovery import BotDiscovery

logger = logging.getLogger("tgbot2mcp.mcp.server")


def create_mcp_server(
    adapter: TelegramAdapter,
    config: AppConfig,
    bot_username: str,
    discovered_bot: DiscoveredBot | None = None,
) -> FastMCP:
    """
    Create and configure the MCP server with universal + dynamic tools.

    Args:
        adapter: The Telegram adapter for bot interaction.
        config: Application configuration.
        bot_username: The target bot's username (e.g. "@SomeBot").
        discovered_bot: Optional pre-computed discovery result.
    """
    mcp = FastMCP(
        name=f"tgbot2mcp-{bot_username.lstrip('@')}",
        instructions=(
            f"MCP server for interacting with the Telegram bot {bot_username}. "
            "Use the universal tools to send messages, commands, and click buttons. "
            "Use get_discovered_actions to see what the bot can do."
        ),
    )

    # --- Universal Tools ---

    @mcp.tool()
    async def telegram_bot_send(
        message: str,
        files: list[str] | None = None,
        timeout: float | None = None,
    ) -> str:
        """
        Send a text message to the bot and get its response.

        Args:
            message: The text message to send.
            files: Optional list of file paths to send as documents/photos.
            timeout: Maximum seconds to wait for the bot's response (default: 20s).

        Returns:
            JSON string with the bot's response messages and buttons.
        """
        result = await adapter.send_message(bot_username, message, files=files, timeout=timeout)
        return _format_result(result)

    @mcp.tool()
    async def telegram_bot_command(
        command: str,
        arguments: str | None = None,
        timeout: float | None = None,
    ) -> str:
        """
        Send a slash command to the bot and get its response.

        Args:
            command: The command to send (e.g. "start", "help", "settings").
            arguments: Optional arguments to append after the command.
            timeout: Maximum seconds to wait for the bot's response.

        Returns:
            JSON string with the bot's response messages and buttons.
        """
        result = await adapter.send_command(bot_username, command, arguments=arguments, timeout=timeout)
        return _format_result(result)

    @mcp.tool()
    async def telegram_bot_click_button(
        message_id: int,
        button_text: str | None = None,
        button_index: int | None = None,
        timeout: float | None = None,
    ) -> str:
        """
        Click an inline or reply keyboard button on a specific message.

        Provide either button_text or button_index to identify which button to click.

        Args:
            message_id: The Telegram message ID containing the button.
            button_text: The exact text of the button to click.
            button_index: The index of the button (0-based, left-to-right, top-to-bottom).
            timeout: Maximum seconds to wait for the bot's response.

        Returns:
            JSON string with the bot's response messages and buttons.
        """
        result = await adapter.click_button(
            bot_username,
            message_id=message_id,
            button_text=button_text,
            button_index=button_index,
            timeout=timeout,
        )
        return _format_result(result)

    @mcp.tool()
    async def telegram_bot_get_messages(
        limit: int = 10,
    ) -> str:
        """
        Get recent messages from the conversation with the bot.

        Args:
            limit: Maximum number of messages to retrieve (default: 10).

        Returns:
            JSON string with the list of recent messages.
        """
        messages = await adapter.get_messages(bot_username, limit=limit)
        return json.dumps(messages, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def telegram_bot_wait_for_response(
        timeout: float = 30.0,
    ) -> str:
        """
        Wait for the bot to send a message (useful after actions that trigger delayed responses).

        Args:
            timeout: Maximum seconds to wait (default: 30s).

        Returns:
            JSON string with any messages received.
        """
        # Send an empty trigger and just collect the response
        result = await adapter.send_message(bot_username, "", timeout=timeout)
        return _format_result(result)

    @mcp.tool()
    async def telegram_bot_reset_session() -> str:
        """
        Reset the conversation state with the bot.

        Clears any stuck conversation locks and resets the internal state.
        Use this if the bot seems unresponsive or the conversation is stuck.

        Returns:
            Confirmation message.
        """
        adapter.reset_conversation(bot_username)
        return json.dumps({"status": "ok", "message": f"Conversation with {bot_username} has been reset."})

    @mcp.tool()
    async def telegram_bot_get_discovered_actions() -> str:
        """
        Get all discovered actions (commands and buttons) for this bot.

        Returns information about what the bot can do, based on:
        - Registered bot commands (from BotFather)
        - Buttons found in bot responses (inline and reply keyboards)
        - Commands parsed from /start and /help responses

        Returns:
            JSON string with discovered commands, buttons, and state information.
        """
        if discovered_bot:
            return _format_discovered_bot(discovered_bot)

        # Run discovery on the fly
        discovery = BotDiscovery(adapter, config, bot_username, max_depth=1)
        result = await discovery.discover()
        return _format_discovered_bot(result)

    # --- Dynamic tools from discovery ---

    if discovered_bot:
        _register_dynamic_tools(mcp, adapter, bot_username, discovered_bot)

    return mcp


def _register_dynamic_tools(
    mcp: FastMCP,
    adapter: TelegramAdapter,
    bot_username: str,
    discovered: DiscoveredBot,
) -> None:
    """Register best-effort dedicated MCP tools from discovered bot actions."""

    # Create a dedicated tool for each discovered command
    for cmd in discovered.commands:
        cmd_name = cmd.command
        cmd_desc = cmd.description or f"Send /{cmd_name} to the bot"

        # Create a closure for each command
        def make_command_tool(command_name: str, description: str):
            async def tool_func(arguments: str | None = None, timeout: float | None = None) -> str:
                result = await adapter.send_command(
                    bot_username, command_name, arguments=arguments, timeout=timeout
                )
                return _format_result(result)
            tool_func.__name__ = f"telegram_bot_cmd_{command_name}"
            tool_func.__doc__ = f"{description}\n\nArgs:\n    arguments: Optional arguments for the command.\n    timeout: Max seconds to wait for response."
            return tool_func

        tool_func = make_command_tool(cmd_name, cmd_desc)
        mcp.tool(name=f"telegram_bot_cmd_{cmd_name}", description=cmd_desc)(tool_func)

    # Create dedicated tools for frequently seen buttons
    seen_button_texts: set[str] = set()
    for btn in discovered.buttons:
        if btn.text in seen_button_texts:
            continue
        seen_button_texts.add(btn.text)

        # Sanitize button text for tool name
        safe_name = _sanitize_tool_name(btn.text)
        if not safe_name:
            continue

        def make_button_tool(button_text: str):
            async def tool_func(message_id: int | None = None, timeout: float | None = None) -> str:
                result = await adapter.click_button(
                    bot_username,
                    message_id=message_id or 0,
                    button_text=button_text,
                    timeout=timeout,
                )
                return _format_result(result)
            tool_func.__name__ = f"telegram_bot_btn_{safe_name}"
            tool_func.__doc__ = f"Click the '{button_text}' button.\n\nArgs:\n    message_id: The message ID containing the button.\n    timeout: Max seconds to wait for response."
            return tool_func

        tool_func = make_button_tool(btn.text)
        mcp.tool(
            name=f"telegram_bot_btn_{safe_name}",
            description=f"Click the '{btn.text}' button on the bot.",
        )(tool_func)


def _format_result(result: BotInteractionResult) -> str:
    """Format a BotInteractionResult as a JSON string for MCP response."""
    data: dict[str, Any] = {}

    if result.timed_out:
        data["status"] = "timeout"
        data["message"] = "The bot did not respond within the timeout period."
    elif result.error:
        data["status"] = "error"
        data["message"] = result.error
    else:
        data["status"] = "ok"
        data["messages"] = result.messages
        data["buttons"] = [b.model_dump() for b in result.buttons]

    return json.dumps(data, ensure_ascii=False, indent=2)


def _format_discovered_bot(bot: DiscoveredBot) -> str:
    """Format a DiscoveredBot as a readable JSON string."""
    data = {
        "username": bot.username,
        "commands": [
            {"command": f"/{c.command}", "description": c.description, "source": c.source}
            for c in bot.commands
        ],
        "buttons": [
            {"text": b.text, "kind": b.kind, "message_id": b.message_id}
            for b in bot.buttons
        ],
        "start_response": bot.start_text[:500] if bot.start_text else "",
        "help_response": bot.help_text[:500] if bot.help_text else "",
        "total_states": len(bot.states),
        "total_transitions": len(bot.transitions),
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def _sanitize_tool_name(text: str) -> str:
    """Convert button text to a valid Python function name."""
    import re

    # Remove non-alphanumeric characters, replace spaces with underscores
    name = re.sub(r"[^a-zA-Z0-9_\s]", "", text)
    name = re.sub(r"\s+", "_", name.strip())
    name = name.lower()

    # Ensure it starts with a letter
    if name and not name[0].isalpha():
        name = "btn_" + name

    # Limit length
    return name[:50] if name else ""
