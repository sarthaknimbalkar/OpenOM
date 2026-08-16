# SPDX-License-Identifier: MIT
"""Extract raster images from a PDF (spec §8b): locate + decompress, recombine SMask to RGBA,
convert CMYK/ICC/Indexed to sRGB, dedupe by xref. Deterministic, inference-free. Unsupported
images are reported in the manifest and skipped — never a crash.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import pymupdf


class ImageDescriptor(TypedDict):
    xref: int
    width: int
    height: int
    colorspace: str
    hasSMask: bool
    mime: str
    path: str | None
    error: str | None


class ImageManifest(TypedDict):
    images: list[ImageDescriptor]
    deduped: int


_RGB_LIKE = {"DeviceRGB", "DeviceGray"}


def extract_images(pdf_bytes: bytes, *, out_dir: Path | None = None) -> ImageManifest:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    seen: set[int] = set()
    deduped = 0
    images: list[ImageDescriptor] = []
    try:
        for pno in range(doc.page_count):
            for img in doc.load_page(pno).get_images(full=True):
                xref = int(img[0])
                if xref in seen:
                    deduped += 1
                    continue
                seen.add(xref)
                smask_xref = int(img[1])
                base_cs = str(img[5]) or "unknown"
                try:
                    pix = pymupdf.Pixmap(doc, xref)
                    # CMYK / ICC / Indexed / other -> sRGB
                    if pix.colorspace is None or pix.colorspace.name not in _RGB_LIKE:
                        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                    if smask_xref:
                        pix = pymupdf.Pixmap(pix, pymupdf.Pixmap(doc, smask_xref))  # add alpha
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
                            "mime": "image/png",
                            "path": path,
                            "error": None,
                        }
                    )
                except Exception as exc:  # noqa: BLE001 — report + skip, never crash (§8b)
                    images.append(
                        {
                            "xref": xref,
                            "width": 0,
                            "height": 0,
                            "colorspace": base_cs,
                            "hasSMask": bool(smask_xref),
                            "mime": "",
                            "path": None,
                            "error": str(exc),
                        }
                    )
    finally:
        doc.close()
    return {"images": images, "deduped": deduped}
