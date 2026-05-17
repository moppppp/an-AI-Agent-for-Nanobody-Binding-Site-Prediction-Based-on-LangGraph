#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评测套件入口。用法: python scripts/eval_suite.py init-datasets"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = Path(__file__).resolve().parent / "eval"


def _py(script: str, *args: str) -> None:
    subprocess.check_call([sys.executable, str(EVAL / script), *args], cwd=str(ROOT))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=[
        "init-datasets", "run-all", "routing", "retrieval",
        "hallucination", "pdb", "corpus", "user-study",
    ])
    p.add_argument("rest", nargs=argparse.REMAINDER)
    p.add_argument("--pdb-sample", type=int, default=100)
    p.add_argument("--invoke-llm", action="store_true")
    p.add_argument("--dir", type=Path, default=None)
    args, rest = p.parse_known_args()
    if args.cmd == "init-datasets":
        _py("seed_datasets.py")
    elif args.cmd == "run-all":
        _py("seed_datasets.py")
        x = ["--pdb-sample", str(args.pdb_sample)]
        if args.invoke_llm:
            x.append("--invoke-llm")
        _py("run_benchmarks.py", *x)
    elif args.cmd == "routing":
        _py("eval_routing.py")
    elif args.cmd == "retrieval":
        _py("eval_retrieval.py")
    elif args.cmd == "hallucination":
        _py("eval_hallucination.py", *(["--invoke-llm"] if args.invoke_llm else []))
    elif args.cmd == "pdb":
        _py("eval_pdb.py", *(["--dir", str(args.dir)] if args.dir else ["--generate", str(args.pdb_sample)]))
    elif args.cmd == "corpus":
        _py("eval_corpus.py")
    else:
        _py("user_study.py", *rest)


if __name__ == "__main__":
    main()
