#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Generate small, structurally-diverse producer fixtures committed for CI (#130).

Rule 5 says producer diversity is where PDF tooling breaks, but the named non-destructive/survival
tests only had the private OMs/ corpus (gitignored) - so in CI they skipped, leaving the gate with
no producer diversity. These committed fixtures stand in for the corpus classes when absent:

  producer-native.pdf   text, compressed object streams + linearized (modern web-optimized producer)
  producer-hybrid.pdf   text + an embedded raster image, classic xref (mixed content)
  producer-scanned.pdf  image-only page, NO text layer (a scanned OM)

Deterministic (fixed dates / deterministic ids) so re-running is a no-op. Run with the repo venv:
    .venv/Scripts/python.exe core/tests/fixtures/gen_producer_fixtures.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pikepdf
import pymupdf

OUT = Path(__file__).resolve().parent / "producers"
_TEXT = (
    "OFFERING MEMORANDUM\n\nSingle-Tenant Net-Lease Investment\n"
    "1000 Example Rd, Sampleville\n\nAsking Price: $1,850,000    Cap Rate: 6.25%\n"
    "NOI: $115,625    Tenant: Example Retail Stores, LLC\n"
)


def _text_doc() -> pymupdf.Document:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 720), _TEXT, fontsize=12)
    doc.set_toc([[1, "Cover", 1]])
    return doc


def _native() -> bytes:
    """Text PDF re-saved with object streams + linearization (a modern producer's structure)."""
    doc = _text_doc()
    raw = doc.tobytes()
    doc.close()
    with pikepdf.open(io.BytesIO(raw)) as pdf:
        buf = io.BytesIO()
        pdf.save(buf, object_stream_mode=pikepdf.ObjectStreamMode.generate, linearize=True)
        return buf.getvalue()


def _hybrid() -> bytes:
    """Text + an embedded raster image (mixed content, classic xref)."""
    doc = _text_doc()
    page = doc[0]
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 96, 96))
    pix.set_rect(pix.irect, (200, 120, 60))  # a solid color block as the image
    page.insert_image(pymupdf.Rect(400, 80, 540, 220), pixmap=pix)
    data = doc.tobytes()
    doc.close()
    return data


def _scanned() -> bytes:
    """Image-only page: render the text to a raster, insert as a full-page image (no text layer)."""
    src = _text_doc()
    pix = src[0].get_pixmap(dpi=150)
    src.close()
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, pixmap=pix)  # image only -> no extractable text
    data = doc.tobytes()
    doc.close()
    return data


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "producer-native.pdf").write_bytes(_native())
    (OUT / "producer-hybrid.pdf").write_bytes(_hybrid())
    (OUT / "producer-scanned.pdf").write_bytes(_scanned())
    print(f"wrote producer-native/hybrid/scanned.pdf -> {OUT}")


if __name__ == "__main__":
    main()
