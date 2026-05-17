from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nanobody_agent.pdf_ingest import ingest_pdf_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF -> markdown (tables + formulas + text)")
    parser.add_argument("--input", type=Path, default=ROOT / "knowledge_base" / "pdfs")
    parser.add_argument("--output", type=Path, default=ROOT / "knowledge_base" / "ingested")
    parser.add_argument("--min-chars", type=int, default=20)
    parser.add_argument("--max-chars", type=int, default=1200)
    parser.add_argument("--table-header-rows", type=int, default=1)
    parser.add_argument("--formula-min-chars", type=int, default=6)
    parser.add_argument("--no-tables", action="store_true")
    parser.add_argument("--no-formulas", action="store_true")
    parser.add_argument("--tables-only", action="store_true")
    parser.add_argument("--no-captions", action="store_true", help="Skip figure caption extraction")
    parser.add_argument("--caption-context", type=int, default=2, help="Lines before caption for ref text")
    args = parser.parse_args()

    if not args.input.is_dir():
        print("Create folder and add PDFs:", args.input)
        sys.exit(1)

    paths = ingest_pdf_dir(
        args.input,
        args.output,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
        extract_tables=not args.no_tables,
        table_header_rows=args.table_header_rows,
        include_body_text=not args.tables_only,
        merge_formulas=not args.no_formulas,
        formula_min_chars=args.formula_min_chars,
        extract_captions=not args.no_captions,
        caption_context_before=args.caption_context,
    )
    if not paths:
        print("No PDF found under:", args.input)
        sys.exit(0)
    print("Wrote", len(paths), "file(s):")
    for p in paths:
        print(" ", p)
    print("Next: python main.py")


if __name__ == "__main__":
    main()
