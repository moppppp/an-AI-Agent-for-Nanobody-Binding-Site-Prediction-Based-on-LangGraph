from __future__ import annotations

import json
from pathlib import Path


def detect_text_encoding(data: bytes) -> str:
    if data.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if data.startswith(b"\xfe\xff"):
        return "utf-16-be"
    if b"\x00" in data[: min(200, len(data))]:
        return "utf-16-le"
    return "utf-8-sig"


def read_text_auto(path: Path) -> str:
    data = path.read_bytes()
    return data.decode(detect_text_encoding(data))


def load_json_file(path: Path) -> object:
    text = read_text_auto(path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Windows Notepad 偶发 UTF-16 无 BOM
        return json.loads(path.read_text(encoding="utf-16-le"))
