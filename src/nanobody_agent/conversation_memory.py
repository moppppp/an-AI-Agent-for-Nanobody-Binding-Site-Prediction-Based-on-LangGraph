from __future__ import annotations

import threading
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage

from nanobody_agent.config import Settings
from nanobody_agent.llm_utils import get_chat_model

_SUMMARY_SYSTEM = """你是会话摘要助手。将对话历史压缩为简洁中文要点（保留实体、数值、用户目标与已达成结论）。
若已有摘要，请在其基础上合并更新，避免重复。只输出摘要正文，不超过指定字数。"""


@dataclass
class Turn:
    role: str  # user | assistant
    content: str


@dataclass
class ConversationSession:
    session_id: str
    summary: str = ""
    turns: list[Turn] = field(default_factory=list)

    def pair_count(self) -> int:
        return len(self.turns) // 2

    def build_context_before_turn(self, settings: Settings) -> str:
        """摘要 + 滑动窗口内近期轮次（不含本轮待发送问题）。"""
        parts: list[str] = []
        if self.summary.strip():
            parts.append("【历史摘要】\n" + self.summary.strip())
        recent = self._window_turns(settings)
        if recent:
            lines: list[str] = []
            for t in recent:
                label = "用户" if t.role == "user" else "助手"
                text = t.content.strip()
                if len(text) > 500:
                    text = text[:500] + "…"
                lines.append(f"{label}：{text}")
            parts.append("【近期对话】\n" + "\n".join(lines))
        return "\n\n".join(parts)

    def _window_turns(self, settings: Settings) -> list[Turn]:
        max_msgs = max(2, int(settings.chat_memory_window_turns) * 2)
        return self.turns[-max_msgs:]

    def record_turn(self, user_text: str, assistant_text: str, settings: Settings | None = None) -> None:
        u = (user_text or "").strip()
        a = (assistant_text or "").strip()
        if u:
            self.turns.append(Turn("user", u))
        if a:
            self.turns.append(Turn("assistant", a))
        if settings is not None:
            from nanobody_agent.session_persistence import save_session

            save_session(self, settings)

    def compress(self, settings: Settings) -> bool:
        """超出窗口的旧轮次合并进摘要。返回是否发生了压缩。"""
        max_msgs = max(2, int(settings.chat_memory_window_turns) * 2)
        if len(self.turns) <= max_msgs:
            return False
        archive = self.turns[:-max_msgs]
        self.turns = self.turns[-max_msgs:]
        self.summary = _summarize_turns(settings, self.summary, archive)
        cap = int(settings.chat_memory_max_summary_chars)
        if len(self.summary) > cap:
            self.summary = self.summary[: cap - 1] + "…"
        return True


def _summarize_turns(settings: Settings, prior_summary: str, turns: list[Turn]) -> str:
    if not turns:
        return prior_summary
    lines: list[str] = []
    for t in turns:
        label = "用户" if t.role == "user" else "助手"
        lines.append(f"{label}：{(t.content or '').strip()[:600]}")
    new_block = "\n".join(lines)
    cap = int(settings.chat_memory_max_summary_chars)
    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        return _heuristic_summary(prior_summary, new_block, cap)
    try:
        llm = get_chat_model(settings)
        prior = (prior_summary or "").strip() or "（无）"
        prompt = (
            f"字数上限约 {min(400, cap // 4)} 字。\n"
            f"已有摘要：\n{prior}\n\n待并入的新对话：\n{new_block}"
        )
        resp = llm.invoke(
            [
                SystemMessage(content=_SUMMARY_SYSTEM),
                HumanMessage(content=prompt),
            ]
        )
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        merged = (text or "").strip()
        if merged:
            return merged[:cap]
    except Exception:
        pass
    return _heuristic_summary(prior_summary, new_block, cap)


def _heuristic_summary(prior_summary: str, new_block: str, cap: int) -> str:
    parts: list[str] = []
    if prior_summary.strip():
        parts.append(prior_summary.strip())
    for line in new_block.splitlines():
        line = line.strip()
        if line:
            parts.append(line[:160])
    out = " | ".join(parts)
    if len(out) > cap:
        return out[: cap - 1] + "…"
    return out


class ConversationStore:
    def __init__(self, max_sessions: int = 256) -> None:
        self._max_sessions = max(16, max_sessions)
        self._sessions: dict[str, ConversationSession] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str, settings: Settings | None = None) -> ConversationSession:
        sid = (session_id or "").strip() or "default"
        with self._lock:
            if sid not in self._sessions:
                loaded = None
                if settings is not None:
                    from nanobody_agent.session_persistence import load_session

                    loaded = load_session(sid, settings)
                self._sessions[sid] = loaded or ConversationSession(session_id=sid)
                self._order.append(sid)
                while len(self._order) > self._max_sessions:
                    old = self._order.pop(0)
                    self._sessions.pop(old, None)
            else:
                if sid in self._order:
                    self._order.remove(sid)
                self._order.append(sid)
            return self._sessions[sid]

    def clear(self, session_id: str, settings: Settings | None = None) -> bool:
        sid = (session_id or "").strip()
        if not sid:
            return False
        if settings is not None:
            from nanobody_agent.session_persistence import delete_session

            delete_session(sid, settings)
        with self._lock:
            if sid in self._sessions:
                del self._sessions[sid]
            if sid in self._order:
                self._order.remove(sid)
            return True


_store: ConversationStore | None = None


def get_conversation_store() -> ConversationStore:
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store
