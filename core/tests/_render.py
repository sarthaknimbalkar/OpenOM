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
