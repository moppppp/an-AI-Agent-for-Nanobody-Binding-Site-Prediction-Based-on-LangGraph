from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _detect_env_encoding(data: bytes) -> str:
    if data.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if data.startswith(b"\xfe\xff"):
        return "utf-16-be"
    if b"\x00" in data[: min(200, len(data))]:
        return "utf-16-le"
    return "utf-8-sig"


def _load_dotenv_file() -> None:
    """Load .env into os.environ; tolerate UTF-16 (Windows Notepad 'Unicode')."""
    env_path = _project_root() / ".env"
    if not env_path.is_file():
        return

    data = env_path.read_bytes()
    encoding = _detect_env_encoding(data)
    needs_repair = encoding.startswith("utf-16")

    for key, value in dotenv_values(env_path, encoding=encoding).items():
        if key and value is not None:
            os.environ.setdefault(key, value)

    if needs_repair:
        text = env_path.read_text(encoding=encoding)
        env_path.write_text(text, encoding="utf-8", newline="\n")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # openai | deepseek（DeepSeek 使用 OpenAI 兼容接口）
    llm_provider: str = "deepseek"
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    openai_base_url: str | None = None
    openai_model: str = "deepseek-chat"

    hybrid_dense_weight: float = 0.65
    kb_relevance_threshold: float = 0.65
    kb_relevance_gray_high: float = 0.75
    kb_relevance_verify_low: float = 0.50
    # secondary semantic verify (gray zone); local lightweight model
    semantic_verify_model: str = "BAAI/bge-small-zh-v1.5"
    semantic_verify_threshold: float = 0.48
    bm25_smooth_k: float = 4.0
    embedding_model: str = "BAAI/bge-small-zh-v1.5"

    knowledge_dir: Path = _project_root() / "knowledge_base"
    # OCR 全文很大，默认不索引以加快启动；需要时设 KNOWLEDGE_INCLUDE_OCR=true
    knowledge_include_ocr: bool = False
    knowledge_max_chunks: int = 0  # 0=不限制；调试可设 500

    nanokgat_use_stub: bool = True
    nanokgat_python_module: str = ""
    nanokgat_predict_callable: str = "predict_binding_sites"

    pymol_viewer_url_template: str = "http://127.0.0.1:8765/pymol/view?session={session_id}"
    outputs_dir: Path = _project_root() / "outputs"

    # 多轮对话：滑动窗口（保留最近 N 轮完整对话）+ 更早轮次 LLM/启发式摘要
    chat_memory_window_turns: int = 4
    chat_memory_max_summary_chars: int = 1600

    # 连续相同问题 Redis 缓存（超过 threshold 次后，第 threshold+1 次起读缓存）
    redis_enabled: bool = True
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_key_prefix: str = "nanobody"
    redis_cache_ttl_seconds: int = 86400
    repeat_query_cache_threshold: int = 3
    # True：同一 session 内只要问过相同问题（中间可夹其它问题），第 2 次起可读缓存
    repeat_query_cache_intermittent: bool = True

    # 低相关拒答、补充检索
    kb_reject_threshold: float = 0.38
    kb_extended_retrieval_top_k: int = 8

    # 知识增强：实体对齐、定性词扩展、时效衰减、事实漂移
    entity_align_enabled: bool = True
    qualitative_expand_enabled: bool = True
    temporal_decay_enabled: bool = True
    temporal_half_life_years: float = 5.0
    fact_drift_enabled: bool = True
    fact_drift_penalty: float = 0.12

    # 序列检索：安装 antiberty 后自动启用，否则氨基酸组成回退
    antiberty_enabled: bool = True
    sequence_dense_boost: float = 0.12

    # 会话持久化（Redis 存多轮记忆 JSON）
    session_persist_redis: bool = True
    session_persist_ttl_seconds: int = 604800

    # PDB 上传
    upload_max_bytes: int = 10_485_760
    uploads_dir: Path = _project_root() / "uploads"

    # 领域工具层（噬菌体库 / LIMS / PDB 库 / 科学计算作业）
    tools_enabled: bool = True
    tools_allow_outbound: bool = False
    tool_audit_dir: Path = _project_root() / "outputs" / "tool_audit"
    phage_db_url: str = ""  # e.g. sqlite:///path/to/phage.db
    lims_api_base: str = ""  # internal LIMS base URL (outbound gated)
    pdb_library_dir: Path = _project_root() / "knowledge_base" / "pdb_library"
    science_jobs_dir: Path = _project_root() / "outputs" / "science_jobs"
    job_scheduler: str = "stub"  # stub | slurm | k8s
    tool_actor_role: str = "scientist"


def _apply_llm_provider(settings: Settings) -> Settings:
    provider = (settings.llm_provider or "deepseek").strip().lower()
    api_key = (
        settings.openai_api_key
        or settings.deepseek_api_key
        or os.environ.get("DEEPSEEK_API_KEY", "")
        or os.environ.get("OPENAI_API_KEY", "")
    ).strip()
    updates: dict = {}
    if api_key:
        updates["openai_api_key"] = api_key

    if provider == "deepseek":
        if not (settings.openai_base_url or "").strip():
            updates["openai_base_url"] = "https://api.deepseek.com/v1"
        model = (settings.openai_model or "").strip()
        if not model or model == "gpt-4o-mini":
            updates["openai_model"] = "deepseek-chat"
    elif provider == "openai":
        if not (settings.openai_base_url or "").strip():
            updates["openai_base_url"] = None

    if updates:
        return settings.model_copy(update=updates)
    return settings


def get_settings() -> Settings:
    _load_dotenv_file()
    return _apply_llm_provider(Settings())
