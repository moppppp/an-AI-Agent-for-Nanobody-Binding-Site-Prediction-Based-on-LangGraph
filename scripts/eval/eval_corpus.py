#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from common import OUTPUTS, ROOT  # noqa: E402


def eval_corpus() -> dict:
    kb = ROOT / "knowledge_base"
    pdfs = list((kb / "pdfs").glob("**/*.pdf")) if (kb / "pdfs").is_dir() else []
    ingested = list((kb / "ingested").glob("**/*.md")) if (kb / "ingested").is_dir() else []
    ocr = list((kb / "ingested_ocr").glob("**/*.md")) if (kb / "ingested_ocr").is_dir() else []
    result = {
        "pdf_files_in_pdfs_dir": len(pdfs),
        "ingested_markdown": len(ingested),
        "ingested_ocr_markdown": len(ocr),
        "note": "200+ nanobody PDFs: compare pdf count vs ingested; run scripts/batch_ingest_pdfs.py",
    }
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    (OUTPUTS / "corpus_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    eval_corpus()
