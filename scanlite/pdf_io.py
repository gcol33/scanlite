"""PDF and image I/O: load pages from PDF/images, export to searchable PDF."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import cv2
import fitz  # PyMuPDF
import numpy as np
from numpy.typing import NDArray
from PIL import Image


def load_file(path: str | Path) -> list[NDArray]:
    """Load a PDF or image file and return a list of BGR numpy arrays (one per page)."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"):
        img = cv2.imread(str(path))
        if img is None:
            raise ValueError(f"Could not read image: {path}")
        return [img]
    raise ValueError(f"Unsupported file type: {suffix}")


def _load_pdf(path: Path, dpi: int = 200) -> list[NDArray]:
    """Render each PDF page to a BGR numpy array at the given DPI."""
    doc = fitz.open(str(path))
    pages = []
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        if pix.n == 4:  # RGBA
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:  # RGB
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        elif pix.n == 1:  # Grayscale
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        pages.append(img)
    doc.close()
    return pages


def _downscale(img: NDArray, target_dpi: int, source_dpi: int = 200) -> NDArray:
    """Downscale an image to a target DPI, assuming source_dpi as the original resolution."""
    if target_dpi >= source_dpi:
        return img
    scale = target_dpi / source_dpi
    h, w = img.shape[:2]
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def export_pdf(
    pages: list[NDArray],
    output_path: str | Path,
    ocr: bool = False,
    dpi: int = 200,
    jpeg_quality: int = 85,
) -> None:
    """Combine page images into a single PDF.

    Args:
        dpi: Output resolution. Images are downscaled if this is lower than
             their native resolution (assumed 200 DPI from PDF import).
             Lower values produce smaller files.
        jpeg_quality: JPEG compression quality (1-100). Lower = smaller file.
        ocr: If True, runs Tesseract to produce a searchable text layer.
    """
    if ocr:
        _export_ocr_pdf(pages, output_path, dpi, jpeg_quality)
    else:
        _export_image_pdf(pages, output_path, dpi, jpeg_quality)


def _export_image_pdf(
    pages: list[NDArray], output_path: str | Path, dpi: int, jpeg_quality: int
) -> None:
    """Create a PDF from images using PyMuPDF (no OCR)."""
    doc = fitz.open()
    for img_bgr in pages:
        scaled = _downscale(img_bgr, dpi)
        img_rgb = cv2.cvtColor(scaled, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)

        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=jpeg_quality)
        buf.seek(0)

        h, w = scaled.shape[:2]
        page_w = w * 72.0 / dpi
        page_h = h * 72.0 / dpi
        page = doc.new_page(width=page_w, height=page_h)
        page.insert_image(fitz.Rect(0, 0, page_w, page_h), stream=buf.read())

    doc.save(str(output_path))
    doc.close()


def _export_ocr_pdf(
    pages: list[NDArray], output_path: str | Path, dpi: int, jpeg_quality: int
) -> None:
    """Create a searchable PDF using Tesseract's PDF output, then merge pages."""
    try:
        import pytesseract
    except ImportError as e:
        raise ImportError("pytesseract is required for OCR. Install it and Tesseract.") from e

    merged = fitz.open()

    for img_bgr in pages:
        scaled = _downscale(img_bgr, dpi)
        img_rgb = cv2.cvtColor(scaled, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)

        pdf_bytes = pytesseract.image_to_pdf_or_hocr(pil_img, extension="pdf")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        page_doc = fitz.open(tmp_path)
        merged.insert_pdf(page_doc)
        page_doc.close()
        Path(tmp_path).unlink(missing_ok=True)

    merged.save(str(output_path))
    merged.close()
