from __future__ import annotations

import re
from dataclasses import dataclass

_POS = re.compile(
    r"(提高|增加|上升|增强|升高|改善|优于|increase|improved|higher|elevated)",
    re.I,
)
_NEG = re.compile(
    r"(降低|减少|下降|减弱|抑制|劣于|decrease|reduced|lower|inhibited)",
    re.I,
)
_NUMERIC = re.compile(r"(\d+(?:\.\d+)?)\s*(%|倍|fold|nM|μM|uM|nm|pmol)", re.I)


@dataclass
class ChunkFact:
    index: int
    text: str
    source: str
    version_key: str
    year: int | None
    entities: set[str]
    polarity: int


def _polarity(text: str) -> int:
    p = len(_POS.findall(text))
    n = len(_NEG.findall(text))
    if p > n:
        return 1
    if n > p:
        return -1
    return 0


def _numeric_conflict(a: str, b: str) -> bool:
    na = _NUMERIC.findall(a)
    nb = _NUMERIC.findall(b)
    if not na or not nb:
        return False
    try:
        va, ua = float(na[0][0]), na[0][1].lower()
        vb, ub = float(nb[0][0]), nb[0][1].lower()
        if ua != ub:
            return False
        if va == 0 or vb == 0:
            return va != vb
        return abs(va - vb) / max(abs(va), abs(vb)) > 0.3
    except (ValueError, IndexError):
        return False


def build_chunk_facts(
    texts: list[str],
    sources: list[str],
    version_keys: list[str],
    years: list[int | None],
    entities_list: list[set[str]],
) -> list[ChunkFact]:
    return [
        ChunkFact(
            index=i,
            text=texts[i],
            source=sources[i] if i < len(sources) else "",
            version_key=version_keys[i] if i < len(version_keys) else "",
            year=years[i] if i < len(years) else None,
            entities=entities_list[i] if i < len(entities_list) else set(),
            polarity=_polarity(texts[i]),
        )
        for i in range(len(texts))
    ]


def apply_drift_penalties(
    scores: list[float],
    facts: list[ChunkFact],
    *,
    penalty: float,
    top_n: int = 12,
) -> tuple[list[float], list[dict]]:
    if not facts or penalty <= 0:
        return scores, []

    order = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_n]
    adjusted = list(scores)
    events: list[dict] = []

    for ii, i in enumerate(order):
        fi = facts[i]
        if fi.polarity == 0:
            continue
        for j in order[ii + 1 :]:
            fj = facts[j]
            if not (fi.entities & fj.entities):
                continue
            if fi.source and fi.source == fj.source:
                continue
            reason = ""
            conflict = False
            if fi.polarity and fj.polarity and fi.polarity != fj.polarity:
                conflict, reason = True, "polarity"
            elif _numeric_conflict(fi.text, fj.text):
                conflict, reason = True, "numeric"
            if not conflict:
                continue
            penalized = j
            if fj.year and fi.year and fi.year > fj.year:
                penalized = j
            before = adjusted[penalized]
            adjusted[penalized] = max(0.0, adjusted[penalized] - penalty)
            events.append(
                {
                    "penalized_index": penalized,
                    "reason": reason,
                    "kept_index": i,
                    "score_before": before,
                    "score_after": adjusted[penalized],
                }
            )
    return adjusted, events
