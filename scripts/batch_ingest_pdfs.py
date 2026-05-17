#!/usr/bin/env python3
"""Batch ingest PDFs from knowledge_base/pdfs into ingested/ and optional OCR."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> None:
    parser = argparse.ArgumentParser(description="批量 PDF 入库")
    parser.add_argument("--ocr", action="store_true", help="扫描件走 OCR 分支")
    parser.add_argument("--pdf-dir", type=Path, default=ROOT / "knowledge_base" / "pdfs")
    args = parser.parse_args()

    pdf_dir = args.pdf_dir
    pdfs = list(pdf_dir.glob("**/*.pdf"))
    print(f"发现 PDF: {len(pdfs)} 个")
    if not pdfs:
        print("请将 PDF 放入 knowledge_base/pdfs/")
        return

    if args.ocr:
        from ingest_pdfs_ocr import main as ocr_main  # type: ignore[import-not-found]

        ocr_main()
    else:
        from nanobody_agent.pdf_ingest import ingest_pdf_dir

        out = ROOT / "knowledge_base" / "ingested"
        paths = ingest_pdf_dir(pdf_dir, out)
        print(f"文本层入库完成，输出目录: {out}，生成 {len(paths)} 个 md 文件")


if __name__ == "__main__":
    main()
