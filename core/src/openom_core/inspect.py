# SPDX-License-Identifier: MIT
"""Classify a PDF (native / hybrid / scanned) and summarize it (spec §I om_inspect, §X.3).

Deterministic, inference-free. Uses PyMuPDF for text/image inspection and the core reader for
payload presence + integrity state.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from .embed import read
from .errors import EncryptedPdfError

try:
    import pymupdf
except ImportError:  # PyMuPDF (AGPL) is an optional [render] extra
    pymupdf = None

_RENDER_HINT = "inspect requires PyMuPDF: pip install 'openom-core[render]'"

DocClass = Literal["native", "hybrid", "scanned"]

TEXT_MIN_CHARS = 100  # a page with at least this much extractable text has a real text layer
FULLPAGE_AREA_FRAC = 0.80  # image covering >= this fraction of the page is "full-page"
SAMPLE_PAGES = 12  # cap pages sampled for text/image classification (speed)

# Tuned against the M1 fixture matrix (see test_inspect); classification thresholds §X.3.
SCANNED_TEXT_COVERAGE = 0.20
NATIVE_TEXT_COVERAGE = 0.85
HYBRID_IMAGES_PER_PAGE = 3.0

# #6: an OCR'd scan is a full-page raster with an INVISIBLE text layer over it (render mode 3/7).
# When a majority of pages look like that, the document is a scan (the text is an OCR overlay, not
# authored content) - regardless of how much text is extractable.
OCR_OVERLAY_FRAC = 0.6
_INVISIBLE_RENDER_MODES = {3, 7}  # PyMuPDF texttrace `type`: no fill/stroke ⇒ invisible


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
        "classConfidence": float,
        "pages": int,
        "payload": PayloadInfo,
        "images": ImageInfo,
        "textCoverage": float,
        "ocrOverlay": float,
    },
)

_FULLPAGE_FRAC_LIMIT = 0.5  # a native doc has few full-page images


def classify(
    text_coverage: float,
    fullpage_img_frac: float,
    images_per_page: float,
    ocr_overlay_frac: float = 0.0,
) -> DocClass:
    # An OCR'd scan (#6): most pages are a full-page image with an invisible text layer over it. The
    # page IS a scan; the text is a searchable OCR overlay, so a high extractable-text coverage must
    # not read as native/hybrid. Checked first, before the text-coverage branches.
    if ocr_overlay_frac >= OCR_OVERLAY_FRAC:
        return "scanned"
    if text_coverage < SCANNED_TEXT_COVERAGE:
        return "scanned"
    if (
        text_coverage >= NATIVE_TEXT_COVERAGE
        and fullpage_img_frac < _FULLPAGE_FRAC_LIMIT
        and images_per_page < HYBRID_IMAGES_PER_PAGE
    ):
        return "native"
    return "hybrid"


def classification_confidence(
    cls: DocClass,
    text_coverage: float,
    fullpage_img_frac: float,
    images_per_page: float,
    ocr_overlay_frac: float = 0.0,
) -> float:
    """Normalized [0,1] margin from the decision surface - near a threshold ⇒ low confidence."""

    def clamp(x: float) -> float:
        return max(0.0, min(1.0, x))

    tc, fp, ipp = text_coverage, fullpage_img_frac, images_per_page
    if cls == "scanned":
        # Scanned via OCR overlay (#6) is measured on the overlay margin, not text coverage (which
        # is high for an OCR scan); take whichever signal is the stronger evidence of "scanned".
        by_text = (SCANNED_TEXT_COVERAGE - tc) / SCANNED_TEXT_COVERAGE
        by_ocr = (ocr_overlay_frac - OCR_OVERLAY_FRAC) / (1.0 - OCR_OVERLAY_FRAC)
        return clamp(max(by_text, by_ocr))
    if cls == "native":
        return clamp(
            min(
                (tc - NATIVE_TEXT_COVERAGE) / (1.0 - NATIVE_TEXT_COVERAGE),
                (_FULLPAGE_FRAC_LIMIT - fp) / _FULLPAGE_FRAC_LIMIT,
                (HYBRID_IMAGES_PER_PAGE - ipp) / HYBRID_IMAGES_PER_PAGE,
            )
        )
    # hybrid = residual: confident when clearly above scanned AND clearly not native.
    above_scanned = (tc - SCANNED_TEXT_COVERAGE) / SCANNED_TEXT_COVERAGE
    from_native = max(
        (NATIVE_TEXT_COVERAGE - tc) / NATIVE_TEXT_COVERAGE,
        (fp - _FULLPAGE_FRAC_LIMIT) / _FULLPAGE_FRAC_LIMIT,
        (ipp - HYBRID_IMAGES_PER_PAGE) / HYBRID_IMAGES_PER_PAGE,
    )
    return clamp(min(above_scanned, from_native))


def _text_is_mostly_invisible(page: pymupdf.Page) -> bool:
    """True when most of a page's glyphs are drawn with an invisible render mode (#6).

    OCR software lays a searchable text layer over the scanned page image using render mode 3/7 (no
    fill, no stroke) so it doesn't paint over the scan. Authored text is visible (mode 0). We
    compare invisible vs total glyph counts from PyMuPDF's texttrace, which exposes the mode as
    `type`.
    """
    invisible = 0
    total = 0
    for span in page.get_texttrace():
        n = len(span.get("chars", ()))
        total += n
        if span.get("type") in _INVISIBLE_RENDER_MODES:
            invisible += n
    return total > 0 and invisible / total >= 0.5


def _sample_indices(pages: int, cap: int) -> list[int]:
    """Evenly-spread page indices across the whole document (not just the first `cap`), so an
    OM whose first pages are an image-heavy cover isn't misclassified from a biased sample."""
    if pages <= cap:
        return list(range(pages))
    return sorted({round(i * (pages - 1) / (cap - 1)) for i in range(cap)})


def inspect(pdf_bytes: bytes) -> Profile:
    if pymupdf is None:
        raise ImportError(_RENDER_HINT)
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    if doc.needs_pass:  # password-protected: refuse cleanly, not a "document closed" ValueError
        doc.close()
        raise EncryptedPdfError
    try:
        pages = doc.page_count
        indices = _sample_indices(pages, SAMPLE_PAGES)
        sample = len(indices) or 1
        text_pages = 0
        fullpage_pages = 0
        ocr_scan_pages = 0
        for i in indices:
            page = doc.load_page(i)
            has_text = len(page.get_text("text").strip()) >= TEXT_MIN_CHARS
            if has_text:
                text_pages += 1
            area = page.rect.width * page.rect.height
            is_fullpage = bool(area) and any(
                (pymupdf.Rect(im["bbox"]).width * pymupdf.Rect(im["bbox"]).height) / area
                > FULLPAGE_AREA_FRAC
                for im in page.get_image_info(xrefs=True)
            )
            if is_fullpage:
                fullpage_pages += 1
            # #6: an OCR'd-scan page = a full-page image with a mostly-INVISIBLE text layer over it.
            if is_fullpage and has_text and _text_is_mostly_invisible(page):
                ocr_scan_pages += 1

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
        ocr_overlay_frac = ocr_scan_pages / sample
        images_per_page = len(seen) / pages if pages else 0.0
        doc_class = classify(text_coverage, fullpage_frac, images_per_page, ocr_overlay_frac)
        confidence = classification_confidence(
            doc_class, text_coverage, fullpage_frac, images_per_page, ocr_overlay_frac
        )
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
        "classConfidence": round(confidence, 4),
        "pages": pages,
        "payload": payload,
        "images": {"count": len(seen), "hasSMask": has_smask, "colorspaces": sorted(colorspaces)},
        "textCoverage": round(text_coverage, 4),
        "ocrOverlay": round(ocr_overlay_frac, 4),  # #6: fraction of pages that are OCR'd-scan pages
    }
