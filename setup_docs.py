# -*- coding: utf-8 -*-
"""Generate README.md, .env.example, merge .env. Run: python setup_docs.py"""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent

README_MD = r"""# nanobody_agent — 纳米抗体 LangGraph 智能体

基于 **LangGraph** 的纳米抗体结合位点智能体，实现「知识检索 + 结合位点预测」协同。

## 功能概览

| 模块 | 说明 |
|------|------|
| 工作流 | LangGraph：RAG、拒答、扩展检索、直连 LLM、位点预测 |
| 路由 | 规则意图 + FAISS/BM25 + BGE 灰区语义复核 |
| Web | http://127.0.0.1:8765 |

## 配置 DeepSeek API Key（必做）

RAG 生成、多轮对话摘要等依赖 **DeepSeek**（OpenAI 兼容 HTTP API）。**本仓库不包含任何有效 API Key**，请自行申请后写入本地 `.env`。

### 步骤

1. 前往 [DeepSeek 开放平台](https://platform.deepseek.com/) 注册账号，在控制台 **创建 API Key**。
2. 在项目根目录执行（Windows）：

   ```bat
   copy .env.example .env
   ```

   Linux / macOS：

   ```bash
   cp .env.example .env
   ```

3. 编辑 **`.env`**（已被 `.gitignore` 忽略，**切勿提交到 GitHub**），填入你自己的密钥：

   ```env
   LLM_PROVIDER=deepseek
   DEEPSEEK_API_KEY=sk-请替换为你的真实密钥
   OPENAI_BASE_URL=https://api.deepseek.com/v1
   OPENAI_MODEL=deepseek-chat
   ```

4. 保存后启动服务。若 Key 为空或错误，问答/摘要会报错或走降级逻辑。

### 可选：使用 OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-你的OpenAI密钥
OPENAI_MODEL=gpt-4o-mini
```

## 快速开始

```bash
cd nanobody_agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# 先按上一节填写 DEEPSEEK_API_KEY
docker compose -f compose.redis.yaml up -d
python run_web.py
```

浏览器打开 http://127.0.0.1:8765

CLI：`python main.py "什么是纳米抗体？"`

## 知识库

PDF 放入 `knowledge_base/pdfs/` → `python ingest_pdfs.py`

## 评测

```bash
python scripts/eval/eval_routing.py
```

## NanoKGAT

默认 `NANOKGAT_USE_STUB=true`（Stub 演示）。真实 GNN：`NANOKGAT_USE_STUB=false` + `NANOKGAT_PYTHON_MODULE`，见 `src/nanobody_agent/nanokgat_adapter.py`。

## 许可证

请自行添加 LICENSE 文件。
"""

ENV_EXAMPLE = """# 复制为 .env 并填写你自己的 API Key（勿提交 .env 到 Git）
# Windows: copy .env.example .env
# Linux/macOS: cp .env.example .env

# --- LLM（必填：DEEPSEEK_API_KEY 或 OPENAI_API_KEY）---
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat

# --- Retrieval ---
HYBRID_DENSE_WEIGHT=0.65
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
SEMANTIC_VERIFY_MODEL=BAAI/bge-small-zh-v1.5
KB_RELEVANCE_THRESHOLD=0.65
KB_RELEVANCE_GRAY_HIGH=0.75
KB_RELEVANCE_VERIFY_LOW=0.50
KB_REJECT_THRESHOLD=0.38
SEMANTIC_VERIFY_THRESHOLD=0.48
BM25_SMOOTH_K=4.0
KB_EXTENDED_RETRIEVAL_TOP_K=8
KNOWLEDGE_INCLUDE_OCR=false
KNOWLEDGE_MAX_CHUNKS=0

# --- Redis ---
REDIS_ENABLED=true
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_KEY_PREFIX=nanobody
REDIS_CACHE_TTL_SECONDS=86400
REPEAT_QUERY_CACHE_THRESHOLD=3
REPEAT_QUERY_CACHE_INTERMITTENT=true
SESSION_PERSIST_REDIS=true
SESSION_PERSIST_TTL_SECONDS=604800

# --- Memory ---
CHAT_MEMORY_WINDOW_TURNS=4
CHAT_MEMORY_MAX_SUMMARY_CHARS=1600

# --- NanoKGAT ---
NANOKGAT_USE_STUB=true
NANOKGAT_PYTHON_MODULE=
NANOKGAT_PREDICT_CALLABLE=predict_binding_sites
PYMOL_VIEWER_URL_TEMPLATE=http://127.0.0.1:8765/pymol/view?session={session_id}
ANTIBERTY_ENABLED=true
SEQUENCE_DENSE_BOOST=0.12
UPLOAD_MAX_BYTES=10485760
"""

EXTRA = [
    "OPENAI_API_KEY=",
    "BM25_SMOOTH_K=4.0",
    "KB_REJECT_THRESHOLD=0.38",
    "REDIS_KEY_PREFIX=nanobody",
    "REPEAT_QUERY_CACHE_INTERMITTENT=true",
    "SESSION_PERSIST_REDIS=true",
    "SESSION_PERSIST_TTL_SECONDS=604800",
    "KB_EXTENDED_RETRIEVAL_TOP_K=8",
    "ANTIBERTY_ENABLED=true",
    "SEQUENCE_DENSE_BOOST=0.12",
    "CHAT_MEMORY_WINDOW_TURNS=4",
    "CHAT_MEMORY_MAX_SUMMARY_CHARS=1600",
    "PYMOL_VIEWER_URL_TEMPLATE=http://127.0.0.1:8765/pymol/view?session={session_id}",
    "NANOKGAT_PYTHON_MODULE=",
    "NANOKGAT_PREDICT_CALLABLE=predict_binding_sites",
    "KNOWLEDGE_INCLUDE_OCR=false",
    "KNOWLEDGE_MAX_CHUNKS=0",
    "UPLOAD_MAX_BYTES=10485760",
]


def read_smart(p: Path) -> str:
    b = p.read_bytes()
    if b.startswith(b"\xff\xfe"):
        return b.decode("utf-16-le")
    if b.startswith(b"\xfe\xff"):
        return b.decode("utf-16-be")
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", errors="replace")


def w(p: Path, t: str) -> None:
    p.write_text(t, encoding="utf-8", newline="\n")


def merge_env() -> None:
    p = ROOT / ".env"
    lines = read_smart(p).splitlines() if p.is_file() else []
    have = {x.split("=", 1)[0].strip() for x in lines if "=" in x and not x.strip().startswith("#")}
    if lines and lines[-1].strip():
        lines.append("")
    lines.append("# --- setup_docs ---")
    for item in EXTRA:
        k = item.split("=", 1)[0]
        if k not in have:
            lines.append(item)
    w(p, "\n".join(lines).rstrip() + "\n")


def main() -> None:
    w(ROOT / "README.md", README_MD)
    w(ROOT / ".env.example", ENV_EXAMPLE)
    merge_env()
    print("OK: README.md, .env.example, .env")


if __name__ == "__main__":
    main()
