from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nanobody_agent.pdf_ocr import (
    get_active_ocr_backend,
    ingest_pdf_dir_ocr,
    needs_ocr,
    set_ocr_verbose,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR scanned PDFs into knowledge_base markdown")
    parser.add_argument("--input", type=Path, default=ROOT / "knowledge_base" / "pdfs")
    parser.add_argument("--output", type=Path, default=ROOT / "knowledge_base" / "ingested_ocr")
    parser.add_argument("--dpi", type=int, default=200, help="Render resolution (200-300 for scans)")
    parser.add_argument("--lang", choices=("ch", "en"), default="ch", help="ch=Chinese+English, en=English")
    parser.add_argument("--min-chars", type=int, default=20)
    parser.add_argument("--check", action="store_true", help="Only print whether PDFs need OCR")
    parser.add_argument("--quiet", action="store_true", help="No per-page progress output")
    args = parser.parse_args()

    if not args.input.is_dir():
        print("Create folder and add PDFs:", args.input)
        sys.exit(1)

    pdfs = sorted(args.input.rglob("*.pdf"))
    if not pdfs:
        print("No PDF under:", args.input)
        sys.exit(0)

    if args.check:
        for pdf in pdfs:
            flag = "NEED_OCR" if needs_ocr(pdf) else "text_layer_ok"
            print(flag, pdf.name)
        return

    set_ocr_verbose(not args.quiet)
    print(
        f"Found {len(pdfs)} PDF(s). CPU OCR is slow (~10-60 s/page); "
        f"first run may download models with no output for 1-3 min.",
        flush=True,
    )
    paths = ingest_pdf_dir_ocr(
        args.input,
        args.output,
        dpi=args.dpi,
        lang=args.lang,
        min_chars=args.min_chars,
    )
    backend = get_active_ocr_backend() or "unknown"
    print("OCR backend:", backend)
    print("Wrote", len(paths), "OCR markdown file(s) to:", args.output)
    for p in paths:
        print(" ", p)
    print("Next: copy or merge into knowledge_base/ingested, then: python main.py")


if __name__ == "__main__":
    main()
