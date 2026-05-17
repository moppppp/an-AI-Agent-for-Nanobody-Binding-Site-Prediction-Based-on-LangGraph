#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from common import DATASETS, OUTPUTS, dump_json
from eval_corpus import eval_corpus
from eval_hallucination import eval_hallucination
from eval_pdb import eval_pdb
from eval_retrieval import eval_retrieval
from eval_routing import eval_routing


def run_all(*, pdb_sample: int, invoke_llm: bool) -> None:
    t0 = time.time()
    routing = eval_routing(None)
    retrieval = eval_retrieval(None)
    halluc = eval_hallucination(invoke_llm=invoke_llm, labels=None)
    pdb = eval_pdb(pdb_dir=None, generate=pdb_sample, seed=42)
    corpus = eval_corpus()

    summary = {
        "routing": {k: v for k, v in routing.items() if k != "details"},
        "retrieval": retrieval,
        "hallucination": halluc,
        "pdb": pdb,
        "corpus": corpus,
        "elapsed_seconds": round(time.time() - t0, 1),
    }

    ref_path = DATASETS / "reference_metrics.json"
    if ref_path.is_file():
        ref = json.loads(ref_path.read_text(encoding="utf-8"))
        summary["reference_comparison"] = {
            "routing_accuracy_pct": {
                "measured": summary["routing"].get("agent_routing_accuracy_pct"),
                "reference": ref.get("routing_accuracy_pct"),
            },
            "routing_lift_pct": {
                "measured": summary["routing"].get("lift_vs_fixed_pct"),
                "reference": ref.get("routing_lift_vs_fixed_retrieval_pct"),
            },
            "retrieval_lift_pct": {
                "measured": summary["retrieval"].get("lift_hit_at_1_pct"),
                "reference": ref.get("hybrid_retrieval_lift_vs_dense_only_pct"),
            },
            "hallucination_rate_pct": {
                "measured": summary["hallucination"].get("hallucination_proxy_rate_pct"),
                "reference": ref.get("hallucination_rate_pct"),
            },
            "pdb_success_rate_pct": {
                "measured": summary["pdb"].get("success_rate_pct"),
                "reference": ref.get("pdb_upload_success_rate_pct"),
            },
            "meta": ref.get("meta"),
        }

    dump_json(OUTPUTS / "benchmark_summary.json", summary)
    print("\nWrote", OUTPUTS / "benchmark_summary.json")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--pdb-sample", type=int, default=100)
    p.add_argument("--invoke-llm", action="store_true")
    a = p.parse_args()
    run_all(pdb_sample=a.pdb_sample, invoke_llm=a.invoke_llm)


if __name__ == "__main__":
    main()
