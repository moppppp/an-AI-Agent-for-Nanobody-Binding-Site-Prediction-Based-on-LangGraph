#!/usr/bin/env python
"""将 PDF 解析为 knowledge_base 可用的 Markdown。

用法:
  pip install pymupdf
  python scripts/ingest_pdfs.py
  python scripts/ingest_pdfs.py --input knowledge_base/pdfs --output knowledge_base/ingested

然后把 PDF 放入 knowledge_base/pdfs/，运行本脚本，再启动 python main.py 重建索引。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nanobody_agent.pdf_ingest import ingest_pdf_dir  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse PDFs into knowledge_base markdown")
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "knowledge_base" / "pdfs",
        help="Directory containing .pdf files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "knowledge_base" / "ingested",
        help="Output directory for generated .md",
    )
    parser.add_argument("--min-chars", type=int, default=20, help="Min chars per chunk")
    parser.add_argument("--max-chars", type=int, default=1200, help="Max chars per chunk")
    args = parser.parse_args()

    if not args.input.is_dir():
        print(f"输入目录不存在，请先创建并放入 PDF: {args.input}")
        sys.exit(1)

    paths = ingest_pdf_dir(
        args.input,
        args.output,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
    )
    if not paths:
        print(f"未找到 PDF: {args.input}")
        sys.exit(0)

    print(f"已生成 {len(paths)} 个 Markdown 文件:")
    for p in paths:
        print(f"  {p}")
    print("\n下一步: python main.py  （启动时会自动加载 knowledge_base 下所有 .md）")


if __name__ == "__main__":
    main()
