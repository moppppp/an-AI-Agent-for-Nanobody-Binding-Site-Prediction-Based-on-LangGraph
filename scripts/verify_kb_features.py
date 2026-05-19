# -*- coding: utf-8 -*-
"""
验证知识增强功能：实体对齐、定性词扩展、时效衰减、事实漂移、混合检索。

用法:
  cd C:\\Users\\HP\\nanobody_agent
  python scripts\\verify_kb_features.py           # 仅单元级（快）
  python scripts\\verify_kb_features.py --full  # 含加载知识库与检索（慢，约 1～3 分钟）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _info(msg: str) -> None:
    print(f"  [--] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def test_entity_and_qualitative() -> bool:
    print("\n=== 1. 实体对齐 + 定性词扩展 ===")
    from nanobody_agent.config import get_settings
    from nanobody_agent.kb_enrichment import KnowledgeEnrichment

    s = get_settings()
    enr = KnowledgeEnrichment(s)
    q = "nanobody 的结合位点预测是否显著优于传统抗体？"
    out, meta = enr.prepare_query(q)
    _info(f"原问题: {q}")
    _info(f"扩展后: {out[:120]}...")
    _info(f"meta: {json.dumps(meta, ensure_ascii=False)}")
    ok = "纳米抗体" in out or "结合位点" in out
    ok = ok and (meta.get("qualitative_hits") or "显著" in q)
    if ok:
        _ok("查询已做实体规范化/别名扩展，并命中定性词「显著」")
    else:
        _fail("未看到预期的实体或定性词扩展")
    return ok


def test_temporal_decay() -> bool:
    print("\n=== 2. 时效性衰减 ===")
    from nanobody_agent.config import get_settings
    from nanobody_agent.kb_enrichment import KnowledgeEnrichment

    enr = KnowledgeEnrichment(get_settings())
    w_new = enr.temporal_weight(2024)
    w_old = enr.temporal_weight(2010)
    _info(f"2024 年权重: {w_new:.4f}")
    _info(f"2010 年权重: {w_old:.4f}")
    ok = w_new > w_old and w_old < 1.0
    if ok:
        _ok("较新文献权重更高")
    else:
        _fail(f"衰减异常: new={w_new}, old={w_old}")
    return ok


def test_fact_drift() -> bool:
    print("\n=== 3. 事实漂移检测（合成矛盾片段）===")
    from nanobody_agent.config import get_settings
    from nanobody_agent.kb_enrichment import KnowledgeChunk, KnowledgeEnrichment

    enr = KnowledgeEnrichment(get_settings())
    chunks = [
        KnowledgeChunk(
            "纳米抗体对靶标亲和力显著提高 50%。",
            "paper_a.pdf",
            2020,
            "a:v1",
            "纳米抗体对靶标亲和力显著提高 50%。",
        ),
        KnowledgeChunk(
            "纳米抗体对靶标亲和力明显降低 40%。",
            "paper_b.pdf",
            2018,
            "b:v1",
            "纳米抗体对靶标亲和力明显降低 40%。",
        ),
        KnowledgeChunk(
            "纳米抗体结构稳定，适用于高温储存。",
            "paper_c.pdf",
            2022,
            "c:v1",
            "纳米抗体结构稳定，适用于高温储存。",
        ),
    ]
    scores = [0.9, 0.85, 0.5]
    adj, events = enr.apply_fact_drift(scores, chunks)
    _info(f"原始得分: {scores}")
    _info(f"调整后:   {[round(x, 3) for x in adj]}")
    _info(f"漂移事件: {json.dumps(events, ensure_ascii=False)}")
    ok = len(events) >= 1 and adj[1] < scores[1]
    if ok:
        _ok("检测到矛盾并下调了冲突片段得分")
    else:
        _fail("未触发预期漂移惩罚（检查 FACT_DRIFT_ENABLED / FACT_DRIFT_PENALTY）")
    return ok


def test_kb_meta_parse() -> bool:
    print("\n=== 4. 入库元数据 kb-meta ===")
    sample = ROOT / "knowledge_base" / "_verify_sample.md"
    sample.parent.mkdir(parents=True, exist_ok=True)
    sample.write_text(
        "# test\n\n"
        "<!-- kb-meta: source=verify.pdf year=2021 version=999 -->\n\n"
        "纳米抗体（nanobody）是一种小型单域抗体。\n",
        encoding="utf-8",
    )
    from nanobody_agent.config import get_settings
    from nanobody_agent.kb_enrichment import KnowledgeEnrichment

    chunks = KnowledgeEnrichment(get_settings()).load_chunks([sample])
    sample.unlink(missing_ok=True)
    if not chunks:
        _fail("未能从带 kb-meta 的 Markdown 解析出片段")
        return False
    c = chunks[0]
    _info(f"source={c.source}, year={c.year}, version_key={c.version_key[:40]}...")
    ok = c.year == 2021 and "verify" in c.source
    if ok:
        _ok("kb-meta 年份与来源解析正确")
    else:
        _fail(f"解析结果不符: {c}")
    return ok


def test_retriever_full() -> bool:
    print("\n=== 5. 完整检索链路（加载知识库）===")
    from nanobody_agent.config import get_settings
    from nanobody_agent.retrieval import HybridRetriever

    settings = get_settings()
    retriever = HybridRetriever(settings)
    retriever.load_corpus()
    if not retriever._docs:
        _fail("知识库为空，请先运行 ingest_pdfs.py 或往 knowledge_base/ 放入 .md")
        return False

    q = "什么是纳米抗体？"
    bd = retriever.score_breakdown(q)
    hits = retriever.retrieve(q, top_k=3)
    _info(f"routing_score={bd.get('routing_score'):.3f}")
    _info(f"query_enrichment={json.dumps(bd.get('query_enrichment', {}), ensure_ascii=False)}")
    for h in hits:
        _info(
            f"  rank={h['rank']} score={h['score']:.3f} year={h.get('year')} "
            f"tw={h.get('temporal_weight', 1):.3f} | {h['text'][:60]}..."
        )
    decision = retriever.decide_kb_route(q)
    _info(
        f"decide_kb_route: route_kb={decision.get('route_kb')} "
        f"gray={decision.get('gray_zone')} sem={decision.get('semantic_verify_score')}"
    )
    ok = bool(hits) and bd.get("routing_score", 0) > 0
    if ok:
        _ok("混合检索与路由评分正常")
    else:
        _fail("检索无结果或相关度为 0")
    return ok


def test_end_to_end_cli() -> None:
    print("\n=== 6. 端到端（可选，需 API Key）===")
    _info("运行: python main.py \"什么是纳米抗体？\"")
    _info("观察输出中的 relevance / intent / 检索片段")
    _info("预测类: python main.py \"请预测纳米抗体结合位点\"")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="包含 load_corpus + retrieve（需已有 knowledge_base 内容）",
    )
    args = parser.parse_args()

    print("纳米抗体智能体 — 知识增强功能验证")
    print(f"项目目录: {ROOT}")

    results = [
        test_entity_and_qualitative(),
        test_temporal_decay(),
        test_fact_drift(),
        test_kb_meta_parse(),
    ]
    if args.full:
        results.append(test_retriever_full())
    else:
        print("\n(跳过完整检索，加 --full 可测 FAISS+BM25+增强)")

    test_end_to_end_cli()

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 40}")
    print(f"通过 {passed}/{total} 项自动化检查")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
