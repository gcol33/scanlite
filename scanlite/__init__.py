"""Scanlite: cross-platform document scanner with crop, perspective, enhance, and OCR."""

__version__ = "0.1.1"

from scanlite.tesseract import configure as _configure_tesseract

_configure_tesseract()
