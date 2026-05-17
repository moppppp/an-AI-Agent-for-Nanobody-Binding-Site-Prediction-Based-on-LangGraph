# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BODY = (
    "# nanobody_agent\n\n"
    "## DeepSeek API Key (required)\n\n"
    "Get a key from https://platform.deepseek.com/\n\n"
    "Windows:\n\n"
    "    copy .env.example .env\n\n"
    "Edit .env (never commit to git):\n\n"
    "    LLM_PROVIDER=deepseek\n"
    "    DEEPSEEK_API_KEY=sk-YOUR_REAL_KEY_HERE\n"
    "    OPENAI_BASE_URL=https://api.deepseek.com/v1\n"
    "    OPENAI_MODEL=deepseek-chat\n\n"
    "## Quick start\n\n"
    "    pip install -r requirements.txt\n"
    "    python run_web.py\n\n"
    "Open http://127.0.0.1:8765\n\n"
    "## NanoKGAT\n\n"
    "Default NANOKGAT_USE_STUB=true. See src/nanobody_agent/nanokgat_adapter.py\n"
)

BODY_ZH = """# nanobody_agent \u2014 \u7eb3\u7c73\u6297\u4f53 LangGraph \u667a\u80fd\u4f53

\u57fa\u4e8e **LangGraph** \u7684\u7eb3\u7c73\u6297\u4f53\u7ed3\u5408\u4f4d\u70b9\u667a\u80fd\u4f53\u3002

## \u914d\u7f6e DeepSeek API Key\uff08\u5fc5\u505a\uff09

RAG \u751f\u6210\u3001\u5bf9\u8bdd\u6458\u8981\u7b49\u9700\u8981\u8c03\u7528 **DeepSeek**\uff08OpenAI \u517c\u5bb9\u63a5\u53e3\uff09\u3002**\u672c\u4ed3\u5e93\u4e0d\u5305\u542b\u4efb\u4f55\u6709\u6548 API Key**\uff0c\u8bf7\u81ea\u884c\u7533\u8bf7\u540e\u5199\u5165\u672c\u5730 `.env`\u3002

### \u6b65\u9aa4

1. \u6253\u5f00 [DeepSeek \u5f00\u653e\u5e73\u53f0](https://platform.deepseek.com/) \u6ce8\u518c\u5e76\u521b\u5efa API Key\u3002
2. \u590d\u5236\u73af\u5883\u53d8\u91cf\u6a21\u677f\uff1a
   - Windows: `copy .env.example .env`
   - Linux/macOS: `cp .env.example .env`
3. \u7f16\u8f91 **`.env`**\uff08\u5df2\u5728 `.gitignore` \u4e2d\uff0c**\u52ff\u63d0\u4ea4\u5230 GitHub**\uff09\uff1a

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-\u8bf7\u66ff\u6362\u4e3a\u4f60\u7684\u771f\u5b9e\u5bc6\u94a5
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

4. \u4fdd\u5b58\u540e\u6267\u884c `python run_web.py`\u3002Key \u4e3a\u7a7a\u6216\u9519\u8bef\u65f6\uff0c\u95ee\u7b54\u4e0e\u6458\u8981\u5c06\u65e0\u6cd5\u6b63\u5e38\u5de5\u4f5c\u3002

\u53ef\u9009\uff1a\u4f7f\u7528 OpenAI \u65f6\u8bbe `LLM_PROVIDER=openai` \u5e76\u586b `OPENAI_API_KEY`\u3002

## \u5feb\u901f\u5f00\u59cb

```bash
cd nanobody_agent
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
copy .env.example .env
docker compose -f compose.redis.yaml up -d
python run_web.py
```

\u6d4f\u89c8\u5668\uff1ahttp://127.0.0.1:8765

## \u77e5\u8bc6\u5e93

PDF \u2192 `knowledge_base/pdfs/` \u2192 `python ingest_pdfs.py`

## \u8bc4\u6d4b

`python scripts/eval/eval_routing.py`

## NanoKGAT

\u9ed8\u8ba4 `NANOKGAT_USE_STUB=true`\uff08Stub \u6f14\u793a\uff09\u3002\u771f\u5b9e GNN\uff1a`NANOKGAT_USE_STUB=false` + `NANOKGAT_PYTHON_MODULE`\uff0c\u89c1 `src/nanobody_agent/nanokgat_adapter.py`\u3002
"""

ENV_EX = """# copy to .env - fill YOUR DeepSeek API key (never commit .env)

LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
HYBRID_DENSE_WEIGHT=0.65
KB_RELEVANCE_THRESHOLD=0.65
KB_RELEVANCE_GRAY_HIGH=0.75
KB_RELEVANCE_VERIFY_LOW=0.50
KB_REJECT_THRESHOLD=0.38
SEMANTIC_VERIFY_THRESHOLD=0.48
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
SEMANTIC_VERIFY_MODEL=BAAI/bge-small-zh-v1.5
BM25_SMOOTH_K=4.0
NANOKGAT_USE_STUB=true
REDIS_ENABLED=true
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_KEY_PREFIX=nanobody
REDIS_CACHE_TTL_SECONDS=86400
REPEAT_QUERY_CACHE_THRESHOLD=3
REPEAT_QUERY_CACHE_INTERMITTENT=true
SESSION_PERSIST_REDIS=true
SESSION_PERSIST_TTL_SECONDS=604800
CHAT_MEMORY_WINDOW_TURNS=4
CHAT_MEMORY_MAX_SUMMARY_CHARS=1600
KB_EXTENDED_RETRIEVAL_TOP_K=8
ANTIBERTY_ENABLED=true
SEQUENCE_DENSE_BOOST=0.12
UPLOAD_MAX_BYTES=10485760
NANOKGAT_PYTHON_MODULE=
NANOKGAT_PREDICT_CALLABLE=predict_binding_sites
PYMOL_VIEWER_URL_TEMPLATE=http://127.0.0.1:8765/pymol/view?session={session_id}
KNOWLEDGE_INCLUDE_OCR=false
KNOWLEDGE_MAX_CHUNKS=0
"""


def main():
    (ROOT / "README.md").write_text(BODY_ZH, encoding="utf-8", newline="\n")
    (ROOT / ".env.example").write_text(ENV_EX, encoding="utf-8", newline="\n")
    print("OK: README.md and .env.example updated")


if __name__ == "__main__":
    main()
