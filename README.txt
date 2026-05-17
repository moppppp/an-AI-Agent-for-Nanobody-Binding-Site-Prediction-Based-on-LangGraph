# nanobody_agent — 纳米抗体 LangGraph 智能体

基于 **LangGraph** 的纳米抗体结合位点智能体，实现「知识检索 + 结合位点预测」协同：文献 RAG、多级路由与拒答、扩展检索、直连大模型、NanoKGAT 预测分支（默认 Stub，可对接真实 GNN）。

## 功能概览

| 模块 | 说明 |
|------|------|
| 工作流 | LangGraph：RAG、拒答、扩展检索、直连 LLM、位点预测 |
| 路由 | 规则意图 + FAISS/BM25 + BGE 灰区语义复核 |
| 知识库 | PyMuPDF / OCR 分块入库 |
| 会话 | 滑动窗口 + 对话摘要；Redis 可选 |
| Web | http://127.0.0.1:8765，支持 PDB 上传与引用展示 |

## 快速开始

```bash
cd nanobody_agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# 编辑 .env 填写 DEEPSEEK_API_KEY
docker compose -f compose.redis.yaml up -d
python run_web.py
```

命令行：`python main.py "什么是纳米抗体？"`

## 知识库

PDF 放入 `knowledge_base/pdfs/` → `python ingest_pdfs.py` / `python ingest_pdfs_ocr.py`

## 评测

```bash
python scripts/eval/seed_datasets.py
python scripts/eval/eval_routing.py
python scripts/eval/run_benchmarks.py --pdb-sample 20
```

## NanoKGAT

默认 `NANOKGAT_USE_STUB=true`。接入真实模型见 `src/nanobody_agent/nanokgat_adapter.py`。

## 许可证

请自行添加 LICENSE 文件。
