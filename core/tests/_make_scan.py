"""Test helper: synthesize a scanned (image-only) PDF by rasterizing a source PDF's pages.

The corpus has no true scanned OM (Q3), so we build one to exercise scanned classification.
Each output page is a single full-page raster with no text layer.
"""

from __future__ import annotations

import pymupdf


def make_scanned(pdf_bytes: bytes, dpi: int = 150) -> bytes:
    src = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out = pymupdf.open()
    try:
        for page in src:
            pix = page.get_pixmap(dpi=dpi)
            new_page = out.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, pixmap=pix)
        return out.tobytes()
    finally:
        src.close()
        out.close()


def make_text_pdf() -> bytes:
    """A synthetic text-only PDF (real text layer, no images) -> classifies 'native'."""
    doc = pymupdf.open()
    try:
        page = doc.new_page()
        body = ("This is a single-tenant net-lease offering memorandum with a real text "
                "layer and no raster imagery. ") * 8
        page.insert_text((72, 72), body, fontsize=11)
        return doc.tobytes()
    finally:
        doc.close()
