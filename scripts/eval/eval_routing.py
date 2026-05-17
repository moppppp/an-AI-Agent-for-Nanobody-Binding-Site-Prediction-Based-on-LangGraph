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
    fixed_retrieval_route,
    get_retriever,
    lift,
    load_jsonl,
    pct,
    setup_import_path,
)


def eval_routing(labels: Path | None = None) -> dict:
    setup_import_path()
    retriever, settings = get_retriever()
    rows = load_jsonl(labels or DATASETS / "routing_labels.jsonl")
    if not rows:
        raise SystemExit(f"Missing labels: {DATASETS / 'routing_labels.jsonl'}")

    th = float(settings.kb_relevance_threshold)
    agent_ok = fixed_ok = 0
    details = []
    for row in rows:
        q = row["query"]
        exp = row["expected"].lower()
        st = classify_router_state(q, retriever, settings)
        ap = agent_graph_route(st, th)
        fp = fixed_retrieval_route(q, retriever, th)
        am = ap == exp
        fm = (fp == exp) if exp != "reject" else False
        agent_ok += int(am)
        fixed_ok += int(fm)
        details.append({"query": q[:60], "expected": exp, "agent": ap, "fixed": fp, "agent_ok": am})

    n = len(rows)
    result = {
        "labeled_queries": n,
        "agent_routing_accuracy_pct": round(pct(agent_ok, n), 2),
        "fixed_retrieval_accuracy_pct": round(pct(fixed_ok, n), 2),
        "lift_vs_fixed_pct": round(lift(pct(agent_ok, n), pct(fixed_ok, n)), 2),
        "details": details,
    }
    dump_json(OUTPUTS / "routing_report.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--labels", type=Path, default=None)
    eval_routing(p.parse_args().labels)


if __name__ == "__main__":
    main()
