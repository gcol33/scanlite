# Scanlite

[![Release](https://github.com/gcol33/scanlite/actions/workflows/release.yml/badge.svg)](https://github.com/gcol33/scanlite/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Turn photos of documents into clean, searchable PDFs.**

Load scanned pages or photos from your phone, let Scanlite straighten, crop, and clean them automatically, reorder as needed, and export a single PDF with an optional OCR text layer.

## Quick Start

```bash
pip install scanlite
scanlite
```

## Features

### Import

- PDF (rendered at 200 DPI), PNG, JPG, TIFF, BMP, WebP
- Multi-page PDFs split into individual pages automatically
- Drag-and-drop support (when tkdnd is available)

### Processing

- **Auto-crop**: Otsu threshold + contour detection trims to the document edge
- **Auto-perspective**: Canny edge detection finds a 4-point quadrilateral and warps it flat
- **Scan enhance**: three modes that produce a clean, scanner-like look:

  | Mode | What it does |
  |------|-------------|
  | `auto` | Detects page brightness; picks B&W for white pages, CLAHE for darker ones |
  | `bw` | Adaptive Gaussian threshold for pure black-on-white text |
  | `gray` | CLAHE contrast enhancement for photos or diagrams |

- Every operation works per-page or as a batch across all pages
- Reset any page to its original at any time

### Reorder and Manage

- Move Up / Move Down (or arrow keys) to reorder
- Delete to remove a page
- Thumbnail panel shows the current page order at a glance

### Export

- **PDF**: combines all pages into a single document
- **PDF + OCR**: Tesseract generates an invisible text layer per page, making the output searchable and copy-pasteable
- Keyboard shortcuts: `Ctrl+S` export, `Ctrl+Shift+S` export with OCR

## Installation

### pip (all platforms)

```bash
pip install scanlite
scanlite          # launch the GUI
```

### Native installers

Download from [Releases](https://github.com/gcol33/scanlite/releases):

| Platform | Download | Install |
|----------|----------|---------|
| Windows x64 | [Scanlite-0.1.0.msi](https://github.com/gcol33/scanlite/releases/download/v0.1.0/Scanlite-0.1.0.msi) | Double-click; installs to Program Files with Start Menu shortcut |
| macOS Apple Silicon | [Scanlite-0.1.0.dmg](https://github.com/gcol33/scanlite/releases/download/v0.1.0/Scanlite-0.1.0.dmg) | Open, drag to Applications |
| Debian / Ubuntu | [scanlite-0.1.0.deb](https://github.com/gcol33/scanlite/releases/download/v0.1.0/scanlite-0.1.0.deb) | `sudo dpkg -i scanlite-0.1.0.deb` |
| Fedora / RHEL | [scanlite-0.1.0.rpm](https://github.com/gcol33/scanlite/releases/download/v0.1.0/scanlite-0.1.0.rpm) | `sudo rpm -i scanlite-0.1.0.rpm` |

### OCR dependency

OCR export requires [Tesseract](https://github.com/tesseract-ocr/tesseract) installed separately:

```bash
# Windows (winget)
winget install UB-Mannheim.TesseractOCR

# macOS
brew install tesseract

# Debian/Ubuntu
sudo apt install tesseract-ocr

# Fedora
sudo dnf install tesseract
```

The app works fine without Tesseract; you just cannot use the "Export PDF + OCR" button.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+O` | Import files |
| `Up` / `Down` | Navigate pages |
| `Delete` | Remove selected page |
| `Ctrl+S` | Export PDF |
| `Ctrl+Shift+S` | Export PDF + OCR |

## How It Works

Scanlite's processing pipeline runs perspective correction first (to avoid cropping a skewed quad), then crop, then enhancement. Each step is independent and can be applied or skipped per page.

The perspective detector looks for the largest 4-sided contour in the edge map and computes a homography to warp it into a rectangle. If no quadrilateral is found, the image passes through unchanged.

The scan enhancer auto-detects whether a page is mostly white (median brightness > 170) and picks adaptive thresholding for text-heavy pages or CLAHE for photos and diagrams.

## System Requirements

- Python 3.10+
- Tesseract OCR (optional, for searchable PDF export)

## Support

> "Software is like sex: it's better when it's free." -- Linus Torvalds

If this tool saved you a trip to the copy shop, buying me a coffee is a nice way to say thanks.

[![Buy Me A Coffee](https://img.shields.io/badge/-Buy%20me%20a%20coffee-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/gcol33)

## License

MIT (see [LICENSE.md](LICENSE.md))

## Citation

```bibtex
@software{scanlite,
  author = {Colling, Gilles},
  title = {Scanlite: Cross-Platform Document Scanner},
  year = {2026},
  url = {https://github.com/gcol33/scanlite}
}
```
