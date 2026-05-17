from __future__ import annotations

import re
from functools import lru_cache

import numpy as np

_AA_ALPHABET = "ACDEFGHIKLMNPQRSTVWY"
_AA_SET = set(_AA_ALPHABET)
_SEQ_IN_QUERY = re.compile(
    r"(?:序列[是为：:\s]*)?([ACDEFGHIKLMNPQRSTVWY]{8,})",
    re.I,
)


def extract_sequence(text: str) -> str | None:
    t = (text or "").strip()
    if not t:
        return None
    m = _SEQ_IN_QUERY.search(t.replace(" ", "").upper())
    if m:
        seq = "".join(c for c in m.group(1).upper() if c in _AA_SET)
        return seq if len(seq) >= 8 else None
    compact = re.sub(r"[^A-Za-z]", "", t).upper()
    if len(compact) >= 12 and sum(1 for c in compact if c in _AA_SET) / len(compact) > 0.9:
        return compact
    return None


def is_sequence_query(query: str) -> bool:
    return extract_sequence(query) is not None


@lru_cache(maxsize=1)
def _antiberty_runner():
    try:
        from antiberty import AntiBERTyRunner  # type: ignore[import-untyped]

        return AntiBERTyRunner()
    except Exception:
        return None


def embed_sequence(seq: str, dim_hint: int = 384) -> np.ndarray | None:
    seq = "".join(c for c in (seq or "").upper() if c in _AA_SET)
    if len(seq) < 4:
        return None

    runner = _antiberty_runner()
    if runner is not None:
        try:
            emb = runner.embed(seq)
            arr = np.asarray(emb, dtype=np.float64).reshape(-1)
            n = np.linalg.norm(arr)
            return arr / n if n > 1e-12 else arr
        except Exception:
            pass

    vec = np.zeros(dim_hint, dtype=np.float64)
    for i, aa in enumerate(seq):
        vec[ord(aa) % dim_hint] += 1.0
        if i + 2 < len(seq):
            tri = seq[i : i + 3]
            vec[hash(tri) % dim_hint] += 0.5
    n = np.linalg.norm(vec)
    return vec / n if n > 1e-12 else vec
