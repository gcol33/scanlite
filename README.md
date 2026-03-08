# Scanlite

Cross-platform document scanner. Import PDFs and images, crop, perspective-correct, enhance to a clean scan look, reorder pages, and export as a searchable PDF with OCR.

## Install

```bash
pip install scanlite
```

Or download native installers from [Releases](https://github.com/gcol33/scanlite/releases):
**.msi** (Windows) · **.dmg** (macOS Apple Silicon) · **.deb** / **.rpm** (Linux)

## Usage

```bash
scanlite
```

## Features

- **Import** PDF, PNG, JPG, TIFF, BMP, WebP
- **Reorder** pages via Move Up / Move Down
- **Auto-crop** to document edges
- **Auto-perspective** correction (detects skewed quadrilaterals)
- **Scan enhance** with three modes: auto, black & white, high-contrast grayscale
- **Export PDF** with optional OCR text layer (requires [Tesseract](https://github.com/tesseract-ocr/tesseract))
- Per-page or batch processing
- Modern dark UI (Sun Valley theme)

## System requirements

- Python 3.10+
- Tesseract OCR (optional, for searchable PDF export)

## License

[MIT](LICENSE.md)
