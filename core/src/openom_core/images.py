# SPDX-License-Identifier: MIT
"""Extract raster images from a PDF (spec §8b): locate + decompress, recombine SMask to RGBA,
convert CMYK/ICC/Indexed to sRGB, dedupe by xref. Deterministic, inference-free. Unsupported
images are reported in the manifest and skipped - never a crash.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import NotRequired, TypedDict

import pymupdf

#: Reject a single image larger than this many pixels *before* materializing it - a small
#: compressed image stream can declare enormous dimensions (a decompression bomb). ~100 MP.
MAX_IMAGE_PIXELS = 100_000_000

#: Zoom used to rasterize a vector-only page (#16). 2.0 = 144 DPI - legible without being huge; the
#: pixel-count guard drops it to 72 DPI if a large page would exceed MAX_IMAGE_PIXELS.
_RENDER_ZOOM = 2.0


class ImageDescriptor(TypedDict):
    xref: int
    width: int
    height: int
    colorspace: str
    hasSMask: bool
    contentHash: str | None
    mime: str
    path: str | None
    error: str | None
    #: Set only on synthetic entries (#16): "rendered-page" for a rasterized vector-only page.
    source: NotRequired[str]
    #: 1-based page number, present only when ``source == "rendered-page"``.
    page: NotRequired[int]


class ImageManifest(TypedDict):
    images: list[ImageDescriptor]
    deduped: int


_RGB_LIKE = {"DeviceRGB", "DeviceGray"}


def _error_descriptor(
    xref: int, base_cs: str, smask_xref: int, message: str, *, width: int = 0, height: int = 0
) -> ImageDescriptor:
    return {
        "xref": xref,
        "width": width,
        "height": height,
        "colorspace": base_cs,
        "hasSMask": bool(smask_xref),
        "contentHash": None,
        "mime": "",
        "path": None,
        "error": message,
    }


def _render_page(
    doc: pymupdf.Document, pno: int, out_dir: Path | None
) -> ImageDescriptor:
    """Rasterize a vector-only page to sRGB (#16) at a bounded DPI. Reported+skipped on failure."""
    page = doc.load_page(pno)
    zoom = _RENDER_ZOOM
    rect = page.rect
    if (rect.width * zoom) * (rect.height * zoom) > MAX_IMAGE_PIXELS:
        zoom = 1.0  # a very large page: fall back to 72 DPI rather than allocate a bomb
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csRGB, alpha=False)
    content_hash = "sha256:" + hashlib.sha256(pix.samples).hexdigest()
    path: str | None = None
    if out_dir is not None:
        dest = out_dir / f"page_{pno + 1}.png"
        pix.save(dest)
        path = str(dest)
    return {
        "xref": 0,  # synthetic: a rendered page has no image xref
        "width": pix.width,
        "height": pix.height,
        "colorspace": "DeviceRGB",
        "hasSMask": False,
        "contentHash": content_hash,
        "mime": "image/png",
        "path": path,
        "error": None,
        "source": "rendered-page",
        "page": pno + 1,
    }


def extract_images(
    pdf_bytes: bytes, *, out_dir: Path | None = None, render_vector_pages: bool = False
) -> ImageManifest:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    seen_xref: set[int] = set()
    seen_content: set[str] = set()
    deduped = 0
    images: list[ImageDescriptor] = []
    pages_with_raster: set[int] = set()
    try:
        for pno in range(doc.page_count):
            for img in doc.load_page(pno).get_images(full=True):
                pages_with_raster.add(pno)
                xref = int(img[0])
                if xref in seen_xref:
                    deduped += 1
                    continue
                seen_xref.add(xref)
                smask_xref = int(img[1])
                decl_w, decl_h = int(img[2]), int(img[3])
                base_cs = str(img[5]) or "unknown"
                # Bomb guard: reject on declared dimensions before allocating the raster.
                if decl_w * decl_h > MAX_IMAGE_PIXELS:
                    images.append(
                        _error_descriptor(
                            xref, base_cs, smask_xref,
                            f"image too large: {decl_w}x{decl_h} px exceeds {MAX_IMAGE_PIXELS}",
                            width=decl_w, height=decl_h,
                        )
                    )
                    continue
                try:
                    pix = pymupdf.Pixmap(doc, xref)
                    # CMYK / ICC / Indexed / other -> sRGB
                    if pix.colorspace is None or pix.colorspace.name not in _RGB_LIKE:
                        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                    if smask_xref:
                        pix = pymupdf.Pixmap(pix, pymupdf.Pixmap(doc, smask_xref))  # add alpha
                    content_hash = "sha256:" + hashlib.sha256(pix.samples).hexdigest()
                    if content_hash in seen_content:
                        deduped += 1  # identical pixels under a different xref
                        continue
                    seen_content.add(content_hash)
                    path: str | None = None
                    if out_dir is not None:
                        dest = out_dir / f"img_{xref}.png"
                        pix.save(dest)
                        path = str(dest)
                    images.append(
                        {
                            "xref": xref,
                            "width": pix.width,
                            "height": pix.height,
                            "colorspace": base_cs,
                            "hasSMask": bool(smask_xref),
                            "contentHash": content_hash,
                            "mime": "image/png",
                            "path": path,
                            "error": None,
                        }
                    )
                except Exception as exc:  # noqa: BLE001 - report + skip, never crash (§8b)
                    images.append(_error_descriptor(xref, base_cs, smask_xref, str(exc)))
        # #16: a page with no raster images (a vector-only page - charts, maps, drawn site plans)
        # yields nothing above. When asked, rasterize it so downstream has the page's visuals.
        if render_vector_pages:
            for pno in range(doc.page_count):
                if pno in pages_with_raster:
                    continue
                try:
                    images.append(_render_page(doc, pno, out_dir))
                except Exception as exc:  # noqa: BLE001 - report + skip, never crash (§8b)
                    images.append(
                        _error_descriptor(0, "DeviceRGB", 0, f"page {pno + 1} render failed: {exc}")
                    )
    finally:
        doc.close()
    return {"images": images, "deduped": deduped}
