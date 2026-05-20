from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from nanobody_agent.config import Settings
from nanobody_agent.state import Intent

_VIZ_KEYWORDS = ("pymol", "可视化", "结构可视化", "三维结构", "3d结构")
_PREDICTION_KEYWORDS = ("预测", "结合位点", "表位", "binding", "nanokgat", "候选残基", "打分")
_COMPARISON_KEYWORDS = ("对比", "比较", "区别", "vs", "versus")
_DEFINITION_KEYWORDS = ("什么是", "是什么", "定义", "介绍", "概念")
_DOMAIN_TOOLS_KEYWORDS = (
    "噬菌体",
    "展示库",
    "LIMS",
    "SPR",
    "ELISA",
    "FoldX",
    "Rosetta",
    "AlphaFold",
    "突变扫描",
    "亲和力成熟",
    "ddG",
    "RMSD",
    "结构库",
    "SLURM",
)


def classify_intent_rules(user_query: str) -> Intent | None:
    """Rule-based intent; no API call."""
    q = user_query.strip()
    if not q:
        return None
    lower = q.lower()
    has_pred = any(k in q for k in _PREDICTION_KEYWORDS) or any(k in lower for k in ("predict", "binding"))
    has_viz = any(k in q for k in _VIZ_KEYWORDS) or "pymol" in lower
    if has_viz and has_pred:
        return "visualization"
    if has_viz:
        return "visualization"
    if has_pred:
        return "prediction"
    if any(k in q for k in _DOMAIN_TOOLS_KEYWORDS) or any(
        k in lower for k in ("foldx", "rosetta", "alphafold", "slurm")
    ):
        return "domain_tools"
    if any(k in q for k in _COMPARISON_KEYWORDS):
        return "comparison"
    if any(k in q for k in _DEFINITION_KEYWORDS):
        return "definition"
    return None


def get_chat_model(settings: Settings) -> ChatOpenAI:
    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        raise RuntimeError(
            "未配置 API Key。DeepSeek 请在 .env 设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY；"
            "并设置 LLM_PROVIDER=deepseek、OPENAI_BASE_URL=https://api.deepseek.com/v1、"
            "OPENAI_MODEL=deepseek-chat。参考 env.example。"
        )
    kwargs: dict[str, Any] = {
        "model": settings.openai_model,
        "api_key": api_key,
    }
    base_url = (settings.openai_base_url or "").strip()
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


_INTENT_SYSTEM = """你是纳米抗体与结构生物信息学助手的路由器。
根据用户最新问题，从下列意图中选一个（只输出 JSON，不要其它文字）：
- definition：概念/定义类
- comparison：模型/方法对比类
- prediction：结合位点/表位等预测类（需要跑 NanoKGAT）
- visualization：在预测之外明确要求 PyMOL 或结构可视化
若同时有预测与可视化，选 visualization。
无法判断则选 unknown。

输出格式严格为：{"intent":"definition|comparison|prediction|visualization|unknown"}
"""


def classify_intent_llm(user_query: str, settings: Settings) -> Intent:
    llm = get_chat_model(settings)
    resp = llm.invoke(
        [
            SystemMessage(content=_INTENT_SYSTEM),
            HumanMessage(content=user_query),
        ]
    )
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return "unknown"
    try:
        data = json.loads(m.group(0))
        raw = str(data.get("intent", "unknown")).lower().strip()
    except json.JSONDecodeError:
        return "unknown"

    if raw in ("definition", "comparison", "prediction", "visualization"):
        return raw  # type: ignore[return-value]
    return "unknown"


def classify_intent(user_query: str, settings: Settings) -> Intent:
    """Rules first, then LLM; on API failure fall back to rules or unknown."""
    rule = classify_intent_rules(user_query)
    if rule:
        return rule
    try:
        return classify_intent_llm(user_query, settings)
    except Exception:
        return classify_intent_rules(user_query) or "unknown"


def _llm_unavailable_message(detail: str = "") -> str:
    base = (
        "大模型 API 不可用（未配置密钥、配额不足或网络错误）。\n"
        "预测类问题请包含「预测」「结合位点」等词，将走 NanoKGAT stub，无需 LLM。"
    )
    if detail:
        return base + f"\n（详情：{detail[:200]}）"
    return base


def rag_fallback_answer(user_query: str, snippets: list[str]) -> str:
    """When LLM is down but retrieval succeeded, return snippets directly."""
    if not snippets:
        return _llm_unavailable_message("知识库未检索到可用片段")
    lines = [
        "以下根据知识库检索结果整理（大模型暂不可用，未做二次润色）：",
        "",
    ]
    for i, s in enumerate(snippets[:3], 1):
        block = s.strip()
        if len(block) > 600:
            block = block[:600] + "…"
        lines.append(f"【片段 {i}】\n{block}\n")
    lines.append(
        "提示：请在 .env 配置有效的 DEEPSEEK_API_KEY，并确认账户有余额；"
        "配置成功后重启 `python run_web.py` 可获得自然语言总结。"
    )
    return "\n".join(lines)


_RAG_SYSTEM = """你是纳米抗体结合位点预测领域的专业助手。请仅依据提供的知识片段作答；
若片段不足以回答，请明确说明并给出保守建议。使用简体中文。若提供对话记忆，请结合上下文理解指代与追问。
引用知识时请使用 [1]、[2] 等编号标注来源（与片段编号一致）。"""


def format_memory_block(memory_context: str) -> str:
    text = (memory_context or "").strip()
    if not text:
        return ""
    return f"\n\n## 对话记忆\n{text}\n"


def rag_answer(
    user_query: str,
    snippets: list[str] | str,
    settings: Settings,
    *,
    memory_context: str = "",
    use_citation_prompt: bool = False,
) -> str:
    snippet_list: list[str]
    if isinstance(snippets, str):
        ctx = snippets
        snippet_list = []
    else:
        snippet_list = snippets
        ctx = "\n\n---\n\n".join(snippets) if snippets else "(无检索片段)"
    if snippet_list and not (settings.openai_api_key or "").strip():
        return rag_fallback_answer(user_query, snippet_list)
    try:
        llm = get_chat_model(settings)
        mem = format_memory_block(memory_context)
        resp = llm.invoke(
            [
                SystemMessage(content=_RAG_SYSTEM),
                HumanMessage(
                    content=f"知识片段：\n{ctx}{mem}\n\n用户问题：{user_query}"
                ),
            ]
        )
        return resp.content if isinstance(resp.content, str) else str(resp.content)
    except Exception as e:
        if snippet_list:
            return rag_fallback_answer(user_query, snippet_list)
        return _llm_unavailable_message(str(e))


_DIRECT_SYSTEM = """你是纳米抗体与机器学习结构预测领域的专业助手。请用简体中文、条理清晰地回答。
若提供对话记忆，请结合上下文理解指代与追问。"""


def direct_answer(
    user_query: str,
    settings: Settings,
    *,
    memory_context: str = "",
) -> str:
    if not (settings.openai_api_key or "").strip():
        return _llm_unavailable_message("未读取到 API Key")
    try:
        llm = get_chat_model(settings)
        mem = format_memory_block(memory_context)
        prompt = user_query + mem if mem else user_query
        resp = llm.invoke(
            [
                SystemMessage(content=_DIRECT_SYSTEM),
                HumanMessage(content=prompt),
            ]
        )
        return resp.content if isinstance(resp.content, str) else str(resp.content)
    except Exception as e:
        return _llm_unavailable_message(str(e))


def to_ai_message(text: str) -> AIMessage:
    return AIMessage(content=text)
