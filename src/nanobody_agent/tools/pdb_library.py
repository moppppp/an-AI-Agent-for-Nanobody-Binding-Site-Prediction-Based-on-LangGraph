from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from nanobody_agent.config import Settings
from nanobody_agent.pdb_handler import parse_pdb_file
from nanobody_agent.tools.io_utils import read_text_auto


def _ca_coords(path: Path, chain: str | None) -> list[tuple[str, int, str, float, float, float]]:
    coords: list[tuple[str, int, str, float, float, float]] = []
    chosen = (chain or "").strip().upper() or None
    for line in read_text_auto(path).splitlines():
        if not line.startswith("ATOM") or len(line) < 27:
            continue
        if line[12:16].strip() != "CA":
            continue
        ch = line[21].strip() or "A"
        if chosen and ch != chosen:
            continue
        try:
            resseq = int(line[22:26])
        except ValueError:
            continue
        icode = line[26].strip() if len(line) > 26 else ""
        if len(line) >= 54:
            x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
        else:
            x, y, z = 0.0, 0.0, 0.0
        coords.append((ch, resseq, icode, x, y, z))
    return coords


def _meta_from_file(path: Path, chain: str | None) -> dict[str, Any]:
    try:
        return parse_pdb_file(path, chain=chain)
    except ValueError:
        all_ca = _ca_coords(path, chain)
        if not all_ca:
            raise
        ch = (chain or all_ca[0][0]).strip().upper()
        residues = [
            {"chain": c[0], "resseq": c[1], "icode": c[2], "label": f"{c[0]}{c[1]}"}
            for c in all_ca
        ]
        return {
            "chain_id": ch,
            "sequence": "X" * len(residues),
            "residues": residues,
            "atom_count": len(all_ca),
        }


def _contacts(
    coords_a: list[tuple],
    coords_b: list[tuple],
    cutoff: float = 5.0,
) -> list[dict]:
    out: list[dict] = []
    for ca in coords_a:
        for cb in coords_b:
            d = math.sqrt(
                (ca[3] - cb[3]) ** 2 + (ca[4] - cb[4]) ** 2 + (ca[5] - cb[5]) ** 2
            )
            if d <= cutoff:
                out.append(
                    {
                        "a": f"{ca[0]}{ca[1]}{ca[2]}",
                        "b": f"{cb[0]}{cb[1]}{cb[2]}",
                        "distance_A": round(d, 2),
                    }
                )
    return out[:200]


def lookup_pdb(
    settings: Settings,
    *,
    pdb_id: str,
    chain: str | None = None,
    partner_chain: str | None = None,
) -> dict[str, Any]:
    """Local PDB library: ID lookup + residue contact parsing."""
    lib = settings.pdb_library_dir.resolve()
    lib.mkdir(parents=True, exist_ok=True)
    pid = pdb_id.strip().upper()
    candidates = list(lib.glob(f"{pid}.pdb")) + list(lib.glob(f"{pid.lower()}.pdb"))
    uploads = settings.uploads_dir / f"{pid}.pdb"
    if uploads.is_file():
        candidates.append(uploads)
    if not candidates:
        return {
            "found": False,
            "pdb_id": pid,
            "hint": f"Place {pid}.pdb under {lib} or uploads/",
        }
    path = candidates[0]
    meta = _meta_from_file(path, chain=chain)
    result: dict[str, Any] = {
        "found": True,
        "pdb_id": pid,
        "path": str(path),
        "chain_id": meta["chain_id"],
        "sequence_length": len(meta["sequence"]),
        "residue_count": len(meta["residues"]),
        "atom_count": meta["atom_count"],
    }
    if partner_chain:
        ca = _ca_coords(path, chain or meta["chain_id"])
        cb = _ca_coords(path, partner_chain)
        result["contacts"] = _contacts(ca, cb)
        result["partner_chain"] = partner_chain
    return result


def parse_pdb_query(user_query: str) -> dict[str, Any]:
    pdb_id = None
    m = re.search(r"\b([1-9][A-Za-z0-9]{3})\b", user_query)
    if m:
        pdb_id = m.group(1).upper()
    chain = None
    m2 = re.search(r"链\s*([A-Za-z])", user_query)
    if m2:
        chain = m2.group(1).upper()
    partner = None
    m3 = re.search(r"与\s*链\s*([A-Za-z])", user_query)
    if m3:
        partner = m3.group(1).upper()
    return {"pdb_id": pdb_id, "chain": chain, "partner_chain": partner}
