# SPDX-License-Identifier: MIT
"""Extract raster images from a PDF (spec §8b): locate + decompress, recombine SMask to RGBA,
convert CMYK/ICC/Indexed to sRGB, dedupe by xref. Deterministic, inference-free. Unsupported
images are reported in the manifest and skipped — never a crash.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TypedDict

import pymupdf

#: Reject a single image larger than this many pixels *before* materializing it — a small
#: compressed image stream can declare enormous dimensions (a decompression bomb). ~100 MP.
MAX_IMAGE_PIXELS = 100_000_000


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


def extract_images(pdf_bytes: bytes, *, out_dir: Path | None = None) -> ImageManifest:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    seen_xref: set[int] = set()
    seen_content: set[str] = set()
    deduped = 0
    images: list[ImageDescriptor] = []
    try:
        for pno in range(doc.page_count):
            for img in doc.load_page(pno).get_images(full=True):
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
                except Exception as exc:  # noqa: BLE001 — report + skip, never crash (§8b)
                    images.append(_error_descriptor(xref, base_cs, smask_xref, str(exc)))
    finally:
        doc.close()
    return {"images": images, "deduped": deduped}
