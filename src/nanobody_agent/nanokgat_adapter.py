from __future__ import annotations

import importlib
import json
import random
import uuid
from pathlib import Path
from typing import Any, Callable

from nanobody_agent.config import Settings
from nanobody_agent.sequence_embed import extract_sequence


def _load_predict_fn(settings: Settings) -> Callable[..., dict[str, Any]] | None:
    if not settings.nanokgat_python_module or not settings.nanokgat_predict_callable:
        return None
    mod = importlib.import_module(settings.nanokgat_python_module)
    fn = getattr(mod, settings.nanokgat_predict_callable, None)
    if fn is None or not callable(fn):
        return None
    return fn


def _stub_probs_and_attention(seq_len: int, hot_indices: list[int]) -> tuple[dict[str, float], list[dict]]:
    probs: dict[str, float] = {}
    attn: list[dict] = []
    for i in range(min(seq_len, 120)):
        p = 0.05 + (0.75 if i in hot_indices else 0.0) + random.random() * 0.08
        probs[str(i + 1)] = round(min(0.99, p), 4)
        attn.append({"residue_index": i + 1, "weight": round(p, 4)})
    attn.sort(key=lambda x: -x["weight"])
    return probs, attn[:15]


def run_nanokgat(
    user_query: str,
    settings: Settings,
    *,
    sequence: str | None = None,
    pdb_path: str | None = None,
    pdb_meta: dict | None = None,
) -> dict[str, Any]:
    """
    调用 NanoKGAT。默认 STUB；可传入 sequence / pdb_path。
    返回 residues, residue_probs, attention_weights, confidence, structure_path, session_id
    """
    seq = (sequence or extract_sequence(user_query) or "").upper()
    if pdb_meta and pdb_meta.get("sequence"):
        seq = str(pdb_meta["sequence"])

    if settings.nanokgat_use_stub:
        session_id = uuid.uuid4().hex[:12]
        out_dir = settings.outputs_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        stub_path = out_dir / f"nanokgat_stub_{session_id}.json"

        seq_len = len(seq) if seq else 110
        hot = [31, 49, 99, 25, 92][: max(1, min(5, seq_len // 10 or 1))]
        residue_probs, attention_weights = _stub_probs_and_attention(seq_len, hot)
        residues = [f"H{i}" for i in hot] if not pdb_meta else [
            pdb_meta["residues"][i]["label"]
            for i in hot
            if pdb_meta.get("residues") and i < len(pdb_meta["residues"])
        ] or [f"R{i+1}" for i in hot]

        payload: dict[str, Any] = {
            "session_id": session_id,
            "residues": residues,
            "residue_probs": residue_probs,
            "attention_weights": attention_weights,
            "confidence": 0.82,
            "sequence": seq[:500] if seq else None,
            "structure_path": str(stub_path),
            "pdb_path": pdb_path,
            "notes": "stub prediction; replace with NanoKGAT output",
        }
        stub_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    fn = _load_predict_fn(settings)
    if fn is None:
        raise RuntimeError(
            "NANOKGAT_USE_STUB=false 但未找到可调用函数，请设置 NANOKGAT_PYTHON_MODULE 与 "
            "NANOKGAT_PREDICT_CALLABLE。"
        )
    return fn(user_query, sequence=sequence, pdb_path=pdb_path, pdb_meta=pdb_meta)


def build_pymol_link(session_id: str, settings: Settings) -> str:
    return settings.pymol_viewer_url_template.format(session_id=session_id)
