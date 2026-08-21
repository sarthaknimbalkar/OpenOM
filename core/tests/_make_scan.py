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


def make_ocr_scanned(pdf_bytes: bytes, dpi: int = 150) -> bytes:
    """A scan WITH an OCR text layer (#6): each page is a full-page raster with an INVISIBLE
    (render mode 3) searchable text layer over it - the classic OCR'd-scan structure that must
    classify 'scanned' even though its text is extractable."""
    src = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out = pymupdf.open()
    try:
        for page in src:
            pix = page.get_pixmap(dpi=dpi)
            new_page = out.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, pixmap=pix)
            new_page.insert_text(
                (36, 60),
                "OCR searchable text layer over the scanned page image. " * 6,
                fontsize=10,
                render_mode=3,  # invisible: the OCR overlay, not authored/visible text
            )
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


def make_hybrid_pdf() -> bytes:
    """A real text layer PLUS a full-page image on each page -> classifies 'hybrid'."""
    doc = pymupdf.open()
    try:
        for _ in range(2):
            page = doc.new_page(width=612, height=792)
            page.insert_text((72, 72), "Real offering text with a full-page graphic. " * 8,
                             fontsize=11)
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 120, 150))
            pix.set_rect(pix.irect, (40, 90, 160))
            page.insert_image(page.rect, pixmap=pix)  # covers >80% of the page
        return doc.tobytes()
    finally:
        doc.close()
