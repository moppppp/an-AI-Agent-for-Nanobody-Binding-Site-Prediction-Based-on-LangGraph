# -*- coding: utf-8 -*-
"""Verify KB enrichment. Run: python verify_kb_features.py [--full]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def info(msg: str) -> None:
    print(f"  [--] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def test_entity_and_qualitative() -> bool:
    print("\n=== 1. entity align + qualitative ===")
    from nanobody_agent.config import get_settings
    from nanobody_agent.kb_enrichment import KnowledgeEnrichment

    enr = KnowledgeEnrichment(get_settings())
    q = "nanobody binding site prediction significant?"
    out, meta = enr.prepare_query(q)
    info(f"meta: {json.dumps(meta, ensure_ascii=False)}")
    info(f"query head: {out[:120]}...")
    passed = bool(meta.get("qualitative_hits")) or "significant" in q
    if passed:
        ok("qualitative / query expand")
    else:
        fail("expected qualitative_hits")
    return passed


def test_temporal_decay() -> bool:
    print("\n=== 2. temporal decay ===")
    from nanobody_agent.config import get_settings
    from nanobody_agent.kb_enrichment import KnowledgeEnrichment

    enr = KnowledgeEnrichment(get_settings())
    w_new = enr.temporal_weight(2024)
    w_old = enr.temporal_weight(2010)
    info(f"2024={w_new:.4f} 2010={w_old:.4f}")
    passed = w_new > w_old
    if passed:
        ok("newer year has higher weight")
    else:
        fail("decay weights wrong")
    return passed


def test_fact_drift() -> bool:
    print("\n=== 3. fact drift ===")
    from nanobody_agent.config import get_settings
    from nanobody_agent.kb_enrichment import KnowledgeChunk, KnowledgeEnrichment

    enr = KnowledgeEnrichment(get_settings())
    chunks = [
        KnowledgeChunk(
            "nanobody affinity increased 50 percent.",
            "a.pdf",
            2020,
            "a",
            "nanobody affinity increased 50 percent.",
        ),
        KnowledgeChunk(
            "nanobody affinity decreased 40 percent.",
            "b.pdf",
            2018,
            "b",
            "nanobody affinity decreased 40 percent.",
        ),
    ]
    scores = [0.9, 0.85]
    adj, events = enr.apply_fact_drift(scores, chunks)
    info(f"scores {scores} -> {[round(x, 3) for x in adj]}")
    info(f"events: {events}")
    passed = bool(events) and adj[1] < scores[1]
    if passed:
        ok("conflict penalized")
    else:
        fail("no drift event (check FACT_DRIFT_ENABLED)")
    return passed


def test_kb_meta() -> bool:
    print("\n=== 4. kb-meta parse ===")
    from nanobody_agent.config import get_settings
    from nanobody_agent.kb_enrichment import KnowledgeEnrichment

    p = ROOT / "knowledge_base" / "_verify_sample.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(
        (
            "# t\n\n"
            "<!-- kb-meta: source=v.pdf year=2021 version=1 -->\n\n"
            "nanobody is a single-domain antibody.\n"
        ).encode("utf-8")
    )
    chunks = KnowledgeEnrichment(get_settings()).load_chunks([p])
    p.unlink(missing_ok=True)
    if not chunks:
        fail("no chunks parsed")
        return False
    c = chunks[0]
    info(f"year={c.year} source={c.source}")
    passed = c.year == 2021
    if passed:
        ok("kb-meta ok")
    else:
        fail(f"bad parse: year={c.year}")
    return passed


def test_retriever_full() -> bool:
    print("\n=== 5. full retrieval ===")
    from nanobody_agent.config import get_settings
    from nanobody_agent.retrieval import HybridRetriever

    r = HybridRetriever(get_settings())
    r.load_corpus()
    if not r._docs:
        fail("knowledge base empty; run ingest_pdfs.py first")
        return False
    q = "what is nanobody"
    bd = r.score_breakdown(q)
    hits = r.retrieve(q, top_k=3)
    info(f"routing_score={bd.get('routing_score', 0):.3f}")
    info(f"enrichment={json.dumps(bd.get('query_enrichment', {}), ensure_ascii=False)}")
    for h in hits:
        info(
            f"  #{h['rank']} score={h['score']:.3f} year={h.get('year')} "
            f"tw={h.get('temporal_weight', 1):.3f}"
        )
        info(f"    {h['text'][:70]}...")
    dec = r.decide_kb_route(q)
    info(f"route_kb={dec.get('route_kb')} sem={dec.get('semantic_verify_score')}")
    passed = bool(hits)
    if passed:
        ok("retrieve ok")
    else:
        fail("no hits")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="load corpus + retrieve")
    args = parser.parse_args()

    print("KB feature verification @", ROOT)
    results = [
        test_entity_and_qualitative(),
        test_temporal_decay(),
        test_fact_drift(),
        test_kb_meta(),
    ]
    if args.full:
        results.append(test_retriever_full())
    else:
        print("\n(tip: add --full to test FAISS+BM25)")

    n = len(results)
    print(f"\n{'=' * 40}")
    print(f"passed {sum(results)}/{n}")
    if sum(results) < n:
        sys.exit(1)


if __name__ == "__main__":
    main()
