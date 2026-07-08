"""SessionSync 协调器集成测试。

验证两个核心路径:
- send_stream / send_collect:bot→session 流式发消息
- watch + 轮询:TUI→bot 方向(用第二次 send 模拟 TUI 活动,验证轮询捕获)

运行:
    .venv/bin/python tests/test_session_sync.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from app_server_client import AppServerClient  # noqa: E402
from session_sync import SessionSync  # noqa: E402

WORKSPACE = os.environ.get("APPSERVER_TEST_WORKSPACE", "/path/to/your/project")


async def test_send_collect(sync: SessionSync, sid: str) -> None:
    """send_collect 应聚合出最终回复。"""
    result = await sync.send_collect(sid, "reply with exactly one word: pong")
    assert result.error is None, f"不应有错误,实际: {result.error}"
    assert "pong" in result.response.lower(), f"回复应含 pong,实际: {result.response!r}"
    assert result.total_tokens > 0, f"token 数应 > 0,实际: {result.total_tokens}"
    print(f"  ✅ send_collect → {result.response!r} ({result.total_tokens} tokens)")


async def test_watch_polling(sync: SessionSync, sid: str) -> None:
    """watch 后,新活动应触发 on_events 回调。

    用第二次 send 模拟"TUI 发了消息",验证 watcher 轮询能捕获。
    """
    captured: list = []
    event = asyncio.Event()

    def on_events(session_id: str, events: list) -> None:
        captured.extend(events)
        # 收到 turn.completed 即算成功
        if any(e.get("type") == "turn.completed" for e in events):
            event.set()

    # 先拿到当前水位
    last_seq = sync.get_last_seq(sid) or 0
    sync.watch(sid, last_seq, on_events)

    # 模拟 TUI 活动:再发一条(产生事件,watcher 应轮询到)
    await sync.send_collect(sid, "say hi in one word")

    # 等轮询捕获(轮询间隔 1.5s + 余量)
    try:
        await asyncio.wait_for(event.wait(), timeout=10)
    except asyncio.TimeoutError:
        pass  # 不强制失败,下面断言

    sync.unwatch(sid)
    types = [e.get("type") for e in captured]
    assert "turn.completed" in types, (
        f"watcher 应捕获到 turn.completed,实际捕获事件类型: {types}"
    )
    print(f"  ✅ watch 轮询捕获 {len(captured)} 个事件,含 turn.completed")


async def main() -> None:
    print("=" * 60)
    print("SessionSync 集成测试")
    print("=" * 60)

    client = AppServerClient(cwd=WORKSPACE, request_timeout=90)
    sync = SessionSync(client, poll_interval=1.0)  # 测试用更短间隔
    await sync.start()

    try:
        # 建一个测试 session
        sid = await client.create_session(WORKSPACE, mode="yolo")
        await client.subscribe(sid)
        print(f"\n测试 session: {sid}\n")

        print("[1] send_collect(流式聚合)")
        await test_send_collect(sync, sid)

        print("\n[2] watch + 轮询(模拟 TUI 活动)")
        await test_watch_polling(sync, sid)

        print("\n" + "=" * 60)
        print("✅ 全部通过")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ 断言失败: {e}")
        raise
    finally:
        await sync.stop()


if __name__ == "__main__":
    asyncio.run(main())
