"""Test helpers: render PDF pages to grayscale arrays and compute global SSIM.

Used to prove embedding is visually non-destructive (§4 / §8a): the rendered pages before and
after an embed must be indistinguishable (SSIM ~= 1.0).
"""

from __future__ import annotations

import numpy as np
import pymupdf


def render_pages(pdf_bytes: bytes, dpi: int = 72) -> list[np.ndarray]:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages: list[np.ndarray] = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
            pages.append(arr.copy())
        return pages
    finally:
        doc.close()


def ssim(a: np.ndarray, b: np.ndarray) -> float:
    """Global (single-window) SSIM over two grayscale images; 1.0 == identical."""
    if a.shape != b.shape:
        return 0.0
    x = a.astype(np.float64)
    y = b.astype(np.float64)
    mu_x, mu_y = x.mean(), y.mean()
    var_x, var_y = x.var(), y.var()
    cov = ((x - mu_x) * (y - mu_y)).mean()
    L = 255.0
    c1, c2 = (0.01 * L) ** 2, (0.03 * L) ** 2
    num = (2 * mu_x * mu_y + c1) * (2 * cov + c2)
    den = (mu_x**2 + mu_y**2 + c1) * (var_x + var_y + c2)
    return float(num / den)


def tiled_ssim_min(a: np.ndarray, b: np.ndarray, tile: int = 64) -> float:
    """Worst-case SSIM over a grid of tiles - a localized change (a stamp in one corner) tanks
    one tile even when the global SSIM stays ~1.0, so this is the honest visual-diff metric."""
    if a.shape != b.shape:
        return 0.0
    worst = 1.0
    for r in range(0, a.shape[0], tile):
        for c in range(0, a.shape[1], tile):
            wa = a[r : r + tile, c : c + tile]
            wb = b[r : r + tile, c : c + tile]
            worst = min(worst, ssim(wa, wb))
    return worst


def pages_pixel_identical(before: bytes, after: bytes, dpi: int = 150) -> bool:
    """Strongest visual proof: every page renders to byte-identical pixels (any change fails)."""
    pa = render_pages(before, dpi=dpi)
    pb = render_pages(after, dpi=dpi)
    if len(pa) != len(pb):
        return False
    return all(np.array_equal(x, y) for x, y in zip(pa, pb, strict=True))
