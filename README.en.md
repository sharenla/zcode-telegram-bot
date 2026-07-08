# ZCode Telegram Bot

[中文](README.md) | **English**

Bring Zhipu ZCode Agent to Telegram — chat with ZCode remotely and let it work on your codebase.

**Key feature: two-way sync with the local TUI/desktop app on the same session.** Converse with ZCode from your phone while sharing full context with the desktop client.

```
                    ┌─ Desktop App ─┐
                    │   ZCode TUI   │
                    └──────┬────────┘
                           │ each spawns its own
        ┌── shared SQLite ─┼──────────┐
        │  (~/.zcode/...)  │          │
        │           ┌──────┴────────┐ │
        │           │  app-server    │ │
Telegram ─► Bot ───►│  (JSON-RPC)   │◄┘
  user        │      └───────────────┘
              │ session/send (streaming)
              │ session/events (poll TUI activity)
              ▼
        pushes reply to user
```

Each user binds to a ZCode `sessionId` for continuous multi-turn context.
The bot and the desktop app each hold their own app-server process, sharing the same SQLite.
Two-way sync is achieved via `session/send` (streaming) and `session/events` (polling).

## Architecture

| Layer | File | Responsibility |
|---|---|---|
| **Protocol** | `src/app_server_client.py` | JSON-RPC/stdio client for `zcode app-server` |
| **Sync** | `src/session_sync.py` | send streaming + TUI activity poll coordinator |
| **Session** | `src/session_store.py` | per-user sessionId + poll watermark persistence |
| **Bot** | `src/bot.py` | Telegram send/receive + streaming push + commands |
| **Fallback** | `src/zcode_client.py` | `--prompt --json` mode (`USE_APP_SERVER=0`) |

> 📐 A detailed architecture diagram is planned. See `docs/` (placeholder).

## Prerequisites

1. **ZCode desktop app installed and signed in** — `/Applications/ZCode.app`
2. **`~/.zcode/cli/config.json` configured** (provider + model.main)
3. **Python 3.11+** and [uv](https://docs.astral.sh/uv/) (or pip)

## Quick Start

```bash
cd zcode-telegram-bot
uv venv --python 3.11 .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# Edit .env: TELEGRAM_BOT_TOKEN / ALLOWED_USERS / APPROVED_DIRECTORY

.venv/bin/python src/main.py
```

## Commands

| Command | Action |
|---|---|
| Plain text | ZCode executes → streams the result back |
| `/new` | Start a fresh session |
| `/sessions` | List local TUI sessions, pick one to **link** (two-way sync) |
| `/sync <sessionId>` | Link a specific session directly |
| `/id` | Show your Telegram user id |
| `/start` | Help |

## How Two-Way Sync Works

- **bot → session**: the bot sends via `session/send` and receives the assistant reply through `session/event` notifications, **streaming** it to the Telegram user in real time.
- **TUI → bot**: the bot polls `session/events?afterSeq=N` in the background to discover new activity by the TUI in the same session (user questions / assistant replies / tool calls), and proactively pushes a notification.

**Architectural constraint**: app-server is a single-client-per-process model. The bot and the TUI each spawn their own app-server, with no cross-process real-time event bus. Therefore the data layer (shared SQLite) is inherently in sync, while the TUI→bot direction relies on polling (~1.5s) for near-real-time.

## Group Chat Support

- All members **share one ZCode session** (context shared) — keyed by chat_id
- Triggers on **@bot mention** or **replying to the bot's message** (not every message)
- **Queueing**: if A's task is running, B's message queues up and runs after A finishes
- Allowlist by group: any member of an allowlisted group can use the bot
- Permission approval: in `build` mode, every write/command requires a Telegram button approval

## Configuration

| Env var | Default | Description |
|---|---|---|
| `USE_APP_SERVER` | `1` | `1`=app-server mode; `0`=--prompt fallback |
| `WORKSPACE_PATH` | = `APPROVED_DIRECTORY` | session workspace |
| `POLL_INTERVAL` | `1.5` | TUI→bot poll interval (seconds) |
| `APP_SERVER_TURN_TIMEOUT` | `600` | max wait per turn (seconds) |
| `SESSION_MODE` | `build` | ZCode permission mode: `build` (approve writes) / `yolo` / `plan` / `edit` |
| `ALLOWED_CHATS` | _(empty)_ | allowlisted group ids (negative), comma-separated |

## Testing

```bash
# app-server protocol client (requires local ZCode installed)
.venv/bin/python tests/test_app_server.py

# SessionSync coordinator (requires local ZCode installed)
.venv/bin/python tests/test_session_sync.py
```

> Note: these tests spawn a real `zcode app-server` subprocess and call the live model, so they need ZCode installed locally and network access. They are not suitable for CI.

## Limitations

- TUI→bot direction is polled (~1.5s latency), not true real-time push
- A session cannot run concurrent prompts (while the TUI is busy, the bot queues)
- No voice/image support

## License

[MIT](LICENSE)
