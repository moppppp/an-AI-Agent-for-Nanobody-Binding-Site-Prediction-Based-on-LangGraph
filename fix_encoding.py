"""Convert UTF-16 project files to UTF-8. Run: python fix_encoding.py"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
GLOBS = ("*.py", "*.md", "*.txt", "*.json")
EXTRA = (ROOT / ".env",)


def fix_file(path: Path) -> bool:
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe"):
        text = data.decode("utf-16-le")
    elif data.startswith(b"\xfe\xff"):
        text = data.decode("utf-16-be")
    elif b"\x00" in data[: min(200, len(data))]:
        text = data.decode("utf-16-le")
    else:
        return False
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    print(f"fixed: {path}")
    return True


def main() -> None:
    count = 0
    for pattern in GLOBS:
        for path in ROOT.rglob(pattern):
            if fix_file(path):
                count += 1
    for path in EXTRA:
        if path.is_file() and fix_file(path):
            count += 1
    print(f"done, fixed {count} file(s)")


if __name__ == "__main__":
    main()
