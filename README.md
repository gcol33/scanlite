# Scanlite

[![Release](https://github.com/gcol33/scanlite/actions/workflows/release.yml/badge.svg)](https://github.com/gcol33/scanlite/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Turn photos of documents into clean, searchable PDFs.**

Load scanned pages or photos from your phone, let Scanlite straighten, crop, and clean them automatically, reorder as needed, and export a single PDF with an optional OCR text layer.

## Getting Started

```bash
pip install scanlite
scanlite
```

Or download a native installer from [Releases](https://github.com/gcol33/scanlite/releases):

| Platform | Download | Install |
|----------|----------|---------|
| Windows x64 | [Scanlite-0.1.1.msi](https://github.com/gcol33/scanlite/releases/download/v0.1.1/Scanlite-0.1.1.msi) | Double-click; installs to Program Files with Start Menu shortcut |
| macOS Apple Silicon | [Scanlite-0.1.1.dmg](https://github.com/gcol33/scanlite/releases/download/v0.1.1/Scanlite-0.1.1.dmg) | Open, drag to Applications |
| Debian / Ubuntu | [scanlite-0.1.1.deb](https://github.com/gcol33/scanlite/releases/download/v0.1.1/scanlite-0.1.1.deb) | `sudo dpkg -i scanlite-0.1.1.deb` |
| Fedora / RHEL | [scanlite-0.1.1.rpm](https://github.com/gcol33/scanlite/releases/download/v0.1.1/scanlite-0.1.1.rpm) | `sudo rpm -i scanlite-0.1.1.rpm` |

Native installers bundle [Tesseract](https://github.com/tesseract-ocr/tesseract) for OCR out of the box. When installing via pip, Tesseract must be available on your system PATH for the OCR export to work.

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
  | `bw` | iPhone-style scan: estimates local background, normalizes illumination, pushes text to black and page to white |
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

The scan enhancer auto-detects whether a page is mostly white and picks the appropriate mode. In B&W mode, it estimates the local background color using morphological closing, divides by it to normalize uneven lighting, then applies a sigmoid contrast stretch to push text toward black and the page surface toward pure white. The result looks like a clean flatbed scan even from a phone photo taken under uneven light.

## System Requirements

- Python 3.10+
- Tesseract OCR (bundled in native installers; for pip installs, [install separately](https://tesseract-ocr.github.io/tessdoc/Installation.html))

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
