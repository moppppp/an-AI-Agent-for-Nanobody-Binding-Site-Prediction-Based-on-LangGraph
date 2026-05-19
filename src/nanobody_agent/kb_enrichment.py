# -*- coding: utf-8 -*-
"""Knowledge enrichment: entity align, qualitative expand, temporal decay, fact drift."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from nanobody_agent.config import Settings

# --- temporal / meta ---
_YEAR_IN_TEXT = re.compile(
    r"(?:©|Copyright|\u7248\u6743)?\s*(20\d{2})\s*\u5e74?|\((20\d{2})\)",
)
_YEAR_IN_NAME = re.compile(r"(20\d{2})")
_KB_META = re.compile(r"<!--\s*kb-meta:\s*([^>]+)\s*-->", re.I)
_SOURCE_TAG = re.compile(r"<!--\s*source:\s*([^>]+)\s*-->", re.I)

_POS = re.compile(r"(提高|增加|上升|增强|升高|改善|优于|increase|improved|higher)", re.I)
_NEG = re.compile(r"(降低|减少|下降|减弱|抑制|劣于|decrease|reduced|lower)", re.I)
_NUMERIC = re.compile(r"(\d+(?:\.\d+)?)\s*(%|倍|fold|nM|μM|uM)", re.I)

_DEFAULT_ALIASES: dict[str, list[str]] = {
    "纳米抗体": ["nanobody", "Nanobody", "单域抗体", "VHH抗体"],
    "VHH": ["重链可变区", "单域抗体可变区", "VHH domain"],
    "结合位点": ["表位", "epitope", "binding site"],
    "NanoKGAT": ["nanoKGAT", "图神经网络结合位点预测"],
}

_DEFAULT_QUALITATIVE: dict[str, str] = {
    "显著": "统计显著 (p<0.05) 或效应量较大",
    "明显": "可观测的实质性差异",
    "略微": "小幅度变化",
    "大幅": "效应量或变化幅度较大",
}


@dataclass
class KnowledgeChunk:
    text: str
    source: str
    year: int | None
    version_key: str
    aligned_text: str


@dataclass
class ChunkFact:
    index: int
    text: str
    source: str
    version_key: str
    year: int | None
    entities: set[str]
    polarity: int


class KnowledgeEnrichment:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._alias_to_canonical: dict[str, str] = {}
        self._canonical_to_aliases: dict[str, list[str]] = {}
        self._qualitative: dict[str, str] = {}
        self._load_lexicons()

    def _read_json(self, path: Path) -> dict | None:
        if not path.is_file():
            return None
        data = path.read_bytes()
        if data.startswith(b"\xff\xfe"):
            text = data.decode("utf-16-le")
        elif data.startswith(b"\xfe\xff"):
            text = data.decode("utf-16-be")
        else:
            text = data.decode("utf-8-sig", errors="replace")
        try:
            raw = json.loads(text)
            return raw if isinstance(raw, dict) else None
        except json.JSONDecodeError:
            return None

    def _load_lexicons(self) -> None:
        root = self.settings.knowledge_dir
        aliases = self._read_json(root / "entity_aliases.json") or _DEFAULT_ALIASES
        for canonical, alias_list in aliases.items():
            c = str(canonical).strip()
            forms = [c]
            if isinstance(alias_list, list):
                forms.extend(str(a).strip() for a in alias_list if str(a).strip())
            self._canonical_to_aliases[c] = forms
            for f in forms:
                self._alias_to_canonical[f.lower()] = c
        qual = self._read_json(root / "qualitative_map.json") or _DEFAULT_QUALITATIVE
        self._qualitative = {str(k): str(v) for k, v in qual.items()}

    def prepare_query(self, query: str) -> tuple[str, dict]:
        meta: dict = {"entity_replacements": [], "qualitative_hits": []}
        q = query
        if self.settings.entity_align_enabled and self._alias_to_canonical:
            q, meta["entity_replacements"] = self._canonicalize(q)
            q = self._expand_entities(q)
        if self.settings.qualitative_expand_enabled:
            q, meta["qualitative_hits"] = self._expand_qualitative(q)
        return q, meta

    def _canonicalize(self, text: str) -> tuple[str, list[str]]:
        replacements: list[str] = []
        out = text
        for alias, canonical in sorted(self._alias_to_canonical.items(), key=lambda x: -len(x[0])):
            if alias == canonical.lower():
                continue
            pat = re.compile(re.escape(alias), re.I)
            if pat.search(out):
                out = pat.sub(canonical, out)
                replacements.append(f"{alias}->{canonical}")
        return out, replacements

    def _expand_entities(self, text: str) -> str:
        extra: list[str] = []
        low = text.lower()
        for canonical, aliases in self._canonical_to_aliases.items():
            if canonical.lower() in low or any(a.lower() in low for a in aliases):
                extra.extend(aliases[:4])
        return text + (" " + " ".join(dict.fromkeys(extra)) if extra else "")

    def _expand_qualitative(self, query: str) -> tuple[str, list[str]]:
        hits = [w for w in self._qualitative if w in query]
        if not hits:
            return query, []
        hints = [self._qualitative[w] for w in hits[:3]]
        return query + " " + " ".join(hints), hits

    def entities_in_text(self, text: str) -> set[str]:
        low = text.lower()
        return {c for a, c in self._alias_to_canonical.items() if a in low}

    def temporal_weight(self, year: int | None) -> float:
        if not self.settings.temporal_decay_enabled or year is None:
            return 1.0
        hl = float(self.settings.temporal_half_life_years)
        if hl <= 0:
            return 1.0
        age = max(0, datetime.now().year - year)
        return float(0.5 ** (age / hl))

    def load_chunks(self, paths: list[Path]) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        max_n = int(self.settings.knowledge_max_chunks or 0)
        for p in paths:
            try:
                raw = p.read_bytes()
            except OSError:
                continue
            if not raw.strip():
                continue
            if raw.startswith(b"\xff\xfe"):
                text = raw.decode("utf-16-le")
            else:
                text = raw.decode("utf-8-sig", errors="replace")
            file_year = self._year_from_path(p)
            meta: dict[str, str] = {}
            lines: list[str] = []
            for line in text.splitlines():
                m = _KB_META.search(line)
                if m:
                    for part in m.group(1).split():
                        if "=" in part:
                            k, v = part.split("=", 1)
                            meta[k.strip()] = v.strip()
                    continue
                sm = _SOURCE_TAG.search(line)
                if sm:
                    meta["source"] = sm.group(1).strip()
                    continue
                lines.append(line)
            body = "\n".join(lines)
            if meta.get("year", "").isdigit():
                file_year = int(meta["year"])
            elif file_year is None:
                ym = _YEAR_IN_TEXT.search(body[:3000])
                if ym:
                    file_year = int(next(g for g in ym.groups() if g))
            vkey = meta.get("version") or f"{p.as_posix()}:{p.stat().st_mtime_ns}"
            source = meta.get("source") or p.name
            for para in re.split(r"\n{2,}", body):
                para = para.strip()
                if len(para) < 20:
                    continue
                aligned, _ = self._canonicalize(para)
                chunks.append(
                    KnowledgeChunk(para, source, file_year, vkey, aligned)
                )
                if max_n > 0 and len(chunks) >= max_n:
                    return chunks
        return chunks

    def _year_from_path(self, path: Path) -> int | None:
        for m in _YEAR_IN_NAME.finditer(path.stem):
            y = int(m.group(1))
            if 1990 <= y <= datetime.now().year + 1:
                return y
        try:
            return datetime.fromtimestamp(path.stat().st_mtime).year
        except OSError:
            return None

    def apply_fact_drift(
        self, scores: list[float], chunks: list[KnowledgeChunk]
    ) -> tuple[list[float], list[dict]]:
        if not self.settings.fact_drift_enabled:
            return scores, []
        penalty = float(self.settings.fact_drift_penalty)
        facts = [
            ChunkFact(
                i,
                c.aligned_text,
                c.source,
                c.version_key,
                c.year,
                self.entities_in_text(c.aligned_text),
                self._polarity(c.aligned_text),
            )
            for i, c in enumerate(chunks)
        ]
        order = sorted(range(len(scores)), key=lambda i: -scores[i])[:12]
        adjusted = list(scores)
        events: list[dict] = []
        for ii, i in enumerate(order):
            fi = facts[i]
            if not fi.polarity:
                continue
            for j in order[ii + 1 :]:
                fj = facts[j]
                if not (fi.entities & fj.entities):
                    continue
                if fi.source == fj.source:
                    continue
                conflict = (
                    fi.polarity and fj.polarity and fi.polarity != fj.polarity
                ) or self._numeric_conflict(fi.text, fj.text)
                if not conflict:
                    continue
                penalized = j
                before = adjusted[penalized]
                adjusted[penalized] = max(0.0, adjusted[penalized] - penalty)
                events.append(
                    {
                        "penalized_index": penalized,
                        "kept_index": i,
                        "reason": "polarity_or_numeric",
                        "score_after": adjusted[penalized],
                    }
                )
        return adjusted, events

    def _polarity(self, text: str) -> int:
        p, n = len(_POS.findall(text)), len(_NEG.findall(text))
        if p > n:
            return 1
        if n > p:
            return -1
        return 0

    def _numeric_conflict(self, a: str, b: str) -> bool:
        na, nb = _NUMERIC.findall(a), _NUMERIC.findall(b)
        if not na or not nb:
            return False
        try:
            va, ua = float(na[0][0]), na[0][1].lower()
            vb, ub = float(nb[0][0]), nb[0][1].lower()
            if ua != ub:
                return False
            return abs(va - vb) / max(abs(va), abs(vb), 1e-9) > 0.3
        except (ValueError, IndexError):
            return False


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
