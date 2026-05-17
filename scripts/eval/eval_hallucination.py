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

from common import (
    DATASETS,
    OUTPUTS,
    agent_graph_route,
    classify_router_state,
    dump_json,
    get_retriever,
    load_jsonl,
    pct,
    setup_import_path,
)


def eval_hallucination(*, invoke_llm: bool, labels: Path | None = None) -> dict:
    setup_import_path()
    retriever, settings = get_retriever()
    rows = load_jsonl(labels or DATASETS / "hallucination_checks.jsonl")
    if not rows:
        raise SystemExit(f"Missing labels: {DATASETS / 'hallucination_checks.jsonl'}")

    th = float(settings.kb_relevance_threshold)
    failures = 0
    for row in rows:
        q = row["query"]
        expect = row["expect_route"]
        st = classify_router_state(q, retriever, settings)
        route = agent_graph_route(st, th)
        ok = route == expect

        if expect == "kb" and row.get("needle_in_context"):
            hits = retriever.retrieve(q, top_k=3)
            needle = row["needle_in_context"].lower()
            ok = ok and any(needle in (h.get("text") or "").lower() for h in hits)

        if invoke_llm and expect == "kb":
            try:
                from nanobody_agent.graph import build_app

                out = build_app().invoke({"user_query": q, "session_id": "eval-hallucination"})
                ans = (out.get("final_answer") or "").lower()
                if row.get("require_citation"):
                    ok = ok and ("引用" in ans or "[1]" in ans or "来源" in ans)
                for pat in row.get("forbid_in_answer") or []:
                    if pat and pat.lower() in ans:
                        ok = False
            except Exception:
                ok = False

        failures += int(not ok)

    n = len(rows)
    result = {
        "checks": n,
        "hallucination_proxy_rate_pct": round(pct(failures, n), 2),
        "invoke_llm": invoke_llm,
    }
    dump_json(OUTPUTS / "hallucination_report.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--invoke-llm", action="store_true")
    p.add_argument("--labels", type=Path, default=None)
    a = p.parse_args()
    eval_hallucination(invoke_llm=a.invoke_llm, labels=a.labels)


if __name__ == "__main__":
    main()
