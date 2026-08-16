"""Classify a PDF (native / hybrid / scanned) and summarize it (spec §I om_inspect, §X.3).

Deterministic, inference-free. Uses PyMuPDF for text/image inspection and the core reader for
payload presence + integrity state.
"""

from __future__ import annotations

from typing import Literal, TypedDict

import pymupdf

from .embed import read

DocClass = Literal["native", "hybrid", "scanned"]

TEXT_MIN_CHARS = 100  # a page with at least this much extractable text has a real text layer
FULLPAGE_AREA_FRAC = 0.80  # image covering >= this fraction of the page is "full-page"
SAMPLE_PAGES = 12  # cap pages sampled for text/image classification (speed)

# Tuned against the M1 fixture matrix (see test_inspect); classification thresholds §X.3.
SCANNED_TEXT_COVERAGE = 0.20
NATIVE_TEXT_COVERAGE = 0.85
HYBRID_IMAGES_PER_PAGE = 3.0


class PayloadInfo(TypedDict):
    present: bool
    specVersion: str | None
    hashValid: bool | None


class ImageInfo(TypedDict):
    count: int
    hasSMask: bool
    colorspaces: list[str]


Profile = TypedDict(
    "Profile",
    {
        "class": DocClass,
        "pages": int,
        "payload": PayloadInfo,
        "images": ImageInfo,
        "textCoverage": float,
    },
)


def classify(text_coverage: float, fullpage_img_frac: float, images_per_page: float) -> DocClass:
    if text_coverage < SCANNED_TEXT_COVERAGE:
        return "scanned"
    if (
        text_coverage >= NATIVE_TEXT_COVERAGE
        and fullpage_img_frac < 0.5
        and images_per_page < HYBRID_IMAGES_PER_PAGE
    ):
        return "native"
    return "hybrid"


def inspect(pdf_bytes: bytes) -> Profile:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages = doc.page_count
        sample = min(pages, SAMPLE_PAGES) or 1
        text_pages = 0
        fullpage_pages = 0
        for i in range(min(pages, SAMPLE_PAGES)):
            page = doc.load_page(i)
            if len(page.get_text("text").strip()) >= TEXT_MIN_CHARS:
                text_pages += 1
            area = page.rect.width * page.rect.height
            if area and any(
                (pymupdf.Rect(im["bbox"]).width * pymupdf.Rect(im["bbox"]).height) / area
                > FULLPAGE_AREA_FRAC
                for im in page.get_image_info(xrefs=True)
            ):
                fullpage_pages += 1

        seen: set[int] = set()
        has_smask = False
        colorspaces: set[str] = set()
        for i in range(pages):
            for img in doc.load_page(i).get_images(full=True):
                xref = img[0]
                if xref in seen:
                    continue
                seen.add(xref)
                if img[1]:
                    has_smask = True
                colorspaces.add(img[5] or "unknown")

        text_coverage = text_pages / sample
        fullpage_frac = fullpage_pages / sample
        images_per_page = len(seen) / pages if pages else 0.0
        doc_class = classify(text_coverage, fullpage_frac, images_per_page)
    finally:
        doc.close()

    result = read(pdf_bytes)
    payload: PayloadInfo = {
        "present": result.present,
        "specVersion": (result.payload or {}).get("specVersion") if result.payload else None,
        "hashValid": result.hash_valid,
    }
    return {
        "class": doc_class,
        "pages": pages,
        "payload": payload,
        "images": {"count": len(seen), "hasSMask": has_smask, "colorspaces": sorted(colorspaces)},
        "textCoverage": round(text_coverage, 4),
    }
