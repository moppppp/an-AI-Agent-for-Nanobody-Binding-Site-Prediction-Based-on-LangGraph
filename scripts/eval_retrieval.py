#!/usr/bin/env python3
"""Compare hybrid retrieval vs dense-only on a small labeled query set."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# (query, must_contain_substring in top-1 passage)
SAMPLE_QUERIES = [
    ("什么是纳米抗体", "纳米抗体"),
    ("结合位点预测", "结合"),
    ("图神经网络", "图神经"),
    ("AntiBERTy", "AntiBERTy"),
]


def hit_at_1(retriever, query: str, needle: str, dense_only: bool = False) -> bool:
    if dense_only:
        old = retriever.settings.hybrid_dense_weight
        retriever.settings = retriever.settings.model_copy(update={"hybrid_dense_weight": 1.0})
        try:
            hits = retriever.retrieve(query, top_k=1)
        finally:
            retriever.settings = retriever.settings.model_copy(update={"hybrid_dense_weight": old})
    else:
        hits = retriever.retrieve(query, top_k=1)
    if not hits:
        return False
    return needle.lower() in hits[0]["text"].lower()


def main() -> None:
    from nanobody_agent.config import get_settings
    from nanobody_agent.retrieval import HybridRetriever

    settings = get_settings()
    r = HybridRetriever(settings)
    r.load_corpus()

    hybrid_hits = 0
    dense_hits = 0
    for q, needle in SAMPLE_QUERIES:
        h = hit_at_1(r, q, needle, dense_only=False)
        d = hit_at_1(r, q, needle, dense_only=True)
        hybrid_hits += int(h)
        dense_hits += int(d)
        print(f"Q: {q[:30]}  hybrid={h}  dense_only={d}")

    n = len(SAMPLE_QUERIES)
    print(json.dumps({
        "queries": n,
        "hybrid_hit_at_1": hybrid_hits / n,
        "dense_hit_at_1": dense_hits / n,
        "lift": (hybrid_hits - dense_hits) / max(dense_hits, 1),
    }, indent=2))


if __name__ == "__main__":
    main()
