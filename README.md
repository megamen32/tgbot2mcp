<p align="center">
  <img src="assets/hero.svg" alt="tgbot2mcp — Turn any Telegram bot into an MCP server" width="100%"/>
</p>

<p align="center">
  <strong>English</strong> |
  <a href="#ru">Русский</a> |
  <a href="#zh">中文</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/tgbot2mcp/"><img alt="PyPI" src="https://img.shields.io/pypi/v/tgbot2mcp?color=blue"/></a>
  <a href="https://github.com/megamen32/tgbot2mcp"><img alt="GitHub" src="https://img.shields.io/github/stars/megamen32/tgbot2mcp?style=social"/></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-blue"/>
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green"/>
</p>

---

# tgbot2mcp

**Turn any Telegram bot into a ready-to-use [MCP server](https://modelcontextprotocol.io/) in one command.**  
No bot token required. Works with any existing Telegram bot through your user account.

> **What is this?** An open-source Python adapter that connects to Telegram as a user (via MTProto), auto-discovers a target bot's capabilities, and exposes them as MCP tools — so AI agents (Claude, GPT, Gemini) can interact with any Telegram bot.

---

## Quick Start

One command to set everything up:

```bash
uvx tgbot2mcp setup @SomeBot
```

This will:
1. Ask for your Telegram API credentials (from [my.telegram.org/apps](https://my.telegram.org/apps))
2. Log in to Telegram
3. Verify the bot is reachable
4. Auto-configure your MCP client (Claude Desktop / Cursor / VS Code)

**Done.** Your AI agent can now talk to the bot.

---

## Installation

<details open>
<summary><b>uvx (recommended — no install needed)</b></summary>

```bash
uvx tgbot2mcp setup @SomeBot
uvx tgbot2mcp serve @SomeBot
```

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

</details>

<details>
<summary><b>pipx (permanent install)</b></summary>

```bash
pipx install tgbot2mcp
tgbot2mcp setup @SomeBot
```

</details>

<details>
<summary><b>Docker (HTTP/self-hosted)</b></summary>

```bash
docker run --rm -it \
  -p 8080:8080 \
  -v tgbot2mcp-data:/data \
  -e TG_API_ID=123456 \
  -e TG_API_HASH=... \
  ghcr.io/megamen32/tgbot2mcp \
  serve @SomeBot --transport http --host 0.0.0.0 --port 8080
```

</details>

<details>
<summary><b>From source (development)</b></summary>

```bash
git clone https://github.com/megamen32/tgbot2mcp.git
cd tgbot2mcp
pip install -e ".[dev]"
tgbot2mcp setup @SomeBot
```

</details>

---

## How It Works

```
┌─────────────┐     MTProto      ┌─────────────┐      MCP       ┌─────────────┐
│  Telegram    │ ───────────────▶ │  tgbot2mcp  │ ─────────────▶ │  AI Agent   │
│  Bot (@bot)  │ ◀─────────────── │             │ ◀───────────── │ (Claude etc)│
└─────────────┘   Bot responses   │  • Discover │   Tool calls   └─────────────┘
                                   │  • Interact │
                                   │  • Expose   │
                                   └─────────────┘
```

1. **Authenticate** — Log in with your Telegram account (phone number)
2. **Discover** — Crawl the bot: `/start`, `/help`, buttons, full state graph via DFS
3. **Expose** — Every action becomes an MCP tool
4. **Interact** — AI agents send messages, click buttons, navigate states

---

## MCP Tools

### Universal (always available)

| Tool | What it does |
|------|-------------|
| `send` | Send text or `/command` and get the response |
| `click` | Click an inline or reply-keyboard button |
| `read` | Read recent messages from the conversation |
| `wait` | Wait for a delayed bot response |
| `reset` | Reset conversation state |
| `discover` | List all auto-discovered commands and buttons |

### Dynamic (auto-generated from bot discovery)

- **`cmd_{name}`** — one tool per slash command (`cmd_start`, `cmd_help`, etc.)
- **`btn_{label}`** — one tool per button found in bot responses

---

## MCP Client Configuration

### Claude Desktop

```json
{
  "mcpServers": {
    "telegram-bot": {
      "command": "uvx",
      "args": ["tgbot2mcp", "serve", "@YourBot"],
      "env": {
        "TG_API_ID": "YOUR_API_ID",
        "TG_API_HASH": "YOUR_API_HASH"
      }
    }
  }
}
```

> **Tip:** `tgbot2mcp setup` writes this config for you automatically.

### Cursor / VS Code

Same format — saved to `~/.cursor/mcp.json` or `~/.vscode/mcp.json` by `setup`.

---

## Commands

| Command | Description |
|---------|-------------|
| `tgbot2mcp setup @Bot` | Full onboarding wizard (credentials + login + MCP config) |
| `tgbot2mcp login` | Telegram authentication only |
| `tgbot2mcp serve @Bot` | Start MCP server (stdio or HTTP) |
| `tgbot2mcp inspect @Bot` | Show discovered bot capabilities |
| `tgbot2mcp generate @Bot` | Generate standalone MCP server file |

### Serve options

```bash
# stdio (default — for Claude Desktop, Cursor)
tgbot2mcp serve @SomeBot

# HTTP transport (for remote/self-hosted)
tgbot2mcp serve @SomeBot --transport http --port 8080

# Skip discovery (universal tools only, faster startup)
tgbot2mcp serve @SomeBot --no-discover
```

---

## Configuration

Config: `~/.tgbot2mcp/config.yaml`

```yaml
api_id: 12345
api_hash: "your_api_hash"
session_dir: ~/.tgbot2mcp/sessions
default_timeout: 20.0
discovery_max_depth: 5
```

Environment variables (override config):
- `TG_API_ID` / `TELEGRAM_API_ID`
- `TG_API_HASH` / `TELEGRAM_API_HASH`

---

## FAQ

<details>
<summary><b>Do I need the bot's API token?</b></summary>
No. tgbot2mcp uses your Telegram user session (MTProto). Works with any bot, even ones you don't own.
</details>

<details>
<summary><b>Is this safe?</b></summary>
Session files (<code>~/.tgbot2mcp/sessions/</code>) give full access to your Telegram account. Never share them. Created with <code>0600</code> permissions.
</details>

<details>
<summary><b>Which AI clients work?</b></summary>
Any MCP client: Claude Desktop, Cursor, Continue (VS Code), Cline, and others. Supports stdio and HTTP transports.
</details>

<details>
<summary><b>Can I use it with any bot?</b></summary>
Yes. Any public Telegram bot that accepts messages will work.
</details>

---

## Architecture

| Component | Source | Role |
|-----------|--------|------|
| Discovery | [BotFuzzer](https://github.com/seniorsolt/BotFuzzer) | DFS crawling, state graph |
| Interaction | [TgTestKit](https://github.com/elebur/tgtestkit) | Messages, buttons, edited messages |
| MCP | [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Protocol implementation |
| Transport | Telethon (MTProto) | User-session Telegram access |

---

## License

MIT

---

<a id="ru"></a>
## 🇷🇺 Русский

**tgbot2mcp** — превращает любого Telegram-бота в [MCP-сервер](https://modelcontextprotocol.io/) одной командой.  
Токен бота не нужен — работает через ваш аккаунт.

```bash
uvx tgbot2mcp setup @SomeBot
```

Мастер настройки сам запросит API-ключи, выполнит авторизацию, проверит бота и настроит MCP-клиент (Claude / Cursor / VS Code).

**Ручной запуск:**

```bash
uvx tgbot2mcp login
uvx tgbot2mcp serve @SomeBot
```

Нужен [uv](https://docs.astral.sh/uv/) и API-ключи с [my.telegram.org/apps](https://my.telegram.org/apps).

---

<a id="zh"></a>
## 🇨🇳 中文

**tgbot2mcp** — 一条命令将任何 Telegram 机器人变为 [MCP 服务器](https://modelcontextprotocol.io/)。  
无需机器人 Token，通过您的用户账户运行。

```bash
uvx tgbot2mcp setup @SomeBot
```

设置向导会自动请求 API 密钥、完成登录、验证机器人并配置 MCP 客户端（Claude / Cursor / VS Code）。

**手动运行：**

```bash
uvx tgbot2mcp login
uvx tgbot2mcp serve @SomeBot
```

需要 [uv](https://docs.astral.sh/uv/) 和 [my.telegram.org/apps](https://my.telegram.org/apps) 的 API 密钥。

---

<p align="center">
  <sub>Built with Telethon · MCP Python SDK · Inspired by BotFuzzer & TgTestKit</sub>
</p>
