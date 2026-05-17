#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from common import DATASETS, OUTPUTS, dump_json, get_retriever, lift, load_jsonl, setup_import_path


def _hit(retriever, query: str, needle: str, top_k: int, dense_only: bool) -> bool:
    if dense_only:
        old = retriever.settings.hybrid_dense_weight
        retriever.settings = retriever.settings.model_copy(update={"hybrid_dense_weight": 1.0})
        try:
            hits = retriever.retrieve(query, top_k=top_k)
        finally:
            retriever.settings = retriever.settings.model_copy(update={"hybrid_dense_weight": old})
    else:
        hits = retriever.retrieve(query, top_k=top_k)
    nl = needle.lower()
    return any(nl in (h.get("text") or "").lower() for h in hits)


def eval_retrieval(labels: Path | None = None) -> dict:
    setup_import_path()
    retriever, _ = get_retriever()
    rows = load_jsonl(labels or DATASETS / "retrieval_labels.jsonl")
    if not rows:
        raise SystemExit(f"Missing labels: {DATASETS / 'retrieval_labels.jsonl'}")

    h1 = d1 = h3 = d3 = 0
    for row in rows:
        q, needle = row["query"], row["needle"]
        h1 += int(_hit(retriever, q, needle, 1, False))
        d1 += int(_hit(retriever, q, needle, 1, True))
        h3 += int(_hit(retriever, q, needle, 3, False))
        d3 += int(_hit(retriever, q, needle, 3, True))

    n = len(rows)
    result = {
        "queries": n,
        "hybrid_hit_at_1": round(h1 / n, 4),
        "dense_hit_at_1": round(d1 / n, 4),
        "hybrid_hit_at_3": round(h3 / n, 4),
        "dense_hit_at_3": round(d3 / n, 4),
        "lift_hit_at_1_pct": round(lift(h1, d1), 2),
    }
    dump_json(OUTPUTS / "retrieval_report.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--labels", type=Path, default=None)
    eval_retrieval(p.parse_args().labels)


if __name__ == "__main__":
    main()
