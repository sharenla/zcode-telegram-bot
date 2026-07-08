"""app-server 协议客户端的端到端验证测试。

真实 spawn `zcode app-server`,验证 AppServerClient 的核心能力:
create / list / resume / subscribe / send_and_stream。

运行:
    .venv/bin/python tests/test_app_server.py

需要本机已安装 ZCode App 并配置好 CLI。
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# 让 src/ 可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from app_server_client import (  # noqa: E402
    AppServerClient,
    AppServerError,
    SessionUnavailableError,
)

WORKSPACE = os.environ.get("APPSERVER_TEST_WORKSPACE", "/path/to/your/project")


async def test_lifecycle(client: AppServerClient) -> None:
    """start / is_running / close。"""
    assert not client.is_running, "启动前不应 running"
    await client.start()
    assert client.is_running, "start 后应 running"
    print("  ✅ start / is_running")


async def test_create_and_send(client: AppServerClient) -> str:
    """create → subscribe → send_and_stream,返回新 sessionId。"""
    sid = await client.create_session(WORKSPACE)
    assert sid.startswith("sess_"), f"sessionId 应以 sess_ 开头,实际: {sid}"
    print(f"  ✅ create_session → {sid}")

    await client.subscribe(sid)
    print("  ✅ subscribe")

    # 发消息,收集流式事件
    events = []
    async for ev in client.send_and_stream(sid, "reply with exactly one word: pong"):
        events.append(ev)
        print(f"     事件 [{ev.seq:>2}] {ev.type}")

    types = [e.type for e in events]
    assert "turn.completed" in types, f"应收到 turn.completed,实际事件: {types}"
    # 找 completed 事件验证回复内容
    completed = next(e for e in events if e.type == "turn.completed")
    response = completed.payload.get("response", "")
    assert "pong" in response.lower(), f"回复应含 pong,实际: {response!r}"
    print(f"  ✅ send_and_stream → 回复 {response!r} (共 {len(events)} 个事件)")

    return sid


async def test_list(client: AppServerClient, expected_sid: str) -> None:
    """list 应包含刚创建的 session。"""
    sessions = await client.list_sessions(WORKSPACE)
    assert len(sessions) > 0, "应至少有 1 个 session"
    ids = [s.session_id for s in sessions]
    assert expected_sid in ids, f"list 应包含刚建的 {expected_sid},实际: {ids[:3]}"
    print(f"  ✅ list_sessions → {len(sessions)} 个,含新建的")


async def test_resume(client: AppServerClient, sid: str) -> None:
    """resume 应返回历史消息,含刚发的 pong 对话。"""
    snapshot = await client.resume_session(sid)
    messages = snapshot.get("messages", [])
    assert len(messages) >= 2, f"resume 应有历史消息,实际 {len(messages)} 条"
    # 拼出所有文本
    texts = []
    for m in messages:
        for p in m.get("parts", []):
            pd = p.get("data") or p
            if isinstance(pd, dict) and pd.get("text"):
                texts.append(pd["text"].lower())
    joined = " ".join(texts)
    assert "pong" in joined, f"历史应含 pong,实际: {texts}"
    print(f"  ✅ resume_session → {len(messages)} 条历史消息")


async def test_resume_unknown(client: AppServerClient) -> None:
    """resume 不存在的 session 应抛 SessionUnavailableError。"""
    try:
        await client.resume_session("sess_does-not-exist-00000000")
        assert False, "应抛 SessionUnavailableError"
    except SessionUnavailableError:
        print("  ✅ resume 不存在 session → SessionUnavailableError")


async def main() -> None:
    print("=" * 60)
    print("AppServerClient 端到端测试")
    print(f"workspace: {WORKSPACE}")
    print("=" * 60)

    client = AppServerClient(cwd=WORKSPACE)
    try:
        print("\n[1] 生命周期")
        await test_lifecycle(client)

        print("\n[2] create + subscribe + send(流式)")
        sid = await test_create_and_send(client)

        print("\n[3] list")
        await test_list(client, sid)

        print("\n[4] resume(历史消息)")
        await test_resume(client, sid)

        print("\n[5] resume 不存在的 session")
        await test_resume_unknown(client)

        print("\n" + "=" * 60)
        print("✅ 全部通过")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ 断言失败: {e}")
        raise
    except AppServerError as e:
        print(f"\n❌ 协议错误: {e}")
        raise
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
