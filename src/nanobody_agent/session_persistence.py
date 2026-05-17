from __future__ import annotations

import json
import threading
from typing import Any

from nanobody_agent.config import Settings
from nanobody_agent.conversation_memory import ConversationSession, Turn

_redis_client: Any = None
_lock = threading.Lock()


def _get_redis(settings: Settings) -> Any:
    global _redis_client
    if not settings.session_persist_redis or not settings.redis_enabled:
        return None
    with _lock:
        if _redis_client is not None:
            return _redis_client
        try:
            import redis  # type: ignore[import-untyped]

            c = redis.from_url(settings.redis_url, decode_responses=True)
            c.ping()
            _redis_client = c
        except Exception:
            _redis_client = None
        return _redis_client


def _key(session_id: str, prefix: str) -> str:
    return f"{prefix}:session:{session_id}"


def load_session(session_id: str, settings: Settings) -> ConversationSession | None:
    r = _get_redis(settings)
    if r is None:
        return None
    try:
        raw = r.get(_key(session_id, settings.redis_key_prefix))
        if not raw:
            return None
        data = json.loads(raw)
        sess = ConversationSession(session_id=session_id)
        sess.summary = str(data.get("summary") or "")
        sess.turns = [
            Turn(role=str(t.get("role")), content=str(t.get("content")))
            for t in (data.get("turns") or [])
            if t.get("role") and t.get("content") is not None
        ]
        return sess
    except Exception:
        return None


def save_session(session: ConversationSession, settings: Settings) -> None:
    r = _get_redis(settings)
    if r is None:
        return
    try:
        payload = {
            "summary": session.summary,
            "turns": [{"role": t.role, "content": t.content} for t in session.turns],
        }
        ttl = int(settings.session_persist_ttl_seconds)
        r.setex(
            _key(session.session_id, settings.redis_key_prefix),
            ttl,
            json.dumps(payload, ensure_ascii=False),
        )
    except Exception:
        pass


def delete_session(session_id: str, settings: Settings) -> None:
    r = _get_redis(settings)
    if r is None:
        return
    try:
        r.delete(_key(session_id, settings.redis_key_prefix))
    except Exception:
        pass
