#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot: download 20 PDB from user's parquet0218 files (情况 A)."""
from pathlib import Path
import subprocess
import sys

BASE = Path(
    r"C:\Users\HP\Desktop\Analysis-and-evaluation-of-GNN-algorithms-on-multiple-antibody-binding-site-datasets-main"
    r"\Analysis-and-evaluation-of-GNN-algorithms-on-multiple-antibody-binding-site-datasets-main"
    r"\parquet0218"
)
PARQUETS = [
    BASE / "train_processed_serialized.parquet",
    BASE / "val_processed_serialized.parquet",
    BASE / "test_processed_serialized.parquet",
]
OUT = Path(__file__).resolve().parents[1] / "data" / "pdb_test_20"
SCRIPT = Path(__file__).resolve().parent / "download_pdb_batch.py"


def main() -> None:
    for p in PARQUETS:
        if not p.is_file():
            print("MISSING:", p)
            sys.exit(1)
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--limit",
        "20",
        "--out",
        str(OUT),
    ]
    for p in PARQUETS:
        cmd.extend(["--parquet", str(p)])
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd)


if __name__ == "__main__":
    main()
