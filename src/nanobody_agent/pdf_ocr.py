from __future__ import annotations

import os
import re
import warnings
from pathlib import Path
from typing import Callable

# Paddle: disable oneDNN before import (Windows CPU PIR bug on 3.3+).
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

_PADDLE_OCR_CACHE: dict[str, object] = {}
_RAPID_OCR_CACHE: object | None = None
_DISABLED_BACKENDS: set[str] = set()
_ACTIVE_BACKEND: str | None = None
_VERBOSE: bool = False


def set_ocr_verbose(enabled: bool = True) -> None:
    global _VERBOSE
    _VERBOSE = enabled


def _progress(msg: str) -> None:
    if _VERBOSE:
        print(msg, flush=True)


def _fix_win_dll_paths() -> None:
    """Help Paddle/PyTorch find native DLLs on Windows."""
    if os.name != "nt":
        return
    for mod_name, sub in (("torch", "lib"), ("paddle", "libs")):
        try:
            mod = __import__(mod_name)
            lib_dir = os.path.join(os.path.dirname(mod.__file__), sub)
            if os.path.isdir(lib_dir):
                os.add_dll_directory(lib_dir)
        except Exception:
            pass


def _configure_paddle_runtime() -> None:
    _fix_win_dll_paths()
    os.environ["FLAGS_use_mkldnn"] = "0"
    try:
        import paddle

        paddle.set_flags({"FLAGS_use_mkldnn": False})
    except Exception:
        pass


def get_active_ocr_backend() -> str | None:
    return _ACTIVE_BACKEND


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _page_to_numpy(page: object, dpi: int = 200):
    import fitz
    import numpy as np

    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    return img


def _get_rapid_ocr():
    global _RAPID_OCR_CACHE
    if _RAPID_OCR_CACHE is None:
        _progress("Loading RapidOCR (first run may download models, 1-3 min)...")
        from rapidocr_onnxruntime import RapidOCR

        _RAPID_OCR_CACHE = RapidOCR()
        _progress("RapidOCR ready.")
    return _RAPID_OCR_CACHE


def _ocr_image_rapidocr(img, lang: str) -> str:
    # RapidOCR: ONNX only, no Paddle/Torch — recommended on Windows.
    del lang  # default model covers Chinese + English
    ocr = _get_rapid_ocr()
    result, _ = ocr(img)
    if not result:
        return ""
    lines: list[str] = []
    for item in result:
        if item and len(item) >= 2 and item[1]:
            lines.append(str(item[1]))
    return "\n".join(lines)


def _create_paddle_ocr(lang: str):
    _progress("Loading PaddleOCR (slow; may download large models)...")
    _configure_paddle_runtime()
    from paddleocr import PaddleOCR

    attempts = [
        {
            "lang": lang,
            "ocr_version": "PP-OCRv4",
            "enable_mkldnn": False,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        },
        {
            "lang": lang,
            "enable_mkldnn": False,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        },
        {"lang": lang, "enable_mkldnn": False},
        {"lang": lang},
    ]
    last_err: Exception | None = None
    for kw in attempts:
        try:
            return PaddleOCR(**kw)
        except (ValueError, TypeError) as e:
            last_err = e
    if last_err:
        raise last_err
    return PaddleOCR(lang=lang, enable_mkldnn=False)


def _get_paddle_ocr(lang: str):
    if lang not in _PADDLE_OCR_CACHE:
        _PADDLE_OCR_CACHE[lang] = _create_paddle_ocr(lang)
    return _PADDLE_OCR_CACHE[lang]


def _extract_rec_texts(result) -> list[str]:
    lines: list[str] = []
    if result is None:
        return lines
    pages = result if isinstance(result, list) else [result]
    for page in pages:
        if page is None:
            continue
        texts = None
        if isinstance(page, dict):
            texts = page.get("rec_texts")
        else:
            try:
                texts = page["rec_texts"]
            except (KeyError, TypeError, AttributeError):
                texts = None
        if texts:
            lines.extend(str(t) for t in texts if t)
            continue
        if isinstance(page, list):
            for line in page:
                if line and len(line) >= 2 and line[1]:
                    rec = line[1]
                    if isinstance(rec, (list, tuple)) and rec:
                        lines.append(str(rec[0]))
                    elif isinstance(rec, str):
                        lines.append(rec)
    return lines


def _ocr_image_paddleocr(img, lang: str) -> str:
    ocr = _get_paddle_ocr(lang)
    try:
        result = ocr.predict(img)
    except AttributeError:
        try:
            result = ocr.ocr(img, cls=True)
        except TypeError:
            result = ocr.ocr(img)
    return "\n".join(_extract_rec_texts(result))


def _ocr_image_tesseract(img, lang: str) -> str:
    import pytesseract
    from PIL import Image

    if lang.startswith("ch"):
        tess_lang = "chi_sim+eng"
    else:
        tess_lang = "eng"
    pil = Image.fromarray(img)
    return pytesseract.image_to_string(pil, lang=tess_lang)


def _ocr_install_help() -> str:
    return (
        "No OCR backend available.\n"
        "Recommended (Windows, no Paddle/Torch):\n"
        "  pip install rapidocr-onnxruntime onnxruntime\n"
        "Optional Paddle:\n"
        "  pip install \"paddlepaddle>=3.2.0,<3.3.0\" paddleocr\n"
        "Optional Tesseract:\n"
        "  Install Tesseract-OCR, add to PATH, then: pip install pytesseract pillow"
    )


_OCR_BACKENDS: list[tuple[str, Callable]] = [
    ("rapidocr", _ocr_image_rapidocr),
    ("paddleocr", _ocr_image_paddleocr),
    ("tesseract", _ocr_image_tesseract),
]


def ocr_page_text(page: object, *, dpi: int = 200, lang: str = "ch") -> str:
    global _ACTIVE_BACKEND

    img = _page_to_numpy(page, dpi=dpi)
    for name, fn in _OCR_BACKENDS:
        if name in _DISABLED_BACKENDS:
            continue
        try:
            text = fn(img, lang)
        except ImportError:
            continue
        except Exception as e:
            _DISABLED_BACKENDS.add(name)
            warnings.warn(f"OCR backend {name!r} disabled: {type(e).__name__}: {e}", stacklevel=2)
            continue
        if _ACTIVE_BACKEND is None:
            _ACTIVE_BACKEND = name
            _progress(f"Using OCR backend: {name}")
        return text
    raise RuntimeError(_ocr_install_help())


def pdf_ocr_to_markdown(
    pdf_path: Path,
    *,
    dpi: int = 200,
    lang: str = "ch",
    min_chars: int = 20,
) -> str:
    import fitz
    from datetime import datetime

    try:
        mtime = int(pdf_path.stat().st_mtime)
        pub_year = str(datetime.fromtimestamp(mtime).year)
    except OSError:
        mtime, pub_year = 0, ""
    lines = [
        f"# {pdf_path.stem}",
        "",
        f"<!-- kb-meta: source={pdf_path.name} year={pub_year} version={mtime} -->",
        f"<!-- source: {pdf_path.name} (OCR dpi={dpi} lang={lang}) -->",
        "",
    ]
    total = 0
    with fitz.open(pdf_path) as doc:
        n_pages = len(doc)
        _progress(f"  {pdf_path.name}: {n_pages} page(s), dpi={dpi}")
        for i, page in enumerate(doc):
            pno = i + 1
            _progress(f"    OCR page {pno}/{n_pages}...")
            text = _normalize(ocr_page_text(page, dpi=dpi, lang=lang))
            if not text:
                continue
            paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
            if not paras:
                paras = [ln.strip() for ln in text.split("\n") if ln.strip()]
            kept = [p for p in paras if len(p) >= min_chars]
            if not kept:
                kept = [text] if len(text) >= 8 else []
            if not kept:
                continue
            lines += [f"## Page {pno} - OCR", ""]
            for p in kept:
                lines += [p, ""]
                total += 1
    if total == 0:
        lines += ["_(OCR produced no text; try higher dpi or different lang.)_", ""]
    return "\n".join(lines).strip() + "\n"


def page_text_layer_chars(page: object) -> int:
    return len((page.get_text("text") or "").strip())


def needs_ocr(pdf_path: Path, *, min_chars_per_page: int = 40) -> bool:
    import fitz

    with fitz.open(pdf_path) as doc:
        if len(doc) == 0:
            return True
        counts = [page_text_layer_chars(doc[i]) for i in range(len(doc))]
        avg = sum(counts) / max(len(counts), 1)
        return avg < min_chars_per_page


def ingest_pdf_dir_ocr(
    input_dir: Path,
    output_dir: Path,
    *,
    dpi: int = 200,
    lang: str = "ch",
    min_chars: int = 20,
) -> list[Path]:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(input_dir.rglob("*.pdf"))
    written: list[Path] = []
    for idx, pdf in enumerate(pdfs, start=1):
        _progress(f"[{idx}/{len(pdfs)}] {pdf.name}")
        out = output_dir / pdf.relative_to(input_dir).with_suffix(".md")
        out.parent.mkdir(parents=True, exist_ok=True)
        md = pdf_ocr_to_markdown(pdf, dpi=dpi, lang=lang, min_chars=min_chars)
        _progress(f"  -> wrote {out.name}")
        out.write_text(md, encoding="utf-8", newline="\n")
        written.append(out)
    return written
