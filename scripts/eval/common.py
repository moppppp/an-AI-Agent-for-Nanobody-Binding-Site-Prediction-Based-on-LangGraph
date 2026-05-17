# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
# scripts/eval -> parents[0]=scripts, parents[1]=project root
ROOT = EVAL_DIR.parents[1]
SRC = ROOT / "src"
DATASETS = EVAL_DIR / "datasets"
OUTPUTS = ROOT / "outputs" / "eval"


def setup_import_path() -> None:
    src = str(SRC.resolve())
    if src not in sys.path:
        sys.path.insert(0, src)


# Subprocess entrypoints import common before calling setup_import_path()
setup_import_path()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def pct(n: float, d: float) -> float:
    return 0.0 if d <= 0 else 100.0 * n / d


def lift(a: float, b: float) -> float:
    return 0.0 if b <= 0 else 100.0 * (a - b) / b


def get_retriever():
    setup_import_path()
    from nanobody_agent.config import get_settings
    from nanobody_agent.retrieval import HybridRetriever

    s = get_settings()
    r = HybridRetriever(s)
    r.load_corpus()
    return r, s


def classify_router_state(query: str, retriever, _settings) -> dict[str, Any]:
    from nanobody_agent.llm_utils import classify_intent_rules

    if not query.strip():
        return {
            "user_query": query,
            "relevance": 0.0,
            "semantic_verify_score": None,
            "route_kb": False,
            "reject": True,
            "intent": "unknown",
        }
    d = retriever.decide_kb_route(query)
    return {
        "user_query": query,
        "relevance": float(d.get("relevance") or 0.0),
        "semantic_verify_score": d.get("semantic_verify_score"),
        "route_kb": bool(d.get("route_kb")),
        "reject": bool(d.get("reject")),
        "intent": classify_intent_rules(query) or "unknown",
    }


def agent_graph_route(state: dict[str, Any], threshold: float) -> str:
    from nanobody_agent.llm_utils import classify_intent_rules

    q = state.get("user_query") or ""
    rule = classify_intent_rules(q) or state.get("intent")
    if rule in ("prediction", "visualization"):
        return "nanokgat"
    if state.get("reject"):
        return "reject"
    if state.get("route_kb"):
        return "kb"
    if rule in ("definition", "comparison") and float(state.get("relevance") or 0) >= 0.5:
        sem = state.get("semantic_verify_score")
        if sem is None or float(sem) >= 0.45:
            return "kb"
    return "kb" if float(state.get("relevance") or 0) >= threshold else "direct"


def fixed_retrieval_route(query: str, retriever, threshold: float = 0.65) -> str:
    rel = float(retriever.score_breakdown(query).get("routing_score") or 0)
    return "kb" if rel >= threshold else "direct"
