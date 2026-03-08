"""Image processing pipeline: crop, perspective correction, scan enhancement."""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# Auto-crop
# ---------------------------------------------------------------------------

def auto_crop(img: NDArray, margin_frac: float = 0.01) -> NDArray:
    """Detect document edges and crop to bounding rectangle.

    Converts to grayscale, applies Gaussian blur + Otsu threshold,
    finds the largest contour, and crops to its bounding rect with a
    small margin.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img

    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)

    # Add margin
    mh = int(img.shape[0] * margin_frac)
    mw = int(img.shape[1] * margin_frac)
    y0 = max(0, y - mh)
    y1 = min(img.shape[0], y + h + mh)
    x0 = max(0, x - mw)
    x1 = min(img.shape[1], x + w + mw)

    return img[y0:y1, x0:x1]


# ---------------------------------------------------------------------------
# Auto-perspective correction
# ---------------------------------------------------------------------------

def _order_points(pts: NDArray) -> NDArray:
    """Order 4 points as: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    d = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(d)]
    rect[3] = pts[np.argmax(d)]
    return rect


def auto_perspective(img: NDArray) -> NDArray:
    """Detect a quadrilateral document and warp to a flat rectangle.

    Uses Canny edge detection, finds the largest 4-point contour approximation,
    and applies a perspective transform. Returns the original if no quad is found.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 200)

    # Dilate to close gaps in edges
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edged = cv2.dilate(edged, kernel, iterations=1)

    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    doc_contour = None
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            doc_contour = approx
            break

    if doc_contour is None:
        return img

    pts = _order_points(doc_contour.reshape(4, 2).astype(np.float32))

    # Compute output dimensions
    width_top = np.linalg.norm(pts[1] - pts[0])
    width_bot = np.linalg.norm(pts[2] - pts[3])
    max_w = int(max(width_top, width_bot))

    height_left = np.linalg.norm(pts[3] - pts[0])
    height_right = np.linalg.norm(pts[2] - pts[1])
    max_h = int(max(height_left, height_right))

    if max_w < 100 or max_h < 100:
        return img

    dst = np.array(
        [[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]],
        dtype=np.float32,
    )
    M = cv2.getPerspectiveTransform(pts, dst)
    return cv2.warpPerspective(img, M, (max_w, max_h))


# ---------------------------------------------------------------------------
# Scan enhancement (clean B&W / high-contrast document look)
# ---------------------------------------------------------------------------

def enhance_scan(img: NDArray, mode: str = "auto") -> NDArray:
    """Produce a clean, high-contrast scan look.

    Modes:
        "bw"   - adaptive threshold to pure black & white
        "gray" - CLAHE contrast enhancement on grayscale
        "auto" - detect whether the page is mostly white/light;
                 if so, apply adaptive B&W, otherwise CLAHE gray
    """
    valid_modes = {"auto", "bw", "gray"}
    if mode not in valid_modes:
        raise ValueError(f"mode must be one of {valid_modes}, got '{mode}'")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()

    if mode == "auto":
        # If median brightness > 170, page is mostly white -> B&W works well
        mode = "bw" if np.median(gray) > 170 else "gray"

    if mode == "bw":
        # Adaptive threshold gives clean text on white background
        result = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10
        )
        # Convert back to BGR for consistent pipeline
        return cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)

    # CLAHE for high-contrast grayscale
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


# ---------------------------------------------------------------------------
# Combined pipeline
# ---------------------------------------------------------------------------

def process_page(
    img: NDArray,
    crop: bool = True,
    perspective: bool = True,
    enhance: bool = True,
    enhance_mode: str = "auto",
) -> NDArray:
    """Run the full processing pipeline on a single page image."""
    if perspective:
        img = auto_perspective(img)
    if crop:
        img = auto_crop(img)
    if enhance:
        img = enhance_scan(img, mode=enhance_mode)
    return img
