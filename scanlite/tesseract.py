"""Locate Tesseract binary: bundled first, then system PATH."""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path


def _frozen_dir() -> Path | None:
    """Return the PyInstaller bundle directory, or None if running from source."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return None


def find_tesseract() -> str | None:
    """Find the Tesseract binary path.

    Checks in order:
    1. Bundled binary inside a PyInstaller build
    2. System PATH
    """
    system = platform.system()
    exe = "tesseract.exe" if system == "Windows" else "tesseract"

    # Check bundled location
    bundle = _frozen_dir()
    if bundle:
        bundled = bundle / "tesseract" / exe
        if bundled.exists():
            # Also set TESSDATA_PREFIX so Tesseract finds its language data
            tessdata = bundle / "tesseract" / "tessdata"
            if tessdata.is_dir():
                os.environ["TESSDATA_PREFIX"] = str(tessdata.parent)
            return str(bundled)

    # Fall back to system PATH
    return shutil.which("tesseract")


def configure() -> bool:
    """Configure pytesseract to use the best available Tesseract binary.

    Returns True if Tesseract was found, False otherwise.
    """
    path = find_tesseract()
    if path is None:
        return False

    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = path
    except ImportError:
        pass
    return True
