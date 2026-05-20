from __future__ import annotations

import argparse
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage


def main() -> None:
    root = Path(__file__).resolve().parent
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from nanobody_agent.graph import build_app

    parser = argparse.ArgumentParser(description="纳米抗体结合位点预测 LangGraph 智能体")
    parser.add_argument("query", nargs="?", default="", help="用户问题（可省略进入交互）")
    args = parser.parse_args()

    from nanobody_agent.config import get_settings
    from nanobody_agent.conversation_memory import get_conversation_store
    from nanobody_agent.repeat_query_cache import get_repeat_query_cache

    app = build_app()
    settings = get_settings()
    store = get_conversation_store()
    repeat_cache = get_repeat_query_cache(settings)
    cli_session = "cli"

    def run_once(q: str) -> None:
        repeat_consecutive, repeat_total, norm_q = repeat_cache.record_ask(cli_session, q)
        if repeat_cache.should_read_cache(repeat_consecutive, repeat_total, norm_q, cli_session):
            cached = repeat_cache.get_cached(cli_session, norm_q)
            if cached:
                print("--- 路由信息 ---")
                print("route: repeat_query_cache (Redis/内存缓存命中)")
                print("repeat_consecutive:", repeat_consecutive, "repeat_total:", repeat_total)
                print("--- 回答 ---")
                print(cached.get("answer") or "")
                store.get_or_create(cli_session, settings).record_turn(
                    q, cached.get("answer") or "", settings
                )
                return

        session = store.get_or_create(cli_session, settings)
        memory_context = session.build_context_before_turn(settings)
        state = {
            "messages": [HumanMessage(content=q)],
            "user_query": q,
            "memory_context": memory_context,
            "conversation_summary": session.summary,
        }
        out = app.invoke(state)
        session.record_turn(q, out.get("final_answer") or "", settings)
        session.compress(settings)
        if memory_context.strip() or session.summary.strip():
            print("--- 对话记忆 ---")
            if session.summary.strip():
                print("【历史摘要】")
                print(session.summary.strip())
            if memory_context.strip():
                print("【送入模型的上下文】")
                print(memory_context.strip()[:2000])
            print(
                "memory_turns:",
                session.pair_count(),
                "has_summary:",
                bool(session.summary.strip()),
            )
        print("--- 路由信息 ---")
        rel = float(out.get("relevance") or 0.0)
        print("relevance:", rel)
        detail = out.get("relevance_detail") or {}
        if detail:
            print(
                "  score breakdown: dense_top={:.3f} bm25_part={:.3f} hybrid={:.3f} overlap={:.3f} routing={:.3f}".format(
                    float(detail.get("dense_top", 0)),
                    float(detail.get("bm25_part", 0)),
                    float(detail.get("hybrid", 0)),
                    float(detail.get("overlap_boost", 0)),
                    float(detail.get("routing_score", rel)),
                )
            )
        if out.get("semantic_verify_score") is not None:
            print("  semantic_verify:", out.get("semantic_verify_score"))
        print("  route_kb:", out.get("route_kb"))
        print("intent:", out.get("intent"))
        route = out.get("route_name") or "unknown"
        print("route:", route)
        print("repeat_consecutive:", repeat_consecutive, "repeat_total:", repeat_total)
        if repeat_cache.should_write_cache():
            repeat_cache.save_cached(
                cli_session,
                norm_q,
                {
                    "answer": out.get("final_answer") or "",
                    "route": route,
                    "intent": out.get("intent"),
                    "relevance": rel,
                },
            )

        if out.get("intent"):
            print("intent_path:", out.get("intent"))
        snippets = out.get("knowledge_snippets") or []
        if snippets:
            print("--- 检索片段 (top {}) ---".format(len(snippets)))
            for i, s in enumerate(snippets[:3], 1):
                preview = s.replace("\n", " ")[:160]
                print(f"  [{i}] {preview}{'...' if len(s) > 160 else ''}")
        if out.get("pymol_link"):
            print("pymol_link:", out.get("pymol_link"))
        for tr in out.get("tool_results") or []:
            print(
                "  tool:",
                tr.get("tool"),
                "audit:",
                tr.get("audit_id"),
                "ok:",
                tr.get("success"),
            )
        print("--- 回答 ---")
        print(out.get("final_answer") or "")

    if args.query.strip():
        run_once(args.query.strip())
        return

    print("进入交互模式，输入空行退出。")
    while True:
        try:
            q = input("用户> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            break
        run_once(q)


if __name__ == "__main__":
    main()
