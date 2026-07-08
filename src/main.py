"""入口 —— 启动 bot。

用法:
    .venv/bin/python -m src.main
    # 或
    .venv/bin/python src/main.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# 让 src/ 可被导入(直接 `python src/main.py` 也能跑)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from telegram import Update  # noqa: E402

from bot import ZCodeTelegramBot, set_bot_instance  # noqa: E402
from config import Config  # noqa: E402


def setup_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=logging.INFO,
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


def main() -> None:
    setup_logging()
    log = logging.getLogger("main")

    config = Config.from_env()
    log.info("✅ 配置加载完成")
    log.info("   ALLOWED_USERS: %s", config.allowed_users)
    log.info("   ALLOWED_CHATS: %s", config.allowed_chats)
    log.info("   APPROVED_DIRECTORY: %s", config.approved_directory)
    log.info("   USE_APP_SERVER: %s", config.use_app_server)

    bot = ZCodeTelegramBot(config)
    app = bot.build_application()
    # 存下 app 实例,供轮询推送在无 ctx 场景发消息
    set_bot_instance(app)

    log.info("🚀 Bot 启动中(polling 模式)... 按 Ctrl+C 停止")
    app.run_polling(allowed_updates=Update.__subclasses__())


if __name__ == "__main__":
    main()
