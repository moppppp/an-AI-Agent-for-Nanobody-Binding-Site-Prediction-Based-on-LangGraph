# nanobody_agent — 纳米抗体 LangGraph 智能体

基于 **LangGraph** 的纳米抗体结合位点智能体。

## 配置 DeepSeek API Key（必做）

RAG 生成、对话摘要等需要调用 **DeepSeek**（OpenAI 兼容接口）。**本仓库不包含任何有效 API Key**，请自行申请后写入本地 `.env`。

### 步骤

1. 打开 [DeepSeek 开放平台](https://platform.deepseek.com/) 注册并创建 API Key。
2. 复制环境变量模板：
   - Windows: `copy .env.example .env`
   - Linux/macOS: `cp .env.example .env`
3. 编辑 **`.env`**（已在 `.gitignore` 中，**勿提交到 GitHub**）：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-请替换为你的真实密钥
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

4. 保存后执行 `python run_web.py`。Key 为空或错误时，问答与摘要将无法正常工作。

可选：使用 OpenAI 时设 `LLM_PROVIDER=openai` 并填 `OPENAI_API_KEY`。

## 快速开始

```bash
cd nanobody_agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
docker compose -f compose.redis.yaml up -d
python run_web.py
```

浏览器：http://127.0.0.1:8765

## 知识库

PDF → `knowledge_base/pdfs/` → `python ingest_pdfs.py`

## 评测

`python scripts/eval/eval_routing.py`

## NanoKGAT

默认 `NANOKGAT_USE_STUB=true`（Stub 演示）。真实 GNN：`NANOKGAT_USE_STUB=false` + `NANOKGAT_PYTHON_MODULE`，见 `src/nanobody_agent/nanokgat_adapter.py`。

## 领域工具层

噬菌体展示库 SQL、LIMS（SPR/ELISA）、本地 PDB 结构库、Rosetta/FoldX/AlphaFold 作业（`JOB_SCHEDULER=stub|slurm|k8s`）。配置见 `env.example` 中 `TOOLS_*` 项。

```powershell
python main.py "查询噬菌体展示库 PD-L1 KD 小于 20nM"
python main.py "NB-001 SPR 动力学"
python main.py "PDB 1ABC 链 A 与链 B 残基接触"
python main.py "FoldX 突变扫描 ddG RMSD"
python scripts/verify_domain_tools.py
```

审计日志：`outputs/tool_audit/tool_calls.jsonl`
