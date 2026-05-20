from __future__ import annotations

import re
from pathlib import Path

_AA3_TO_1 = {
    "ALA": "A",
    "CYS": "C",
    "ASP": "D",
    "GLU": "E",
    "PHE": "F",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LYS": "K",
    "LEU": "L",
    "MET": "M",
    "ASN": "N",
    "PRO": "P",
    "GLN": "Q",
    "ARG": "R",
    "SER": "S",
    "THR": "T",
    "VAL": "V",
    "TRP": "W",
    "TYR": "Y",
}


def parse_pdb_file(path: Path, chain: str | None = None) -> dict:
    """
    Minimal PDB parser: sequence from ATOM records, residue list for visualization.
    Returns dict with sequence, residues, chain_id, atom_count.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(str(path))

    chosen_chain = (chain or "").strip().upper() or None
    seen: dict[tuple[str, int, str], str] = {}
    atom_count = 0

    from nanobody_agent.tools.io_utils import read_text_auto

    for line in read_text_auto(path).splitlines():
        if not line.startswith("ATOM"):
            continue
        atom_count += 1
        if len(line) < 26:
            continue
        ch = line[21].strip() or "A"
        if chosen_chain and ch != chosen_chain:
            continue
        resname = line[17:20].strip().upper()
        try:
            resseq = int(line[22:26])
        except ValueError:
            continue
        icode = line[26].strip() if len(line) > 26 else ""
        aa = _AA3_TO_1.get(resname, "X")
        key = (ch, resseq, icode)
        if key not in seen:
            seen[key] = aa

    if not seen:
        raise ValueError("PDB 中未解析到 ATOM 残基，请检查文件或指定链 ID")

    keys = sorted(seen.keys(), key=lambda k: (k[0], k[1], k[2]))
    sequence = "".join(seen[k] for k in keys)
    residues = [
        {"chain": k[0], "resseq": k[1], "icode": k[2], "aa": seen[k], "label": f"{k[0]}{k[1]}{seen[k]}"}
        for k in keys
    ]
    chain_id = chosen_chain or keys[0][0]
    return {
        "sequence": sequence,
        "residues": residues,
        "chain_id": chain_id,
        "atom_count": atom_count,
        "source_path": str(path),
    }
