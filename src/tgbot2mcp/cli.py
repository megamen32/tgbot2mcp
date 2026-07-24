"""
CLI entry point for tgbot2mcp.

Commands:
  tgbot2mcp login                    — Authenticate with Telegram
  tgbot2mcp serve @botname           — Start MCP server for a bot
  tgbot2mcp inspect @botname         — Discover and display bot capabilities
  tgbot2mcp generate @botname        — Generate standalone MCP server code
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import click

from tgbot2mcp.config import AppConfig, ensure_dirs, load_config, save_config
from tgbot2mcp.utils import setup_logging

logger = logging.getLogger("tgbot2mcp.cli")


@click.group()
@click.option("--config", "config_path", type=click.Path(exists=False), default=None,
              help="Path to config YAML file.")
@click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
              default=None, help="Override log level.")
@click.pass_context
def cli(ctx: click.Context, config_path: str | None, log_level: str | None) -> None:
    """tgbot2mcp — Wrap any Telegram bot into a ready-to-use MCP server."""
    ctx.ensure_object(dict)
    config = load_config(Path(config_path) if config_path else None)
    if log_level:
        config.log_level = log_level
    setup_logging(config.log_level)
    ctx.obj["config"] = config


@cli.command()
@click.pass_context
def login(ctx: click.Context) -> None:
    """Authenticate with Telegram (phone number + verification code).

    Creates a persistent session that will be reused by other commands.
    You need a Telegram API ID and hash from https://my.telegram.org/apps.
    """
    config: AppConfig = ctx.obj["config"]
    ensure_dirs(config)

    if not config.api_id or not config.api_hash:
        click.echo("Error: api_id and api_hash are required.")
        click.echo("Set them in ~/.tgbot2mcp/config.yaml or via TG_API_ID / TG_API_HASH env vars.")
        click.echo("Get them from https://my.telegram.org/apps")
        sys.exit(1)

    from tgbot2mcp.telegram.client import TelegramSessionManager

    async def _login() -> None:
        manager = TelegramSessionManager(config)
        user = await manager.login()
        click.echo(f"Successfully logged in as {user.first_name} (@{user.username})")
        await manager.disconnect()

    asyncio.run(_login())


@cli.command()
@click.argument("bot_username")
@click.option("--transport", type=click.Choice(["stdio", "http"]), default="stdio",
              help="MCP transport type.")
@click.option("--host", default="127.0.0.1", help="HTTP transport host.")
@click.option("--port", default=8080, type=int, help="HTTP transport port.")
@click.option("--discover/--no-discover", default=True,
              help="Run bot discovery before starting the server.")
@click.option("--max-depth", default=3, type=int,
              help="Max depth for bot discovery (if enabled).")
@click.pass_context
def serve(
    ctx: click.Context,
    bot_username: str,
    transport: str,
    host: str,
    port: int,
    discover: bool,
    max_depth: int,
) -> None:
    """Start an MCP server for the specified Telegram bot.

    BOT_USERNAME is the bot's username (e.g. @SomeBot or SomeBot).
    """
    config: AppConfig = ctx.obj["config"]
    ensure_dirs(config)
    bot_username = _normalize_bot_username(bot_username)

    from tgbot2mcp.telegram.client import TelegramSessionManager
    from tgbot2mcp.telegram.adapter import TelegramAdapter
    from tgbot2mcp.telegram.discovery import BotDiscovery
    from tgbot2mcp.mcp_server.server import create_mcp_server

    async def _serve() -> None:
        # Connect to Telegram
        session = TelegramSessionManager(config)
        await session.connect()

        adapter = TelegramAdapter(session.client, config)
        discovered_bot = None

        # Optionally run discovery to generate dedicated tools
        if discover:
            click.echo(f"Discovering capabilities of {bot_username}...")
            discovery = BotDiscovery(adapter, config, bot_username, max_depth=max_depth)
            discovered_bot = await discovery.discover()
            click.echo(
                f"Discovered: {len(discovered_bot.commands)} commands, "
                f"{len(discovered_bot.buttons)} buttons, "
                f"{len(discovered_bot.states)} states"
            )

        # Create and run MCP server
        mcp = create_mcp_server(adapter, config, bot_username, discovered_bot)
        click.echo(f"Starting MCP server for {bot_username} via {transport}...")

        from tgbot2mcp.mcp_server.transport import run_mcp_server
        await run_mcp_server(mcp, transport=transport, host=host, port=port)

    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        click.echo("\nShutting down.")


@cli.command()
@click.argument("bot_username")
@click.option("--max-depth", default=2, type=int,
              help="Max depth for discovery (default: 2).")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save discovery result to JSON file.")
@click.pass_context
def inspect(
    ctx: click.Context,
    bot_username: str,
    max_depth: int,
    output: str | None,
) -> None:
    """Discover and display a Telegram bot's capabilities.

    BOT_USERNAME is the bot's username (e.g. @SomeBot or SomeBot).
    """
    config: AppConfig = ctx.obj["config"]
    ensure_dirs(config)
    bot_username = _normalize_bot_username(bot_username)

    from tgbot2mcp.telegram.client import TelegramSessionManager
    from tgbot2mcp.telegram.adapter import TelegramAdapter
    from tgbot2mcp.telegram.discovery import BotDiscovery

    async def _inspect() -> None:
        session = TelegramSessionManager(config)
        await session.connect()

        adapter = TelegramAdapter(session.client, config)
        discovery = BotDiscovery(adapter, config, bot_username, max_depth=max_depth)

        click.echo(f"Inspecting {bot_username}...")
        result = await discovery.discover()

        # Display results
        click.echo(f"\n{'='*60}")
        click.echo(f"Bot: {result.username}")
        click.echo(f"{'='*60}")

        if result.commands:
            click.echo(f"\nCommands ({len(result.commands)}):")
            for cmd in result.commands:
                desc = f" - {cmd.description}" if cmd.description else ""
                click.echo(f"  /{cmd.command}{desc} (from {cmd.source})")

        if result.buttons:
            click.echo(f"\nButtons ({len(result.buttons)}):")
            for btn in result.buttons:
                click.echo(f"  [{btn.kind.value}] {btn.text}")

        click.echo(f"\nStates discovered: {len(result.states)}")
        click.echo(f"Transitions: {len(result.transitions)}")

        if result.start_text:
            click.echo(f"\n/start response:\n  {result.start_text[:300]}...")
        if result.help_text:
            click.echo(f"\n/help response:\n  {result.help_text[:300]}...")

        # Save to file if requested
        if output:
            output_path = Path(output)
            output_path.write_text(
                result.model_dump_json(indent=2),
                encoding="utf-8",
            )
            click.echo(f"\nDiscovery result saved to {output_path}")

        await session.disconnect()

    asyncio.run(_inspect())


@cli.command()
@click.argument("bot_username")
@click.option("--output", "-o", type=click.Path(), required=True,
              help="Output directory for generated server code.")
@click.pass_context
def generate(
    ctx: click.Context,
    bot_username: str,
    output: str,
) -> None:
    """Generate a standalone MCP server from a bot's discovered capabilities.

    BOT_USERNAME is the bot's username (e.g. @SomeBot or SomeBot).

    Generates a self-contained Python MCP server that can run without tgbot2mcp.
    """
    config: AppConfig = ctx.obj["config"]
    ensure_dirs(config)
    bot_username = _normalize_bot_username(bot_username)
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    from tgbot2mcp.telegram.client import TelegramSessionManager
    from tgbot2mcp.telegram.adapter import TelegramAdapter
    from tgbot2mcp.telegram.discovery import BotDiscovery

    async def _generate() -> None:
        session = TelegramSessionManager(config)
        await session.connect()

        adapter = TelegramAdapter(session.client, config)
        discovery = BotDiscovery(adapter, config, bot_username, max_depth=2)

        click.echo(f"Discovering {bot_username} for code generation...")
        result = await discovery.discover()

        # Generate standalone server code
        code = _generate_standalone_server(bot_username, result)
        output_file = output_dir / f"mcp_server_{bot_username.lstrip('@')}.py"
        output_file.write_text(code, encoding="utf-8")

        click.echo(f"Generated standalone MCP server: {output_file}")
        click.echo(f"  Commands: {len(result.commands)}")
        click.echo(f"  Buttons: {len(result.buttons)}")
        click.echo(f"\nRun with: python {output_file}")

        await session.disconnect()

    asyncio.run(_generate())


def _normalize_bot_username(username: str) -> str:
    """Ensure the username starts with @."""
    username = username.strip()
    if not username.startswith("@"):
        username = f"@{username}"
    return username


def _generate_standalone_server(bot_username: str, discovered) -> str:
    """Generate standalone Python MCP server code from discovery results."""
    commands_json = json.dumps(
        [{"command": c.command, "description": c.description} for c in discovered.commands],
        indent=4,
    )
    buttons_json = json.dumps(
        [{"text": b.text, "kind": b.kind} for b in discovered.buttons],
        indent=4,
    )

    return f'''#!/usr/bin/env python3
"""
Standalone MCP server for Telegram bot {bot_username}.
Auto-generated by tgbot2mcp.

Discovered commands: {len(discovered.commands)}
Discovered buttons: {len(discovered.buttons)}
States: {len(discovered.states)}

Run: python {bot_username.lstrip("@")}_mcp_server.py
"""

import json
import asyncio
from mcp.server.fastmcp import FastMCP

# Discovery data
BOT_USERNAME = "{bot_username}"
COMMANDS = {commands_json}

BUTTONS = {buttons_json}

mcp = FastMCP(
    name="tg-{bot_username.lstrip("@")}",
    instructions="MCP server for Telegram bot {bot_username}. "
    "Discovered {{len(COMMANDS)}} commands and {{len(BUTTONS)}} buttons.",
)


# --- Universal tools (always available) ---

@mcp.tool()
async def send_message(message: str, timeout: float = 20.0) -> str:
    """Send a text message to the bot and get its response."""
    # This requires tgbot2mcp runtime — see full implementation
    return json.dumps({{"status": "info", "message": "Requires tgbot2mcp runtime. Use the full tgbot2mcp serve command."}})


@mcp.tool()
async def send_command(command: str, arguments: str | None = None, timeout: float = 20.0) -> str:
    """Send a slash command to the bot."""
    return json.dumps({{"status": "info", "message": "Requires tgbot2mcp runtime."}})


@mcp.tool()
async def get_discovered_actions() -> str:
    """List all discovered commands and buttons for this bot."""
    return json.dumps({{
        "commands": COMMANDS,
        "buttons": BUTTONS,
    }}, indent=2)


if __name__ == "__main__":
    mcp.run()
'''


if __name__ == "__main__":
    cli()
