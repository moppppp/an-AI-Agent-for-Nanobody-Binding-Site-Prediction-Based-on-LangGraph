#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import random
import string
import sys
import tempfile
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from common import OUTPUTS, dump_json, pct, setup_import_path
_AA = ["GLY", "ALA", "VAL", "LEU", "SER"]


def _write_pdb(path: Path, n: int, chain: str) -> None:
    lines = ["HEADER    TEST"]
    for i in range(1, n + 1):
        r = _AA[i % len(_AA)]
        lines.append(
            f"ATOM  {i:5d}  CA  {r} {chain}{i:4d}    "
            f"{10 + i:8.3f}{20:8.3f}{30:8.3f}  1.00  0.00           C"
        )
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def eval_pdb(*, pdb_dir: Path | None, generate: int, seed: int) -> dict:
    setup_import_path()
    from nanobody_agent.pdb_handler import parse_pdb_file

    ok = total = 0
    errors: list[dict] = []

    if pdb_dir:
        files = list(pdb_dir.glob("**/*.pdb")) + list(pdb_dir.glob("**/*.ent"))
        total = len(files)
        for f in files:
            try:
                parse_pdb_file(f)
                ok += 1
            except Exception as exc:
                errors.append({"file": str(f), "error": str(exc)})
    else:
        rng = random.Random(seed)
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(generate):
                p = Path(tmp) / f"test_{i:05d}.pdb"
                _write_pdb(p, rng.randint(5, 40), rng.choice(string.ascii_uppercase[:4]))
                total += 1
                try:
                    parse_pdb_file(p)
                    ok += 1
                except Exception as exc:
                    errors.append({"file": p.name, "error": str(exc)})

    result = {
        "total_files": total,
        "success_count": ok,
        "success_rate_pct": round(pct(ok, total), 2),
        "sample_errors": errors[:10],
    }
    dump_json(OUTPUTS / "pdb_report.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dir", type=Path, default=None)
    p.add_argument("--generate", type=int, default=100)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    eval_pdb(pdb_dir=a.dir, generate=a.generate, seed=a.seed)


if __name__ == "__main__":
    main()
