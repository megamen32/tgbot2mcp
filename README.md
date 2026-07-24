# tgbot2mcp

Universal Telegram Bot to MCP adapter — wrap **any** Telegram bot into a ready-to-use [Model Context Protocol](https://modelcontextprotocol.io/) server via MTProto user sessions.

## How It Works

```
Your Telegram Account (MTProto) → Telethon → tgbot2mcp → MCP Server → AI Clients (Claude, etc.)
                                                      ↑
                                                Bot Discovery
                                            (commands, keyboards,
                                             /start, /help, DFS crawl)
```

1. You authenticate with Telegram using your phone number (like a normal Telegram client)
2. You specify a bot username (e.g. `@SomeBot`)
3. tgbot2mcp auto-discovers the bot's capabilities:
   - Registered commands (from BotFather)
   - `/start` and `/help` responses
   - Inline and reply keyboard buttons
   - Full state graph via DFS traversal (inspired by [BotFuzzer](https://github.com/seniorsolt/BotFuzzer))
4. It exposes everything as MCP tools that AI clients can use

## Architecture

Built on proven open-source foundations:

- **[TgTestKit](https://github.com/elebur/tgtestkit)** — Telethon-based interaction layer (messages, buttons, edited messages, timeouts)
- **[BotFuzzer](https://github.com/seniorsolt/BotFuzzer)** — DFS bot crawling and state graph discovery (adapted from Pyrogram to Telethon)
- **MCP Python SDK** — Standard Model Context Protocol server

## Quick Start

### Prerequisites

- Python 3.11+
- Telegram API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)

### Installation

```bash
pip install -e .
```

### 1. Login to Telegram

```bash
tgbot2mcp login
```

This will prompt for your phone number and verification code. The session is persisted to `~/.tgbot2mcp/sessions/`.

### 2. Inspect a Bot

```bash
tgbot2mcp inspect @SomeBot
```

This runs discovery and shows all commands, buttons, and states found.

### 3. Start MCP Server

```bash
# stdio transport (for Claude Desktop, etc.)
tgbot2mcp serve @SomeBot

# HTTP transport
tgbot2mcp serve @SomeBot --transport http --port 8080

# Skip discovery (universal tools only)
tgbot2mcp serve @SomeBot --no-discover
```

### 4. Generate Standalone Server

```bash
tgbot2mcp generate @SomeBot --output ./generated
```

Creates a self-contained Python MCP server file with the discovered commands hardcoded as dedicated tools.

## MCP Tools

### Universal Tools (always available)

| Tool | Description |
|------|-------------|
| `telegram_bot_send` | Send a text message and get the response |
| `telegram_bot_command` | Send a slash command (`/command args`) |
| `telegram_bot_click_button` | Click an inline/reply keyboard button |
| `telegram_bot_get_messages` | Get recent messages from the chat |
| `telegram_bot_wait_for_response` | Wait for a delayed bot response |
| `telegram_bot_reset_session` | Reset conversation state |
| `telegram_bot_get_discovered_actions` | List all discovered commands/buttons |

### Dynamic Tools (from discovery)

After discovery, dedicated tools are auto-generated:

- `telegram_bot_cmd_{command}` — One tool per discovered slash command
- `telegram_bot_btn_{label}` — One tool per discovered button

## Configuration

Config file: `~/.tgbot2mcp/config.yaml`

```yaml
api_id: 12345
api_hash: "your_api_hash"
session_dir: ~/.tgbot2mcp/sessions
default_timeout: 20.0
wait_consecutive: 2.0
global_action_delay: 0.8
log_level: INFO
discovery_max_depth: 5
discovery_max_repeats: 1
```

Environment variables override config file values:
- `TG_API_ID` / `TELEGRAM_API_ID`
- `TG_API_HASH` / `TELEGRAM_API_HASH`

## Claude Desktop Integration

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "telegram-bot": {
      "command": "tgbot2mcp",
      "args": ["serve", "@YourBotName"],
      "env": {
        "TG_API_ID": "YOUR_API_ID",
        "TG_API_HASH": "YOUR_API_HASH"
      }
    }
  }
}
```

See `examples/claude_desktop_config.json` for a complete example.

## Docker

```bash
# Interactive login
docker compose run tgbot2mcp login

# Start MCP server
docker compose run tgbot2mcp serve @SomeBot
```

## Security Notes

- **Never share your Telegram session files** (`~/.tgbot2mcp/sessions/`)
- Session files give full access to your Telegram account
- The target bot's Bot API token is **never** requested or stored
- Session files are created with `0600` permissions

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with debug logging
tgbot2mcp --log-level DEBUG serve @SomeBot
```

## License

MIT
