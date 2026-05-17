from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import AIMessage

from nanobody_agent.citations import (
    build_citation_snippets,
    format_context_with_refs,
    inject_citation_markers,
)
from nanobody_agent.config import Settings
from nanobody_agent.llm_utils import (
    classify_intent_rules,
    direct_answer,
    rag_answer,
    rag_fallback_answer,
    to_ai_message,
)
from nanobody_agent.nanokgat_adapter import build_pymol_link, run_nanokgat
from nanobody_agent.retrieval import HybridRetriever
from nanobody_agent.sequence_embed import extract_sequence
from nanobody_agent.state import AgentState, Intent


@dataclass
class GraphDeps:
    settings: Settings
    retriever: HybridRetriever


def classify_router(state: AgentState, deps: GraphDeps) -> dict:
    q = state.get("user_query") or ""
    if not q:
        return {
            "relevance": 0.0,
            "relevance_detail": {},
            "semantic_verify_score": None,
            "route_kb": False,
            "reject": True,
            "extended_retrieval": False,
            "intent": "unknown",
            "intent_raw": "unknown",
        }
    decision = deps.retriever.decide_kb_route(q)
    intent = classify_intent_rules(q) or "unknown"
    return {
        "relevance": float(decision.get("relevance") or 0.0),
        "relevance_detail": decision.get("relevance_detail") or {},
        "semantic_verify_score": decision.get("semantic_verify_score"),
        "route_kb": bool(decision.get("route_kb")),
        "reject": bool(decision.get("reject")),
        "extended_retrieval": bool(decision.get("extended_retrieval")),
        "intent": intent,
        "intent_raw": intent,
    }


def _retrieval_query(state: AgentState) -> str:
    q = (state.get("user_query") or "").strip()
    mem = (state.get("memory_context") or "").strip()
    if not mem:
        return q
    return f"{q}\n{mem[:600]}"


def retrieve_knowledge(state: AgentState, deps: GraphDeps) -> dict:
    q = _retrieval_query(state)
    if state.get("extended_retrieval"):
        hits = deps.retriever.retrieve_extended(q)
        route = "retrieve_knowledge_extended"
    else:
        hits = deps.retriever.retrieve(q, top_k=5)
        route = "retrieve_knowledge"
    citations = build_citation_snippets(hits)
    snippets = [c["text"] for c in citations]
    return {
        "knowledge_snippets": snippets,
        "citations": citations,
        "route_name": route,
    }


def generate_answer(state: AgentState, deps: GraphDeps) -> dict:
    q = state.get("user_query") or ""
    citations = state.get("citations") or []
    snippets = state.get("knowledge_snippets") or []
    mem = state.get("memory_context") or ""
    ctx_blocks = format_context_with_refs(citations) if citations else "\n\n---\n\n".join(snippets)
    text = rag_answer(q, ctx_blocks, deps.settings, memory_context=mem, use_citation_prompt=bool(citations))
    text = inject_citation_markers(text, citations)
    route = "knowledge_base_rag"
    if text.startswith("以下根据知识库检索结果整理"):
        route = "knowledge_base_rag_offline"
    return {
        "final_answer": text,
        "citations": citations,
        "messages": [to_ai_message(text)],
        "route_name": route,
    }


def reject_low_relevance(state: AgentState, deps: GraphDeps) -> dict:
    rel = float(state.get("relevance") or 0.0)
    sem = state.get("semantic_verify_score")
    text = (
        "当前问题与知识库内容相关度较低，为避免不准确回答，系统暂不生成推测性结论。\n\n"
        f"- 路由相关度：{rel:.3f}\n"
        + (f"- 语义复核：{float(sem):.3f}\n" if sem is not None else "")
        + "\n建议：\n"
        "1. 补充纳米抗体/结合位点等更具体的关键词；\n"
        "2. 换一种问法或拆分问题；\n"
        "3. 若需结构预测，请使用「预测」「结合位点」或上传 PDB。"
    )
    return {
        "final_answer": text,
        "reject_reason": "low_relevance",
        "messages": [to_ai_message(text)],
        "route_name": "reject_low_relevance",
    }


def llm_router(state: AgentState, deps: GraphDeps) -> dict:
    q = state.get("user_query") or ""
    intent = classify_intent_rules(q) or "unknown"
    return {"intent": intent, "intent_raw": intent}


def direct_llm_answer(state: AgentState, deps: GraphDeps) -> dict:
    q = state.get("user_query") or ""
    mem = state.get("memory_context") or ""
    text = direct_answer(q, deps.settings, memory_context=mem)
    route = "direct_llm"
    if text.startswith("大模型 API 不可用") or text.startswith("以下根据知识库"):
        hits = deps.retriever.retrieve(q, top_k=3)
        if hits:
            citations = build_citation_snippets(hits)
            text = rag_fallback_answer(q, [c["text"] for c in citations])
            route = "knowledge_base_rag_offline"
            return {
                "final_answer": text,
                "citations": citations,
                "messages": [to_ai_message(text)],
                "route_name": route,
            }
    return {
        "final_answer": text,
        "messages": [to_ai_message(text)],
        "route_name": route,
    }


def nanokgat_predict(state: AgentState, deps: GraphDeps) -> dict:
    q = state.get("user_query") or ""
    intent: Intent = state.get("intent") or "prediction"
    seq = extract_sequence(q)
    pdb_path = state.get("pdb_path")
    pdb_meta = state.get("pdb_meta")
    payload = run_nanokgat(
        q,
        deps.settings,
        sequence=seq,
        pdb_path=str(pdb_path) if pdb_path else None,
        pdb_meta=pdb_meta if isinstance(pdb_meta, dict) else None,
    )
    residues = payload.get("residues", [])
    conf = payload.get("confidence")
    probs = payload.get("residue_probs") or {}
    top_probs = sorted(probs.items(), key=lambda x: -float(x[1]))[:8]
    prob_line = ", ".join(f"{k}:{v}" for k, v in top_probs) if top_probs else "（见详情）"
    lines = [
        "NanoKGAT 预测结果（集成接口返回）：",
        f"- 候选结合位点 / 关键残基：{', '.join(map(str, residues)) if residues else '（无）'}",
        f"- 置信度：{conf}" if conf is not None else "",
        f"- 残基概率（Top）：{prob_line}",
        f"- 结构/会话文件：{payload.get('structure_path', '')}",
    ]
    text = "\n".join([x for x in lines if x])
    route = "nanokgat_predict"
    out: dict = {
        "prediction_payload": payload,
        "final_answer": text,
        "messages": [AIMessage(content=text)],
        "route_name": route,
    }

    if intent == "visualization":
        sid = str(payload.get("session_id") or "")
        if sid:
            link = build_pymol_link(sid, deps.settings)
            out["pymol_link"] = link
            merged = text + f"\n\nPyMOL 可视化入口：{link}"
            out["final_answer"] = merged
            out["messages"] = [AIMessage(content=merged)]
            out["route_name"] = "nanokgat_predict_visualization"
    return out


def route_after_llm_router(state: AgentState) -> str:
    intent = state.get("intent") or "unknown"
    if intent in ("definition", "comparison", "unknown"):
        return "direct"
    if intent == "visualization":
        return "viz"
    return "pred"


def route_after_classify_factory(threshold: float):
    def _route(state: AgentState) -> str:
        q = state.get("user_query") or ""
        rule = classify_intent_rules(q) or state.get("intent")
        if rule in ("prediction", "visualization"):
            return "llm"
        if state.get("reject"):
            return "reject"
        if state.get("route_kb"):
            return "kb"
        if rule in ("definition", "comparison") and float(state.get("relevance") or 0.0) >= 0.50:
            sem = state.get("semantic_verify_score")
            if sem is None or float(sem) >= 0.45:
                return "kb"
        return "kb" if float(state.get("relevance") or 0.0) >= threshold else "llm"

    return _route
