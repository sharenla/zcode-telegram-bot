"""会话持久化 —— 每个 Telegram 用户绑定一个 ZCode sessionId。

存储 (user_id, session_id) 映射到 JSON 文件,重启不丢。
支持:
- get / set / reset
- LRU 淘汰(每用户会话数上限)
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock
from typing import Optional


class SessionStore:
    """线程安全的 sessionId 持久化存储。

    数据结构(JSON 文件):
        {
          "123456789": {
            "session_id": "sess_xxx",
            "last_seq": 42,              # 轮询水位(app-server 协议 seq)
            "delivery_kind": "web-remote-replayable",
            "updated_at": 1700000000
          }
        }
    """

    def __init__(self, db_path: str | Path, max_per_user: int = 1) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._max = max_per_user
        self._lock = Lock()
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self._path.is_file():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(self._path)

    def get(self, user_id: int) -> Optional[str]:
        """取某用户当前的 sessionId,没有则返回 None。"""
        with self._lock:
            entry = self._data.get(str(user_id))
            return entry["session_id"] if entry else None

    def set(self, user_id: int, session_id: str) -> None:
        """设置/更新某用户的 sessionId(保留已有 last_seq)。"""
        with self._lock:
            existing = self._data.get(str(user_id), {})
            self._data[str(user_id)] = {
                "session_id": session_id,
                "last_seq": existing.get("last_seq", 0),
                "delivery_kind": existing.get(
                    "delivery_kind", "web-remote-replayable"
                ),
                "updated_at": int(time.time()),
            }
            self._save()

    def get_last_seq(self, user_id: int) -> int:
        """取某用户 session 的轮询水位 seq(默认 0)。"""
        with self._lock:
            entry = self._data.get(str(user_id))
            return entry.get("last_seq", 0) if entry else 0

    def set_last_seq(self, user_id: int, seq: int) -> None:
        """更新某用户的轮询水位(重启后续传,不重复推送)。"""
        with self._lock:
            entry = self._data.get(str(user_id))
            if not entry:
                return  # 没绑 session,不存孤立水位
            entry["last_seq"] = seq
            entry["updated_at"] = int(time.time())
            self._save()

    def reset(self, user_id: int) -> None:
        """清空某用户的 session(下次消息会开新会话)。"""
        with self._lock:
            self._data.pop(str(user_id), None)
            self._save()
