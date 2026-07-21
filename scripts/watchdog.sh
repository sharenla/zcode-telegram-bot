#!/bin/bash
# bot 看门狗:检测 polling 卡死,卡死则重启。
#
# 判定:bot 每 60s 记一条"💓 心跳"日志。若日志在过去 3 分钟内无心跳,
# 判定 polling 卡死,重启进程。
#
# 由 launchd 每 2 分钟调用,或手动 crontab。
# 日志:logs/watchdog.log

PROJECT_DIR="/Users/wukong/ZCodeProject/zcode-telegram-bot"
LOG="$PROJECT_DIR/logs/bot.log"
WATCHDOG_LOG="$PROJECT_DIR/logs/watchdog.log"
STALE_THRESHOLD=180  # 3 分钟(3 次心跳)无更新视为卡死

ts() { date "+%Y-%m-%d %H:%M:%S"; }

mkdir -p "$PROJECT_DIR/logs"

# 1. 进程不在 → 启动
BOTPID=$(pgrep -f "python.*src/main.py" | head -1)
if [ -z "$BOTPID" ]; then
    echo "[$(ts)] bot 进程不在,启动..." >> "$WATCHDOG_LOG"
    cd "$PROJECT_DIR"
    nohup .venv/bin/python src/main.py > "$LOG" 2>&1 &
    echo "[$(ts)] 已启动 PID $!" >> "$WATCHDOG_LOG"
    exit 0
fi

# 2. 进程在 → 检查心跳(日志最后修改时间)
if [ -f "$LOG" ]; then
    LAST_MOD=$(stat -f "%m" "$LOG" 2>/dev/null || echo 0)
    NOW=$(date "+%s")
    AGE=$((NOW - LAST_MOD))
    if [ "$AGE" -gt "$STALE_THRESHOLD" ]; then
        echo "[$(ts)] 日志 ${AGE}s 无更新(>${STALE_THRESHOLD}s),判定卡死,重启 PID $BOTPID" >> "$WATCHDOG_LOG"
        kill -9 "$BOTPID" 2>/dev/null || true
        pkill -9 -f "zcode.cjs app-server" 2>/dev/null || true
        sleep 2
        cd "$PROJECT_DIR"
        nohup .venv/bin/python src/main.py > "$LOG" 2>&1 &
        echo "[$(ts)] 已重启 PID $!" >> "$WATCHDOG_LOG"
    fi
fi
