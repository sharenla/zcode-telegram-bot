# ZCode Telegram Bot

把智谱 ZCode Agent 接到 Telegram,通过聊天远程指挥 ZCode 干活。

**核心特性:与本地 TUI 双向同步同一 session** —— 在手机上和 ZCode 对话,
与桌面端 TUI 共享完整上下文。

```
                    ┌─ TUI 桌面端 ─┐
                    │   zcode TUI  │
                    └──────┬───────┘
                           │ 各自 spawn
        ┌── 共享 SQLite ───┼──────────┐
        │  (~/.zcode/...)  │          │
        │           ┌──────┴───────┐  │
        │           │ app-server    │  │
Telegram ─► Bot ───►│ (JSON-RPC)   │◄─┘
  用户        │      └──────────────┘
              │ session/send(流式)
              │ session/events(轮询 TUI 活动)
              ▼
        推送回复给用户
```

每用户绑定一个 ZCode `sessionId`,多轮对话上下文连续。
Bot 与 TUI 各自持有 app-server 进程,共享同一个 SQLite,
通过 `session/send`(流式)和 `session/events`(轮询)实现准实时双向同步。

## 架构

| 层 | 文件 | 职责 |
|---|---|---|
| **协议层** | `src/app_server_client.py` | `zcode app-server` 的 JSON-RPC/stdio 客户端 |
| **同步层** | `src/session_sync.py` | send 流式 + TUI 活动 poll 协调器 |
| **会话层** | `src/session_store.py` | 每用户 sessionId + 轮询水位持久化 |
| **Bot 层** | `src/bot.py` | Telegram 收发 + 流式推送 + 命令 |
| **回退层** | `src/zcode_client.py` | `--prompt --json` 模式(`USE_APP_SERVER=0`) |

## 前置条件

1. **ZCode 桌面 App 已安装并登录** —— `/Applications/ZCode.app`
2. **`~/.zcode/cli/config.json` 已配置**(provider + model.main)
3. **Python 3.11+** 和 [uv](https://docs.astral.sh/uv/)

## 快速开始

```bash
cd zcode-telegram-bot
uv venv --python 3.11 .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# 编辑 .env:TELEGRAM_BOT_TOKEN / ALLOWED_USERS / APPROVED_DIRECTORY

.venv/bin/python src/main.py
```

## 命令

| 命令 | 作用 |
|---|---|
| 直接发文字 | ZCode 执行 → 流式返回结果 |
| `/new` | 开启新会话 |
| `/sessions` | 列出本地 TUI session,选一个**关联**(双向同步) |
| `/sync <sessionId>` | 直接关联指定 session |
| `/id` | 查看你的 Telegram user id |
| `/start` | 帮助 |

## 双向同步工作原理

- **bot→session**:bot 用 `session/send` 发消息,通过 `session/event` 通知
  **流式**拿到 assistant 回复,实时推送给 Telegram 用户。
- **TUI→bot**:bot 后台轮询 `session/events?afterSeq=N`,发现 TUI 在同一
  session 上的新活动(用户提问 / 助手回复 / 工具调用),主动推送通知给用户。

**架构约束**:app-server 是单客户端/进程模型,bot 与 TUI 各 spawn 自己的
app-server,无跨进程实时事件总线。因此数据层(共享 SQLite)天然同步,
TUI→bot 方向靠轮询(默认 1.5s)实现准实时。

## 配置项

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `USE_APP_SERVER` | `1` | `1`=app-server 模式;`0`=--prompt 回退 |
| `WORKSPACE_PATH` | = `APPROVED_DIRECTORY` | session 工作区 |
| `POLL_INTERVAL` | `1.5` | TUI→bot 轮询间隔(秒) |
| `APP_SERVER_TURN_TIMEOUT` | `600` | 单 turn 最长等待(秒) |
| `ZCODE_CLI_PATH` | 自动定位 | zcode CLI 路径 |

## 测试

```bash
# app-server 协议客户端(需本机装好 ZCode)
.venv/bin/python tests/test_app_server.py

# SessionSync 协调器(需本机装好 ZCode)
.venv/bin/python tests/test_session_sync.py
```

## 局限

- TUI→bot 方向是轮询(1.5s 延迟),非真·实时推送
- 同一 session 不能并发 send(TUI 正在跑时 bot 会提示稍后)
- 无语音/图片支持
