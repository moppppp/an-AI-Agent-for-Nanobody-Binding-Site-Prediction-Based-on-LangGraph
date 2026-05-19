from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

_YEAR_IN_TEXT = re.compile(
    r"(?:©|Copyright|\u7248\u6743)?\s*(20\d{2})\s*\u5e74?|"
    r"\((20\d{2})\)|"
    r"(20\d{2})\s*[-–]\s*(20\d{2})",
)
_YEAR_IN_NAME = re.compile(r"(20\d{2})")
_KB_META = re.compile(r"<!--\s*kb-meta:\s*([^>]+)\s*-->", re.IGNORECASE)


def parse_kb_meta_line(line: str) -> dict[str, str]:
    m = _KB_META.search(line)
    if not m:
        return {}
    out: dict[str, str] = {}
    for part in m.group(1).split():
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def extract_year_from_text(text: str) -> int | None:
    years: list[int] = []
    for m in _YEAR_IN_TEXT.finditer(text[:4000]):
        for g in m.groups():
            if g and str(g).isdigit():
                years.append(int(g))
    return max(years) if years else None


def extract_year_from_path(path: Path) -> int | None:
    for m in _YEAR_IN_NAME.finditer(path.stem):
        y = int(m.group(1))
        if 1990 <= y <= datetime.now().year + 1:
            return y
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).year
    except OSError:
        return None


def temporal_weight(
    year: int | None,
    *,
    half_life_years: float,
    reference_year: int | None = None,
) -> float:
    if year is None or half_life_years <= 0:
        return 1.0
    ref = reference_year or datetime.now().year
    age = max(0, ref - year)
    if age == 0:
        return 1.0
    return float(0.5 ** (age / half_life_years))
