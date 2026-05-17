from __future__ import annotations

import re
from typing import Any

_REF_PATTERN = re.compile(r"\[(\d+)\]")


def build_citation_snippets(hits: list[dict]) -> list[dict[str, Any]]:
    """Attach stable citation ids to retrieval hits."""
    out: list[dict[str, Any]] = []
    for i, h in enumerate(hits, start=1):
        text = (h.get("text") or "").strip()
        if not text:
            continue
        out.append(
            {
                "id": i,
                "rank": h.get("rank", i),
                "score": float(h.get("score") or 0.0),
                "text": text,
                "preview": text[:280] + ("…" if len(text) > 280 else ""),
            }
        )
    return out


def format_context_with_refs(snippets: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for s in snippets:
        parts.append(f"[{s['id']}] {s['text']}")
    return "\n\n---\n\n".join(parts) if parts else "(无检索片段)"


def inject_citation_markers(answer: str, snippets: list[dict[str, Any]]) -> str:
    """Ensure answer contains [n] markers; append Sources block if missing."""
    if not snippets:
        return answer
    text = (answer or "").strip()
    if not _REF_PATTERN.search(text):
        text += "\n\n（依据知识库片段生成，详见下方引用。）"
    lines = ["", "---", "**引用来源**"]
    for s in snippets:
        lines.append(f"- [{s['id']}] {s['preview']}")
    return text + "\n".join(lines)
