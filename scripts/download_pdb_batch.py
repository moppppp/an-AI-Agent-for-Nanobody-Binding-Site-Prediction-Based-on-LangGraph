#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch download PDB from RCSB (NanoKGAT parquet / id list)."""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RCSB_URL = "https://files.rcsb.org/download/{pdb_id}.pdb"
_PDB_RE = re.compile(r"^[a-z0-9]{4}$", re.I)


def _normalize_pdb_id(raw: str) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().lower().replace(".pdb", "").replace(".ent", "")
    if not s:
        return None
    s = s.split()[0]
    return s if len(s) == 4 and _PDB_RE.match(s) else None


def ids_from_parquet(path: Path) -> set[str]:
    import pandas as pd

    df = pd.read_parquet(path)
    ids: set[str] = set()

    preferred = ("PDB", "pdb", "pdb_id", "PDB_ID")
    for col in preferred:
        if col in df.columns:
            for v in df[col].dropna().astype(str):
                pid = _normalize_pdb_id(v)
                if pid:
                    ids.add(pid)

    combo = "PDB/ nano_chain/ antigen_chain"
    if combo in df.columns:
        for v in df[combo].dropna().astype(str):
            parts = v.split()
            if parts:
                pid = _normalize_pdb_id(parts[0])
                if pid:
                    ids.add(pid)

    for col in df.columns:
        if col in preferred or col == combo:
            continue
        if "pdb" not in str(col).lower():
            continue
        for v in df[col].dropna().astype(str):
            pid = _normalize_pdb_id(v)
            if pid:
                ids.add(pid)

    return ids


def ids_from_text_file(path: Path) -> set[str]:
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pid = _normalize_pdb_id(line.split(",")[0])
        if pid:
            ids.add(pid)
    return ids


def collect_ids(*, parquet_files: list[Path], parquet_dir: Path | None, ids_file: Path | None) -> list[str]:
    found: set[str] = set()
    if ids_file and ids_file.is_file():
        found |= ids_from_text_file(ids_file)
    for p in parquet_files:
        if p.is_file():
            found |= ids_from_parquet(p)
    if parquet_dir and parquet_dir.is_dir():
        for p in sorted(parquet_dir.glob("**/*.parquet")):
            found |= ids_from_parquet(p)
    return sorted(found)


def download_one(pdb_id: str, out_dir: Path, session: requests.Session, timeout: int) -> tuple[bool, str]:
    dest = out_dir / f"{pdb_id.lower()}.pdb"
    if dest.is_file() and dest.stat().st_size > 100:
        return True, "cached"
    try:
        r = session.get(RCSB_URL.format(pdb_id=pdb_id.upper()), timeout=timeout)
        if r.status_code == 404:
            return False, "404"
        r.raise_for_status()
        if "ATOM" not in r.text and "HETATM" not in r.text:
            return False, "no_atoms"
        dest.write_text(r.text, encoding="utf-8")
        return True, "ok"
    except Exception as exc:
        return False, str(exc)[:120]


def main() -> None:
    ap = argparse.ArgumentParser(description="从 RCSB 批量下载 PDB")
    ap.add_argument("--parquet", action="append", default=[])
    ap.add_argument("--parquet-dir", type=Path, default=None)
    ap.add_argument("--ids-file", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "pdb_nanokgat")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=0.15)
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    parquet_files = [Path(p) for p in args.parquet]
    ids = collect_ids(
        parquet_files=parquet_files,
        parquet_dir=args.parquet_dir,
        ids_file=args.ids_file,
    )
    if not ids:
        raise SystemExit("未解析到 PDB ID，请检查 parquet 路径与列名（PDB 或 PDB/ nano_chain/ antigen_chain）")
    if args.limit > 0:
        ids = ids[: args.limit]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"下载 {len(ids)} 个 PDB -> {out_dir}")

    session = requests.Session()
    session.headers.update({"User-Agent": "nanobody-agent-eval/1.0 (academic)"})
    ok = fail = 0
    errors: list[dict] = []
    t0 = time.time()
    for i, pid in enumerate(ids, 1):
        success, msg = download_one(pid, out_dir, session, args.timeout)
        if success:
            ok += 1
        else:
            fail += 1
            errors.append({"pdb_id": pid, "error": msg})
        if i % 10 == 0 or i == len(ids):
            print(f"  [{i}/{len(ids)}] ok={ok} fail={fail} last={pid}")
        if args.delay > 0 and i < len(ids):
            time.sleep(args.delay)

    report = {
        "total_ids": len(ids),
        "success": ok,
        "failed": fail,
        "success_rate_pct": round(100.0 * ok / len(ids), 2) if ids else 0,
        "out_dir": str(out_dir),
        "elapsed_seconds": round(time.time() - t0, 1),
        "pdb_ids": ids,
        "sample_errors": errors[:30],
    }
    (out_dir / "download_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "pdb_ids.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "pdb_ids"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
