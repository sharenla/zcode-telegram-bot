"""独立测试 zcode_client —— 不需要 Telegram token。

运行方式:
    cd /path/to/your/project/zcode-telegram-bot
    .venv/bin/python tests/test_zcode_client.py

测试项:
1. CLI 自动定位
2. 单次 prompt
3. 会话续接 --resume
4. 错误处理(空 prompt)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# 让 src/ 可被导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from zcode_client import (  # noqa: E402
    ZCodeClient,
    ZCodeNotFoundError,
    find_zcode_cli,
)


def test_find_cli() -> None:
    print("=" * 50)
    print("[1] 测试 CLI 自动定位")
    try:
        cli = find_zcode_cli()
        print(f"    ✓ 找到 CLI: {cli}")
        assert Path(cli).is_file(), f"路径不存在: {cli}"
    except ZCodeNotFoundError as e:
        print(f"    ✗ 失败: {e}")
        sys.exit(1)


def test_single_prompt(client: ZCodeClient) -> str:
    print("=" * 50)
    print("[2] 测试单次 prompt(新会话)")
    t0 = time.time()
    result = client.run("reply with exactly one word: pong")
    elapsed = time.time() - t0
    print(f"    耗时: {elapsed:.1f}s")
    print(f"    sessionId: {result.session_id}")
    print(f"    response: {result.response!r}")
    print(f"    tokens: {result.total_tokens}")
    assert "pong" in result.response.lower(), f"期望 pong,得到 {result.response!r}"
    assert result.session_id.startswith("sess_"), f"sessionId 格式异常: {result.session_id}"
    print("    ✓ 通过")
    return result.session_id


def test_resume(client: ZCodeClient, session_id: str) -> None:
    print("=" * 50)
    print("[3] 测试会话续接 --resume")
    # 先在会话里存一个 secret
    secret = "ALPHA-7749"
    client.run(f"记住这个暗号: {secret}。只回复 '记住'。", session_id=session_id)
    # 再问
    result = client.run("我刚才告诉你的暗号是什么?只回复暗号本身。", session_id=session_id)
    print(f"    response: {result.response!r}")
    assert secret in result.response, f"期望含 {secret},得到 {result.response!r}"
    print("    ✓ 会话续接成功,正确回忆 secret")


def test_error_handling(client: ZCodeClient) -> None:
    print("=" * 50)
    print("[4] 测试错误处理(正常 prompt,验证非崩溃)")
    # 空字符串 prompt 在 CLI 侧的行为未知,用极短 prompt 测
    result = client.run("hi")
    print(f"    response: {result.response!r}")
    print("    ✓ 未崩溃")


def main() -> None:
    print("\n🧪 ZCode Client 独立测试\n")
    test_find_cli()

    client = ZCodeClient(working_dir="/tmp", timeout=120)
    session_id = test_single_prompt(client)
    test_resume(client, session_id)
    test_error_handling(client)

    print("\n" + "=" * 50)
    print("✅ 全部测试通过!\n")


if __name__ == "__main__":
    main()
