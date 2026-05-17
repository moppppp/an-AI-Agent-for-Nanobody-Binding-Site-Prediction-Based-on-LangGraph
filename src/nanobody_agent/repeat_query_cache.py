from __future__ import annotations

import hashlib
import json
import re
import threading
from typing import Any

from nanobody_agent.config import Settings

_MEMORY: dict[str, dict[str, Any]] = {}
_MEMORY_LOCK = threading.Lock()


def normalize_query(query: str) -> str:
    """归一化问题文本，用于判断「是否同一问题」。"""
    text = (query or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _query_hash(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


class RepeatQueryCache:
    """同 session 内相同问题：连续重复或间断重复均可命中 Redis/内存缓存。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._threshold = max(1, int(settings.repeat_query_cache_threshold))
        self._ttl = max(60, int(settings.redis_cache_ttl_seconds))
        self._prefix = (settings.redis_key_prefix or "nanobody").strip()
        self._intermittent = bool(settings.repeat_query_cache_intermittent)
        self._redis: Any = None
        if settings.redis_enabled:
            self._redis = self._connect_redis(settings.redis_url)

    @staticmethod
    def _connect_redis(url: str) -> Any:
        try:
            import redis  # type: ignore[import-untyped]
        except ImportError:
            print("[nanobody] 未安装 redis 包，重复问题缓存使用内存模式。pip install redis", flush=True)
            return None
        try:
            client = redis.from_url(url, decode_responses=True)
            client.ping()
            print("[nanobody] Redis 已连接，重复问题缓存已启用", flush=True)
            return client
        except Exception as e:
            print(f"[nanobody] Redis 连接失败，使用内存缓存: {e}", flush=True)
            return None

    def _state_key(self, session_id: str) -> str:
        return f"{self._prefix}:repeat:state:{session_id}"

    def _asks_key(self, session_id: str) -> str:
        return f"{self._prefix}:repeat:asks:{session_id}"

    def _answer_key(self, session_id: str, normalized: str) -> str:
        return f"{self._prefix}:repeat:answer:{session_id}:{_query_hash(normalized)}"

    def _get_state(self, session_id: str) -> tuple[str, int]:
        if self._redis is not None:
            try:
                data = self._redis.hgetall(self._state_key(session_id))
                return (data.get("last_q") or "", int(data.get("count") or 0))
            except Exception:
                pass
        with _MEMORY_LOCK:
            st = _MEMORY.get(session_id) or {}
            return (st.get("last_q") or "", int(st.get("count") or 0))

    def _set_state(self, session_id: str, last_q: str, count: int) -> None:
        if self._redis is not None:
            try:
                key = self._state_key(session_id)
                pipe = self._redis.pipeline()
                pipe.hset(key, mapping={"last_q": last_q, "count": str(count)})
                pipe.expire(key, self._ttl)
                pipe.execute()
                return
            except Exception:
                pass
        with _MEMORY_LOCK:
            bucket = _MEMORY.setdefault(session_id, {})
            bucket["last_q"] = last_q
            bucket["count"] = count

    def _bump_total_asks(self, session_id: str, normalized: str) -> int:
        qhash = _query_hash(normalized)
        if self._redis is not None:
            try:
                key = self._asks_key(session_id)
                total = int(self._redis.hincrby(key, qhash, 1))
                self._redis.expire(key, self._ttl)
                return total
            except Exception:
                pass
        with _MEMORY_LOCK:
            bucket = _MEMORY.setdefault(session_id, {})
            asks = bucket.setdefault("asks", {})
            asks[qhash] = int(asks.get(qhash, 0)) + 1
            return asks[qhash]

    def record_ask(self, session_id: str, query: str) -> tuple[int, int, str]:
        """
        返回 (连续相同次数, 该问题累计次数含间断, 归一化问题)。
        累计次数：中间问了别的问题后再问同一句，也会 +1。
        """
        sid = (session_id or "default").strip()
        norm = normalize_query(query)
        last_q, count = self._get_state(sid)
        if norm and norm == last_q:
            consecutive = count + 1
        else:
            consecutive = 1
        self._set_state(sid, norm, consecutive)
        total = self._bump_total_asks(sid, norm) if norm else 0
        return consecutive, total, norm

    def should_read_cache(self, consecutive: int, total: int, normalized: str, session_id: str) -> bool:
        if not normalized or not self.get_cached(session_id, normalized):
            return False
        if self._intermittent and total >= 2:
            return True
        return consecutive > self._threshold

    def should_write_cache(self) -> bool:
        """每次完整推理后都写入/更新该问题的缓存。"""
        return True

    def get_cached(self, session_id: str, normalized: str) -> dict[str, Any] | None:
        if not normalized:
            return None
        sid = (session_id or "default").strip()
        key = self._answer_key(sid, normalized)
        raw: str | None = None
        if self._redis is not None:
            try:
                raw = self._redis.get(key)
            except Exception:
                raw = None
        if raw is None:
            with _MEMORY_LOCK:
                raw = (_MEMORY.get(sid) or {}).get(f"ans:{_query_hash(normalized)}")
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None

    def save_cached(self, session_id: str, normalized: str, payload: dict[str, Any]) -> None:
        if not normalized:
            return
        sid = (session_id or "default").strip()
        key = self._answer_key(sid, normalized)
        body = json.dumps(payload, ensure_ascii=False)
        if self._redis is not None:
            try:
                self._redis.setex(key, self._ttl, body)
                return
            except Exception:
                pass
        with _MEMORY_LOCK:
            bucket = _MEMORY.setdefault(sid, {})
            bucket[f"ans:{_query_hash(normalized)}"] = body

    def clear_session(self, session_id: str) -> None:
        sid = (session_id or "").strip()
        if not sid:
            return
        if self._redis is not None:
            try:
                self._redis.delete(self._state_key(sid), self._asks_key(sid))
            except Exception:
                pass
        with _MEMORY_LOCK:
            _MEMORY.pop(sid, None)

    @property
    def redis_available(self) -> bool:
        return self._redis is not None

    @property
    def threshold(self) -> int:
        return self._threshold


_cache: RepeatQueryCache | None = None
_cache_lock = threading.Lock()


def get_repeat_query_cache(settings: Settings | None = None) -> RepeatQueryCache:
    global _cache
    if _cache is not None:
        return _cache
    with _cache_lock:
        if _cache is None:
            from nanobody_agent.config import get_settings

            _cache = RepeatQueryCache(settings or get_settings())
        return _cache
