"""Local OCR for scanned images and scanned PDFs.

Engine: RapidOCR (ONNX Runtime) — runs fully on this machine.
PDF: PyMuPDF renders scanned pages to images when no usable text layer
exists; digital PDFs with a text layer are read directly (also local).

No network calls. No cloud OCR. Failures raise OcreError (clear failure).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

SUPPORTED_IMAGE_TYPES = frozenset({
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/bmp",
    "image/tiff",
})
SUPPORTED_PDF_TYPES = frozenset({"application/pdf"})
SUPPORTED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".pdf"})

_MIN_TEXT_LAYER_CHARS = 20
_PATH_SEPARATORS = re.compile(r"[/\\]")


class OcreError(Exception):
    """OCR failed (unsupported input, engine error, empty extraction)."""


@dataclass
class OcrPage:
    page_number: int
    text: str
    char_count: int
    source: str  # "text_layer" | "rapidocr" | "image_ocr"


@dataclass
class OcrResult:
    source_name: str
    text: str
    status: str  # completed | failed
    engine: str
    content_type: str
    page_count: int
    char_count: int
    pages: list[OcrPage] = field(default_factory=list)
    local_processing: bool = True
    error: str | None = None


def sanitize_source_name(filename: str | None, fallback: str = "scanned_document") -> str:
    """Basename only — never expose filesystem paths to clients."""
    if not filename:
        return fallback
    base = _PATH_SEPARATORS.split(str(filename))[-1].strip()
    base = os.path.basename(base)
    if not base or base in {".", ".."}:
        return fallback
    return base[:200]


def _extension(filename: str) -> str:
    return os.path.splitext(sanitize_source_name(filename))[1].lower()


def is_supported(filename: str | None, content_type: str | None = None) -> bool:
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct in SUPPORTED_IMAGE_TYPES or ct in SUPPORTED_PDF_TYPES:
            return True
    return _extension(filename or "") in SUPPORTED_EXTENSIONS


def _get_rapidocr():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _ocr_image_array(image) -> tuple[str, float | None]:
    import numpy as np

    rgb = image.convert("RGB")
    arr = np.asarray(rgb)
    engine = _get_rapidocr()
    result, elapse = engine(arr)
    if not result:
        return "", None
    lines: list[str] = []
    scores: list[float] = []
    for item in result:
        # rapidocr returns [box, text, score]
        if len(item) >= 3:
            text = str(item[1]).strip()
            try:
                scores.append(float(item[2]))
            except (TypeError, ValueError):
                pass
            if text:
                lines.append(text)
        elif len(item) == 2:
            text = str(item[0]).strip() if not isinstance(item[0], str) else str(item[1]).strip()
            if text:
                lines.append(text)
    avg = (sum(scores) / len(scores)) if scores else None
    return "\n".join(lines), avg


def _ocr_image_path(path: str) -> tuple[str, float | None]:
    from PIL import Image

    with Image.open(path) as img:
        return _ocr_image_array(img)


def _ocr_pdf(path: str) -> tuple[list[OcrPage], str]:
    import pymupdf  # local PDF renderer/reader

    doc = pymupdf.open(path)
    try:
        pages: list[OcrPage] = []
        layer_texts: list[str] = []
        for i, page in enumerate(doc, start=1):
            layer = page.get_text("text") or ""
            layer_texts.append(layer)

        total_layer = "".join(layer_texts)
        if len(total_layer.strip()) >= _MIN_TEXT_LAYER_CHARS:
            for i, layer in enumerate(layer_texts, start=1):
                pages.append(
                    OcrPage(
                        page_number=i,
                        text=layer.strip(),
                        char_count=len(layer.strip()),
                        source="text_layer",
                    )
                )
            return pages, "pymupdf-text-layer"

        # Scanned PDF — render each page and run local RapidOCR.
        from PIL import Image

        engine_pages: list[OcrPage] = []
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0), alpha=False)
            mode = "RGB" if pix.n >= 3 else "RGBA"
            img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
            text, _score = _ocr_image_array(img)
            text = text.strip()
            engine_pages.append(
                OcrPage(
                    page_number=i,
                    text=text,
                    char_count=len(text),
                    source="rapidocr",
                )
            )
        return engine_pages, "rapidocr-local"
    finally:
        doc.close()


def run_local_ocr(
    path: str,
    *,
    source_name: str | None = None,
    content_type: str | None = None,
) -> OcrResult:
    """Run local OCR on a scanned image or PDF. Raises OcreError on failure."""
    safe_name = sanitize_source_name(source_name or os.path.basename(path))
    if not os.path.isfile(path):
        raise OcreError("Document not found")

    ext = _extension(safe_name if source_name else path)
    ct = (content_type or "").split(";")[0].strip().lower()

    if ext == ".pdf" or ct in SUPPORTED_PDF_TYPES:
        try:
            pages, engine = _ocr_pdf(path)
        except OcreError:
            raise
        except Exception as exc:  # engine/runtime failure — fail clearly
            raise OcreError(f"Local PDF OCR failed: {exc}") from exc
        combined = "\n\n".join(p.text for p in pages if p.text).strip()
        if not combined:
            raise OcreError("OCR produced no extractable text from PDF")
        return OcrResult(
            source_name=safe_name,
            text=combined,
            status="completed",
            engine=engine,
            content_type=ct or "application/pdf",
            page_count=len(pages),
            char_count=len(combined),
            pages=pages,
            local_processing=True,
        )

    if ext in SUPPORTED_EXTENSIONS - {".pdf"} or ct in SUPPORTED_IMAGE_TYPES:
        try:
            text, _score = _ocr_image_path(path)
        except Exception as exc:
            raise OcreError(f"Local image OCR failed: {exc}") from exc
        text = (text or "").strip()
        if not text:
            raise OcreError("OCR produced no extractable text from image")
        page = OcrPage(page_number=1, text=text, char_count=len(text), source="image_ocr")
        return OcrResult(
            source_name=safe_name,
            text=text,
            status="completed",
            engine="rapidocr-local",
            content_type=ct or f"image/{ext.lstrip('.')}",
            page_count=1,
            char_count=len(text),
            pages=[page],
            local_processing=True,
        )

    raise OcreError(
        f"Unsupported input for local OCR: {safe_name or ct or 'unknown'} "
        f"(supported: PNG, JPEG, PDF)"
    )
