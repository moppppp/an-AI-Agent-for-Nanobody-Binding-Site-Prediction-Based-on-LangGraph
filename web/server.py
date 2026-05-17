from __future__ import annotations

import asyncio
import json
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _write_utf8_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def _extract_css_from_gen() -> bool:
    import re

    gen_py = ROOT / "scripts" / "gen_web_static.py"
    if not gen_py.is_file():
        return False
    src = gen_py.read_text(encoding="utf-8")
    m = re.search(r'APP_CSS = """(.*?)"""', src, re.DOTALL)
    if not m:
        return False
    _write_utf8_file(STATIC_DIR / "app.css", m.group(1))
    return True


def _ensure_static_assets() -> None:
    """Regenerate static UI if missing or saved as UTF-16."""
    index = STATIC_DIR / "index.html"
    css = STATIC_DIR / "app.css"
    js = STATIC_DIR / "app.js"
    needs_gen = not index.is_file() or not css.is_file() or not js.is_file()
    if not needs_gen and css.is_file():
        try:
            css_text = css.read_text(encoding="utf-8", errors="ignore")
            needs_gen = ".chat-scroll" not in css_text
        except OSError:
            needs_gen = True
    if not needs_gen and js.is_file():
        try:
            js_text = js.read_text(encoding="utf-8", errors="ignore")
            needs_gen = (
                "nanobody_session_id" not in js_text
                or "metaMemory" not in js_text
                or "memoryBlock" not in js_text
                or "citationBlock" not in js_text
                or "pdbFile" not in js_text
                or "chatHistoryList" not in js_text
            )
        except OSError:
            needs_gen = True
    if not needs_gen:
        head = index.read_bytes()[:20]
        needs_gen = head.startswith(b"\xff\xfe") or head.startswith(b"\xfe\xff") or not head.startswith(b"<!DOC")
    if not needs_gen and js.is_file():
        head = js.read_bytes()[:4]
        needs_gen = head.startswith(b"\xff\xfe") or head.startswith(b"\xfe\xff")
    if needs_gen:
        gen = ROOT / "scripts" / "gen_web_static.py"
        if gen.is_file():
            import subprocess

            subprocess.run([sys.executable, str(gen)], cwd=str(ROOT), check=False)
        if not css.is_file():
            _extract_css_from_gen()


_ensure_static_assets()

_graph_app: Any = None
_loading = False
_pdb_uploads: dict[str, dict[str, Any]] = {}


def _chat_memory_fields(session_id: str) -> tuple[str, str, int, bool]:
    from nanobody_agent.config import get_settings
    from nanobody_agent.conversation_memory import get_conversation_store

    settings = get_settings()
    session = get_conversation_store().get_or_create(session_id, settings)
    memory_context = session.build_context_before_turn(settings)
    return memory_context, session.summary, session.pair_count(), bool(session.summary.strip())
_load_error: str | None = None
_load_stage: str = "pending"


def _state_to_response(
    out: dict,
    *,
    session_id: str,
    memory_turns: int,
    memory_has_summary: bool,
    memory_summary: str = "",
    memory_context_preview: str = "",
) -> dict[str, Any]:
    snippets = out.get("knowledge_snippets") or []
    citations = out.get("citations") or []
    payload = out.get("prediction_payload") or {}
    detail = out.get("relevance_detail") or {}
    return {
        "answer": out.get("final_answer") or "",
        "session_id": session_id,
        "memory_turns": memory_turns,
        "memory_has_summary": memory_has_summary,
        "memory_summary": memory_summary,
        "memory_context_preview": memory_context_preview,
        "intent": out.get("intent"),
        "route": out.get("route_name"),
        "relevance": float(out.get("relevance") or 0.0),
        "relevance_detail": detail,
        "semantic_verify_score": out.get("semantic_verify_score"),
        "route_kb": out.get("route_kb"),
        "snippets": snippets[:5],
        "citations": citations[:8],
        "prediction": payload if payload else None,
        "pymol_link": out.get("pymol_link") or None,
        "reject_reason": out.get("reject_reason"),
    }


async def _load_graph_app() -> None:
    global _graph_app, _loading, _load_error, _load_stage
    _loading = True
    _load_error = None
    _load_stage = "starting"
    print("[nanobody] 后台加载智能体（首次启动较慢，请看下方进度）", flush=True)
    try:
        from nanobody_agent.graph import build_app

        _load_stage = "building"
        _graph_app = await asyncio.to_thread(build_app)
        _load_stage = "ready"
        print("[nanobody] 智能体已就绪: http://127.0.0.1:8765", flush=True)
    except Exception as e:
        _load_error = str(e)
        _graph_app = None
        _load_stage = "error"
        print(f"[nanobody] 加载失败: {e}", flush=True)
    finally:
        _loading = False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    asyncio.create_task(_load_graph_app())
    yield


app = FastAPI(title="纳米抗体智能体", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = Field(default=None, max_length=128)
    pdb_id: str | None = Field(default=None, max_length=64)


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    memory_turns: int = 0
    memory_has_summary: bool = False
    memory_summary: str = ""
    memory_context_preview: str = ""
    intent: str | None = None
    route: str | None = None
    relevance: float = 0.0
    relevance_detail: dict | None = None
    semantic_verify_score: float | None = None
    route_kb: bool | None = None
    snippets: list[str] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    prediction: dict | None = None
    reject_reason: str | None = None
    pymol_link: str | None = None
    cache_hit: bool = False
    repeat_count: int = 0
    repeat_total: int = 0


@app.get("/api/health")
async def health() -> dict[str, Any]:
    stage = _load_stage
    if _loading:
        hint = {
            "starting": "正在初始化…",
            "building": "正在加载模型并索引知识库（首次约 1～5 分钟）",
        }.get(stage, "加载中…")
    elif _graph_app is not None:
        hint = "就绪"
    elif _load_error:
        hint = f"失败: {_load_error}"
    else:
        hint = "未就绪"
    redis_ok = False
    try:
        from nanobody_agent.config import get_settings
        from nanobody_agent.repeat_query_cache import get_repeat_query_cache

        redis_ok = get_repeat_query_cache(get_settings()).redis_available
    except Exception:
        redis_ok = False
    return {
        "ready": _graph_app is not None,
        "loading": _loading,
        "error": _load_error,
        "stage": stage,
        "hint": hint,
        "redis_available": redis_ok,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    if _loading:
        raise HTTPException(status_code=503, detail="智能体正在加载知识库与模型，请稍候…")
    if _graph_app is None:
        detail = _load_error or "智能体未就绪"
        raise HTTPException(status_code=503, detail=detail)

    from nanobody_agent.config import get_settings
    from nanobody_agent.conversation_memory import get_conversation_store
    from nanobody_agent.repeat_query_cache import get_repeat_query_cache

    q = body.query.strip()
    sid = (body.session_id or "").strip() or str(uuid.uuid4())
    settings = get_settings()
    repeat_cache = get_repeat_query_cache(settings)
    repeat_consecutive, repeat_total, norm_q = repeat_cache.record_ask(sid, q)

    memory_context, conv_summary, _turns_before, _has_sum_before = _chat_memory_fields(sid)
    session = get_conversation_store().get_or_create(sid, settings)

    if repeat_cache.should_read_cache(repeat_consecutive, repeat_total, norm_q, sid):
        cached = repeat_cache.get_cached(sid, norm_q)
        if cached:
            answer = cached.get("answer") or ""
            backend = "Redis" if repeat_cache.redis_available else "内存"
            mode = "间断" if repeat_total >= 2 and repeat_consecutive <= repeat_cache.threshold else "连续"
            print(
                f"[nanobody] 重复问题缓存命中 ({backend}/{mode}) session={sid[:8]}… "
                f"consecutive={repeat_consecutive} total={repeat_total} q={norm_q[:40]!r}",
                flush=True,
            )
            session.record_turn(q, answer, settings)
            session.compress(settings)
            payload = dict(cached)
            payload["session_id"] = sid
            payload["cache_hit"] = True
            payload["repeat_count"] = repeat_consecutive
            payload["repeat_total"] = repeat_total
            payload["memory_turns"] = session.pair_count()
            payload["memory_has_summary"] = bool(session.summary.strip())
            payload["memory_summary"] = session.summary.strip()
            payload["memory_context_preview"] = (memory_context or "")[:1200]
            if not payload.get("route"):
                payload["route"] = "repeat_query_cache"
            return ChatResponse(**payload)

    pdb_meta = None
    pdb_path = None
    if body.pdb_id and body.pdb_id in _pdb_uploads:
        pdb_meta = _pdb_uploads[body.pdb_id].get("meta")
        pdb_path = _pdb_uploads[body.pdb_id].get("path")

    state = {
        "messages": [HumanMessage(content=q)],
        "user_query": q,
        "memory_context": memory_context,
        "conversation_summary": conv_summary,
        "pdb_path": pdb_path or "",
        "pdb_meta": pdb_meta or {},
    }
    try:
        out = await asyncio.to_thread(_graph_app.invoke, state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推理失败: {e}") from e

    session.record_turn(q, out.get("final_answer") or "", settings)
    session.compress(settings)

    data = _state_to_response(
        out,
        session_id=sid,
        memory_turns=session.pair_count(),
        memory_has_summary=bool(session.summary.strip()),
        memory_summary=session.summary.strip(),
        memory_context_preview=(memory_context or "")[:1200],
    )
    data["cache_hit"] = False
    data["repeat_count"] = repeat_consecutive
    data["repeat_total"] = repeat_total

    if repeat_cache.should_write_cache():
        repeat_cache.save_cached(sid, norm_q, data)
        backend = "Redis" if repeat_cache.redis_available else "内存"
        print(
            f"[nanobody] 重复问题已写入缓存 ({backend}) session={sid[:8]}… "
            f"consecutive={repeat_consecutive} total={repeat_total}",
            flush=True,
        )

    return ChatResponse(**data)


@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str) -> dict[str, bool]:
    from nanobody_agent.config import get_settings
    from nanobody_agent.conversation_memory import get_conversation_store
    from nanobody_agent.repeat_query_cache import get_repeat_query_cache

    settings = get_settings()
    sid = session_id.strip()
    ok = get_conversation_store().clear(sid, settings)
    get_repeat_query_cache(settings).clear_session(sid)
    return {"ok": ok}


@app.post("/api/upload/pdb")
async def upload_pdb(file: UploadFile = File(...)) -> dict[str, Any]:
    from nanobody_agent.config import get_settings
    from nanobody_agent.pdb_handler import parse_pdb_file

    settings = get_settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    raw = await file.read()
    if len(raw) > int(settings.upload_max_bytes):
        raise HTTPException(status_code=413, detail="PDB 文件过大")
    pdb_id = uuid.uuid4().hex[:12]
    dest = settings.uploads_dir / f"{pdb_id}.pdb"
    dest.write_bytes(raw)
    try:
        meta = parse_pdb_file(dest)
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"PDB 解析失败: {e}") from e
    _pdb_uploads[pdb_id] = {"path": str(dest), "meta": meta}
    return {
        "pdb_id": pdb_id,
        "chain_id": meta.get("chain_id"),
        "residue_count": len(meta.get("residues") or []),
        "sequence_preview": (meta.get("sequence") or "")[:80],
    }


@app.get("/api/workflow")
async def workflow_schema() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "classify_router", "label": "路由判定"},
            {"id": "reject_low_relevance", "label": "低相关拒答"},
            {"id": "retrieve_knowledge", "label": "混合检索"},
            {"id": "generate_answer", "label": "RAG 生成"},
            {"id": "llm_router", "label": "LLM 分支"},
            {"id": "direct_llm_answer", "label": "直连 LLM"},
            {"id": "nanokgat_predict", "label": "NanoKGAT 预测"},
        ],
        "edges": [
            ["START", "classify_router"],
            ["classify_router", "reject_low_relevance"],
            ["classify_router", "retrieve_knowledge"],
            ["classify_router", "llm_router"],
            ["retrieve_knowledge", "generate_answer"],
            ["llm_router", "direct_llm_answer"],
            ["llm_router", "nanokgat_predict"],
        ],
    }


@app.get("/pymol/view")
async def pymol_view(session_id: str) -> Any:
    from fastapi.responses import HTMLResponse
    from nanobody_agent.config import get_settings

    settings = get_settings()
    payload: dict[str, Any] = {}
    for p in sorted(settings.outputs_dir.glob(f"nanokgat_*_{session_id}.json")):
        payload = json.loads(p.read_text(encoding="utf-8"))
        break
    if not payload:
        for p in sorted(settings.outputs_dir.glob("nanokgat_stub_*.json"), reverse=True):
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("session_id") == session_id:
                payload = data
                break
    residues = payload.get("residues") or []
    probs = payload.get("residue_probs") or {}
    attn = payload.get("attention_weights") or []
    rows = "".join(
        f"<tr><td>{r}</td><td>{probs.get(str(i+1), '-')}</td></tr>"
        for i, r in enumerate(residues)
    )
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/>
    <title>PyMOL 视图 {session_id}</title>
    <style>body{{font-family:sans-serif;padding:1.5rem}}table{{border-collapse:collapse}}
    td,th{{border:1px solid #ccc;padding:.4rem .8rem}}</style></head><body>
    <h1>纳米抗体结合位点 — 会话 {session_id}</h1>
    <p>在 PyMOL 中加载对应 PDB 后，可将下列残基高亮（stub/预测结果）。</p>
    <table><tr><th>残基</th><th>概率</th></tr>{rows}</table>
    <h2>注意力 Top</h2><pre>{json.dumps(attn[:10], ensure_ascii=False, indent=2)}</pre>
    </body></html>"""
    return HTMLResponse(html)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
