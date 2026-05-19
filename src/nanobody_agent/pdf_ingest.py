from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

_MATH_SYMBOLS = set("=+-*/^_{}[]()<>|\\")
_EQ_NUMBER_TAIL = re.compile(r"[\(\uFF08]\s*\d+(?:[.\-]\d+)?\s*[\)\uFF09]\s*$")
_LATEX_HINT = re.compile(r"(\\frac|\\sum|\\int|\\sqrt|_\{|\\\()", re.I)
# 其中|我们通过|因此|所以|本文
_PROSE_BREAK = re.compile(
    r"^(\u5176\u4e2d|\u6211\u4eec\u901a\u8fc7|\u56e0\u6b64|\u6240\u4ee5|\u672c\u6587|Therefore|Hence|In this paper|We propose)",
    re.I,
)
_GARBAGE_ONLY = re.compile(r"^[\s\u200a\u200b\u202f\u00a0]{0,8}$")
_PAGE_FOOTER = re.compile(
    r"(\u7b2c\s*\d+\s*\u9875|\u5171\s*\d+\s*\u9875|Page\s+\d+|page\s+\d+\s+of\s+\d+)",
    re.I,
)
_SECTION_HEAD = re.compile(
    r"^\d+\.\d+[\s\u4e00-\u9fff]|^\d+[\)\u3001]\s*[\u4e00-\u9fff]|^\d+\.\d+\s+[A-Za-z]|^\d+[\).]\s+[A-Za-z]",
)
_CAPTION_START = re.compile(
    r"^(\u56fe\s*[\d\.\-–—]+|Fig\.?\s*[\d\.\-]+|Figure\s+[\d\.\-]+|FIG\.?\s*[\d\.\-]+|"
    r"\u63d2\u56fe\s*[\d\.\-]+|Table\s+[\d\.\-]+|\u8868\s*[\d\.\-]+)",
    re.I,
)
_REF_FIGURE = re.compile(
    r"(\u5982\u56fe|\u89c1\u56fe|\u5982\u4e0b\u56fe|\u5982\u4e0a\u56fe|"
    r"as shown in Fig|shown in Figure|see Figure|see Fig|illustrated in Fig)",
    re.I,
)


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()


def _pad_headers(headers: list[str], width: int) -> list[str]:
    out = list(headers)
    while len(out) < width:
        out.append(f"col{len(out) + 1}")
    return out


def table_to_header_merged_chunks(
    data: list[list],
    *,
    page_no: int,
    table_no: int,
    header_rows: int = 1,
    min_chars: int = 20,
) -> list[str]:
    if not data:
        return []
    rows = [[_clean_cell(c) for c in row] for row in data if row is not None]
    rows = [r for r in rows if any(c for c in r)]
    if not rows or len(rows) <= max(1, header_rows):
        return []
    width = max(len(r) for r in rows)
    headers: list[str] = [""] * width
    for r in range(max(1, header_rows)):
        for j, cell in enumerate(_pad_headers(rows[r], width)):
            if cell:
                headers[j] = f"{headers[j]} {cell}".strip() if headers[j] else cell
    for j in range(width):
        if not headers[j]:
            headers[j] = f"col{j + 1}"
    out: list[str] = []
    pre = f"[Table p{page_no} t{table_no}] "
    for ri, row in enumerate(rows[max(1, header_rows) :], start=max(1, header_rows) + 1):
        row = _pad_headers(row, width)
        pairs = [f"{h}: {v}" for h, v in zip(headers, row) if v]
        if not pairs:
            continue
        body = "; ".join(pairs)
        out.append(pre + body if len(pre + body) >= min_chars else f"{pre}row {ri}: {body}")
    return out


def extract_tables_from_page(page: object, page_no: int, *, header_rows: int = 1, min_chars: int = 20) -> list[str]:
    if not hasattr(page, "find_tables"):
        return []
    try:
        tables = page.find_tables().tables
    except Exception:
        return []
    chunks: list[str] = []
    for ti, table in enumerate(tables, start=1):
        try:
            chunks.extend(
                table_to_header_merged_chunks(
                    table.extract(), page_no=page_no, table_no=ti, header_rows=header_rows, min_chars=min_chars
                )
            )
        except Exception:
            continue
    return chunks


def _table_bboxes(page: object) -> list:
    import fitz

    if not hasattr(page, "find_tables"):
        return []
    try:
        return [fitz.Rect(t.bbox) for t in page.find_tables().tables]
    except Exception:
        return []


def extract_body_text_excluding_tables(page: object, table_bboxes: list) -> str:
    import fitz

    parts: list[str] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        bbox = fitz.Rect(block["bbox"])
        area = bbox.get_area() or 1.0
        if any(not (bbox & tb).is_empty and ((bbox & tb).get_area() / area) > 0.45 for tb in table_bboxes):
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                t = (span.get("text") or "").strip()
                if t:
                    parts.append(t)
            parts.append("\n")
    return _normalize("".join(parts))


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\u200a\u200b\u202f]+", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _is_unicode_math_char(c: str) -> bool:
    if len(c) != 1:
        return False
    o = ord(c)
    if c in _MATH_SYMBOLS:
        return True
    if 0x1D400 <= o <= 0x1D7FF:
        return True
    if 0x2100 <= o <= 0x214F:
        return True
    if 0x2070 <= o <= 0x209F:
        return True
    if 0x2200 <= o <= 0x22FF:
        return True
    return False


def _cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    return sum(1 for c in text if "\u4e00" <= c <= "\u9fff") / len(text)


def _unicode_math_ratio(text: str) -> float:
    t = text.strip()
    if not t:
        return 0.0
    return sum(1 for c in t if _is_unicode_math_char(c)) / len(t)


def _math_density(text: str) -> float:
    t = text.strip()
    if not t:
        return 0.0
    return sum(1 for c in t if _is_unicode_math_char(c) or c.isdigit()) / len(t)


def _clean_formula_line(line: str) -> str:
    t = line.strip()
    t = re.sub(r"[\u200a\u200b\u202f]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _is_skippable_gap_line(line: str) -> bool:
    t = line.strip()
    if not t:
        return True
    if _GARBAGE_ONLY.match(t):
        return True
    return len(t) <= 2 and _unicode_math_ratio(t) < 0.15


def _is_noise_line(line: str) -> bool:
    t = _clean_formula_line(line)
    if not t:
        return True
    if _PAGE_FOOTER.search(t) and (_unicode_math_ratio(t) < 0.22 or _cjk_ratio(t) > 0.12):
        return True
    if _SECTION_HEAD.match(t):
        return True
    if re.match(r"^\d+[\)\u3001]", t) and _cjk_ratio(t) > 0.30 and _unicode_math_ratio(t) < 0.12:
        return True
    return False


def _formula_looks_incomplete(text: str) -> bool:
    t = text.strip()
    if _EQ_NUMBER_TAIL.search(t):
        return False
    if re.search(r"[=,\uFF0C+\-*/(\[\{]$", t):
        return True
    if "=" in t:
        return True
    return False


def _is_valid_formula_chunk(text: str) -> bool:
    t = text.strip()
    if not t or _is_noise_line(t):
        return False
    if _cjk_ratio(t) > 0.38 and _unicode_math_ratio(t) < 0.10:
        return False
    if _PAGE_FOOTER.search(t) and _unicode_math_ratio(t) < 0.14:
        return False
    um = _unicode_math_ratio(t)
    if _EQ_NUMBER_TAIL.search(t):
        return um >= 0.02 or "=" in t
    if "=" in t and um >= 0.04:
        return True
    return um >= 0.12


def _coalesce_formula_segments(
    segs: list[tuple[Literal["formula", "formula_note", "text"], str]],
) -> list[tuple[Literal["formula", "formula_note", "text"], str]]:
    out: list[tuple[Literal["formula", "formula_note", "text"], str]] = []
    for kind, content in segs:
        if kind != "formula":
            out.append((kind, content))
            continue
        c = content.strip()
        if out and out[-1][0] == "formula":
            prev = out[-1][1].strip()
            if _formula_looks_incomplete(prev) or (
                not _EQ_NUMBER_TAIL.search(prev) and (_EQ_NUMBER_TAIL.search(c) or _unicode_math_ratio(c) >= 0.05)
            ):
                merged = re.sub(r"\s+", " ", f"{prev} {c}").strip()
                out[-1] = ("formula", merged)
                continue
        out.append((kind, c))
    return out


def _ends_formula_block(line: str) -> bool:
    t = line.strip()
    if not t:
        return False
    if _PROSE_BREAK.match(t):
        return True
    if _cjk_ratio(t) > 0.50 and _unicode_math_ratio(t) < 0.05 and len(t) > 14:
        return True
    return False


def _is_prose_line(line: str) -> bool:
    t = line.strip()
    if _unicode_math_ratio(t) >= 0.08:
        return False
    if _PROSE_BREAK.match(t):
        return True
    return len(t) >= 10 and _cjk_ratio(t) >= 0.40 and _math_density(t) < 0.08


def _is_formula_line(line: str) -> bool:
    t = _clean_formula_line(line)
    if not t or _is_prose_line(t) or _is_noise_line(t):
        return False
    if _LATEX_HINT.search(t):
        return True
    um = _unicode_math_ratio(t)
    if _EQ_NUMBER_TAIL.search(t):
        return um >= 0.02 or "=" in t
    if "=" not in t and um < 0.14:
        return False
    if um >= 0.12 and "=" in t:
        return True
    if um >= 0.08 and ("=" in t or "\u2211" in t or "\u2208" in t):
        return True
    return bool(re.search(r"[A-Za-z]\s*=\s*", t) and um >= 0.08 and _cjk_ratio(t) < 0.25)


def _is_formula_note_line(line: str) -> bool:
    t = line.strip()
    if t.startswith("\u5176\u4e2d"):
        return True
    if re.match(r"^\d+\.", t) and (
        _unicode_math_ratio(t) > 0.02
        or "\u8282\u70b9" in t
        or "\u5c42" in t
        or "\u6743\u91cd" in t
    ):
        return True
    return False


def _is_formula_continuation(line: str, buf: list[str]) -> bool:
    if not buf:
        return False
    t = line.strip()
    if _is_noise_line(t):
        return False
    if _ends_formula_block(t) or _is_formula_note_line(t):
        return False
    if _is_skippable_gap_line(t):
        return True
    if _is_formula_line(t):
        return True
    prev = _clean_formula_line(buf[-1])
    if t and t[0] in ")=+-*/,.;:]})]":
        return True
    if prev and prev[-1] in "=+-*/({},[<":
        return True
    if _unicode_math_ratio(t) >= 0.05:
        return True
    return _math_density(t) >= 0.08 and len(t) <= 250


def _merge_formula_lines(lines: list[str]) -> str:
    parts: list[str] = []
    for ln in lines:
        t = _clean_formula_line(ln)
        if t and not _is_skippable_gap_line(t):
            parts.append(t)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _merge_formula_note_lines(lines: list[str]) -> str:
    return "\n".join(_clean_formula_line(ln) for ln in lines if _clean_formula_line(ln))


def _is_caption_start(line: str) -> bool:
    t = line.strip()
    if not t or _is_noise_line(t):
        return False
    return bool(_CAPTION_START.match(t))


def _is_caption_continuation(line: str) -> bool:
    t = line.strip()
    if not t or _is_caption_start(t) or _is_formula_line(t) or _is_noise_line(t):
        return False
    if _SECTION_HEAD.match(t):
        return False
    if len(t) > 280:
        return False
    if _cjk_ratio(t) >= 0.15:
        return True
    return len(t) < 100 and not re.match(r"^\d+\.\d+", t)


def extract_figure_captions_from_body(
    body: str,
    page_no: int,
    *,
    min_chars: int = 15,
    context_lines_before: int = 2,
) -> tuple[list[str], str]:
    """Pull figure captions and nearby reference sentences from PDF text layer."""
    body = _normalize(body)
    if not body:
        return [], body
    lines = body.split("\n")
    caption_chunks: list[str] = []
    out_lines: list[str] = []
    i, n = 0, len(lines)
    cap_idx = 0

    while i < n:
        if not _is_caption_start(lines[i]):
            out_lines.append(lines[i])
            i += 1
            continue

        block: list[str] = []
        start = max(0, i - context_lines_before)
        for j in range(start, i):
            prev = lines[j].strip()
            if not prev or _is_noise_line(prev):
                continue
            if _REF_FIGURE.search(prev) or len(prev) < 160:
                if prev not in block:
                    block.append(prev)

        block.append(lines[i].strip())
        i += 1
        while i < n and _is_caption_continuation(lines[i]):
            block.append(lines[i].strip())
            i += 1

        text = re.sub(r"\s+", " ", " ".join(block)).strip()
        if len(text) >= min_chars and not _PAGE_FOOTER.search(text):
            cap_idx += 1
            caption_chunks.append(f"[Figure-caption p{page_no} #{cap_idx}] {text}")

    return caption_chunks, "\n".join(out_lines)


def _extract_inline_figure_refs_from_text(
    text: str,
    page_no: int,
    *,
    min_chars: int = 20,
) -> tuple[list[str], str]:
    """Paragraphs that reference figures but are not caption lines."""
    if not text.strip():
        return [], text
    ref_chunks: list[str] = []
    kept: list[str] = []
    ref_idx = 0
    for para in re.split(r"\n{2,}", text):
        p = para.strip()
        if not p:
            continue
        if _CAPTION_START.match(p):
            kept.append(p)
            continue
        if _REF_FIGURE.search(p) and len(p) >= min_chars:
            ref_idx += 1
            ref_chunks.append(f"[Figure-ref p{page_no} #{ref_idx}] {p}")
        else:
            kept.append(p)
    return ref_chunks, "\n\n".join(kept)


def split_body_into_segments(
    body: str,
) -> list[tuple[Literal["formula", "formula_note", "text"], str]]:
    body = _normalize(body)
    if not body:
        return []
    lines = body.split("\n")
    segs: list[tuple[Literal["formula", "formula_note", "text"], str]] = []
    i, n = 0, len(lines)

    while i < n:
        while i < n and not lines[i].strip():
            i += 1
        if i >= n:
            break

        if _is_formula_line(lines[i]):
            buf = [lines[i]]
            i += 1
            while i < n:
                nxt = lines[i]
                if _ends_formula_block(nxt) or _is_formula_note_line(nxt):
                    break
                if _is_skippable_gap_line(nxt):
                    i += 1
                    continue
                if _is_formula_continuation(nxt, buf):
                    buf.append(nxt)
                    i += 1
                else:
                    break
            segs.append(("formula", _merge_formula_lines(buf)))

            if i < n and _is_formula_note_line(lines[i]):
                note_buf = [lines[i]]
                i += 1
                while i < n:
                    nxt = lines[i]
                    if not nxt.strip():
                        i += 1
                        break
                    if _is_formula_line(nxt):
                        break
                    if _is_formula_note_line(nxt) or (
                        _unicode_math_ratio(nxt) > 0.02 and len(nxt.strip()) < 150
                    ):
                        note_buf.append(nxt)
                        i += 1
                    elif _ends_formula_block(nxt) or _is_prose_line(nxt):
                        break
                    else:
                        break
                segs.append(("formula_note", _merge_formula_note_lines(note_buf)))
            continue

        buf = [lines[i]]
        i += 1
        while i < n and lines[i].strip() and not _is_formula_line(lines[i]):
            buf.append(lines[i])
            i += 1
        t = "\n".join(buf).strip()
        if t:
            segs.append(("text", t))
    return _coalesce_formula_segments(segs)


def chunk_page_text(text: str, *, min_chars: int = 20, max_chars: int = 1200) -> list[str]:
    text = _normalize(text)
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paras:
        paras = [ln.strip() for ln in text.split("\n") if ln.strip()]
    out: list[str] = []
    buf = ""
    for para in paras:
        if len(para) < min_chars and buf:
            buf = f"{buf}\n{para}"
            continue
        if buf:
            out.append(buf)
            buf = ""
        if len(para) < min_chars:
            buf = para
        elif len(para) <= max_chars:
            out.append(para)
        else:
            for k in range(0, len(para), max_chars):
                part = para[k : k + max_chars].strip()
                if len(part) >= min_chars:
                    out.append(part)
    if buf and len(buf) >= min_chars:
        out.append(buf)
    return out


def body_to_chunks(
    body: str,
    page_no: int,
    *,
    min_chars: int = 20,
    max_chars: int = 1200,
    formula_min_chars: int = 6,
    merge_formulas: bool = True,
    extract_captions: bool = True,
    caption_context_before: int = 2,
) -> tuple[list[str], list[str], list[str]]:
    fchunks: list[str] = []
    cap_chunks: list[str] = []
    texts: list[str] = []

    if extract_captions:
        cap_chunks, body = extract_figure_captions_from_body(
            body, page_no, min_chars=min(15, min_chars), context_lines_before=caption_context_before
        )

    segs = split_body_into_segments(body) if merge_formulas else [("text", body)]
    fi = 0
    for kind, content in segs:
        m = content.strip()
        if not m:
            continue
        if kind == "formula":
            if len(m) >= formula_min_chars and _is_valid_formula_chunk(m):
                fi += 1
                fchunks.append(f"[Formula p{page_no} #{fi}] {m}")
        elif kind == "formula_note":
            fchunks.append(f"[Formula-note p{page_no}] {m}")
        else:
            texts.append(m)

    joined = "\n\n".join(texts)
    if extract_captions:
        ref_chunks, joined = _extract_inline_figure_refs_from_text(joined, page_no, min_chars=min_chars)
        cap_chunks.extend(ref_chunks)

    return fchunks, cap_chunks, chunk_page_text(joined, min_chars=min_chars, max_chars=max_chars)


def pdf_to_markdown(
    pdf_path: Path,
    *,
    min_chars: int = 20,
    max_chars: int = 1200,
    extract_tables: bool = True,
    table_header_rows: int = 1,
    include_body_text: bool = True,
    merge_formulas: bool = True,
    formula_min_chars: int = 6,
    extract_captions: bool = True,
    caption_context_before: int = 2,
) -> str:
    import fitz
    from datetime import datetime

    year_m = re.search(r"(20\d{2})", pdf_path.stem)
    try:
        mtime = int(pdf_path.stat().st_mtime)
        pub_year = year_m.group(1) if year_m else str(datetime.fromtimestamp(mtime).year)
    except OSError:
        mtime = 0
        pub_year = year_m.group(1) if year_m else ""
    lines = [
        f"# {pdf_path.stem}",
        "",
        f"<!-- kb-meta: source={pdf_path.name} year={pub_year} version={mtime} -->",
        f"<!-- source: {pdf_path.name} -->",
        "",
    ]
    total = 0
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            pno = i + 1
            tboxes = _table_bboxes(page) if extract_tables else []
            if extract_tables:
                tc = extract_tables_from_page(page, pno, header_rows=table_header_rows, min_chars=min_chars)
                if tc:
                    lines += [f"## Page {pno} - Tables", ""]
                    for c in tc:
                        lines += [c, ""]
                        total += 1
            if include_body_text:
                body = extract_body_text_excluding_tables(page, tboxes) if tboxes else (page.get_text("text") or "")
                fc, cc, tx = body_to_chunks(
                    body,
                    pno,
                    min_chars=min_chars,
                    max_chars=max_chars,
                    formula_min_chars=formula_min_chars,
                    merge_formulas=merge_formulas,
                    extract_captions=extract_captions,
                    caption_context_before=caption_context_before,
                )
                if cc:
                    lines += [f"## Page {pno} - Figure-captions", ""]
                    for c in cc:
                        lines += [c, ""]
                        total += 1
                if fc:
                    lines += [f"## Page {pno} - Formulas", ""]
                    for c in fc:
                        lines += [c, ""]
                        total += 1
                if tx:
                    lines += [f"## Page {pno} - Text", ""]
                    for c in tx:
                        lines += [c, ""]
                        total += 1
    if total == 0:
        lines += [
            "_(Nothing extracted from text layer. Likely scanned PDF: run "
            "`python ingest_pdfs_ocr.py` after `pip install -r requirements-ocr.txt`.)_",
            "",
        ]
    return "\n".join(lines).strip() + "\n"


def ingest_pdf_dir(
    input_dir: Path,
    output_dir: Path,
    *,
    min_chars: int = 20,
    max_chars: int = 1200,
    extract_tables: bool = True,
    table_header_rows: int = 1,
    include_body_text: bool = True,
    merge_formulas: bool = True,
    formula_min_chars: int = 6,
    extract_captions: bool = True,
    caption_context_before: int = 2,
) -> list[Path]:
    input_dir, output_dir = input_dir.resolve(), output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(input_dir.rglob("*.pdf"))
    written: list[Path] = []
    for pdf in pdfs:
        out = output_dir / pdf.relative_to(input_dir).with_suffix(".md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            pdf_to_markdown(
                pdf,
                min_chars=min_chars,
                max_chars=max_chars,
                extract_tables=extract_tables,
                table_header_rows=table_header_rows,
                include_body_text=include_body_text,
                merge_formulas=merge_formulas,
                formula_min_chars=formula_min_chars,
                extract_captions=extract_captions,
                caption_context_before=caption_context_before,
            ),
            encoding="utf-8",
            newline="\n",
        )
        written.append(out)
    return written
