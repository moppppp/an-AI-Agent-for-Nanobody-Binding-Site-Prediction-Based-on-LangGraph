from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class ToolAuditLog:
    """Append-only JSONL audit trail; data stays on-prem (local paths only)."""

    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir.resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.log_dir / "tool_calls.jsonl"

    def record(
        self,
        *,
        tool_name: str,
        actor: str,
        params: dict[str, Any],
        result_summary: str,
        success: bool,
        duration_ms: float,
        error: str | None = None,
    ) -> str:
        entry = {
            "id": uuid.uuid4().hex[:16],
            "ts": time.time(),
            "tool": tool_name,
            "actor": actor,
            "params": params,
            "success": success,
            "duration_ms": round(duration_ms, 2),
            "result_summary": result_summary[:500],
            "error": error,
        }
        with self._path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry["id"]
