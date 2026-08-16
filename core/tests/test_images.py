"""Task 9: image extraction — SMask/CMYK/dedupe/bomb-guard (spec §8b)."""

from __future__ import annotations

import io
from pathlib import Path

import pikepdf
import pymupdf
import pytest
from PIL import Image

from _make_scan import make_scanned, make_text_pdf
from openom_core.images import extract_images


def _one_image_pdf() -> bytes:
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=200, height=200)
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40))
        pix.set_rect(pix.irect, (10, 20, 30))
        page.insert_image(pymupdf.Rect(10, 10, 90, 90), pixmap=pix)
        return doc.tobytes()
    finally:
        doc.close()


def _alpha_image_pdf() -> bytes:
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=200, height=200)
        apix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 32, 32), True)
        apix.set_rect(apix.irect, (255, 0, 0, 128))  # RGBA -> stored with a soft mask
        page.insert_image(pymupdf.Rect(10, 10, 90, 90), pixmap=apix)
        return doc.tobytes()
    finally:
        doc.close()


def test_no_images() -> None:
    manifest = extract_images(make_text_pdf())
    assert manifest["images"] == []
    assert manifest["deduped"] == 0


def test_pixel_cap_rejects_oversized(monkeypatch: pytest.MonkeyPatch) -> None:
    """A single over-cap image is reported + skipped before materialization, never a crash."""
    monkeypatch.setattr("openom_core.images.MAX_IMAGE_PIXELS", 100)  # tiny cap
    manifest = extract_images(make_scanned(make_text_pdf()))  # a full-page raster >> 100 px
    assert any(d["error"] and "too large" in d["error"] for d in manifest["images"])
    assert all(d["contentHash"] is None for d in manifest["images"] if d["error"])


def test_content_hash_dedupe_across_xrefs() -> None:
    """Identical pixels under DIFFERENT xrefs (merged docs) dedupe by content, not just xref."""
    with pikepdf.open(io.BytesIO(_one_image_pdf())) as pa, pikepdf.open(
        io.BytesIO(_one_image_pdf())
    ) as pb:
        pa.pages.extend(pb.pages)  # foreign-copies the image to a new xref
        buf = io.BytesIO()
        pa.save(buf)
        merged = buf.getvalue()
    manifest = extract_images(merged)
    non_error = [d for d in manifest["images"] if d["error"] is None]
    assert len(non_error) == 1  # one unique image survives
    assert manifest["deduped"] >= 1
    assert non_error[0]["contentHash"] is not None


def test_xref_dedupe_same_image_two_pages() -> None:
    """The same image XObject shown on two pages dedupes by xref."""
    doc = pymupdf.open()
    try:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40))
        pix.set_rect(pix.irect, (10, 20, 30))
        for _ in range(2):
            page = doc.new_page(width=200, height=200)
            page.insert_image(pymupdf.Rect(10, 10, 90, 90), pixmap=pix)
        pdf_bytes = doc.tobytes()
    finally:
        doc.close()
    manifest = extract_images(pdf_bytes)
    assert manifest["deduped"] >= 1
    assert len([d for d in manifest["images"] if d["error"] is None]) == 1


def test_smask_image_extracted_as_rgba(tmp_path: Path) -> None:
    manifest = extract_images(_alpha_image_pdf(), out_dir=tmp_path)
    ok = [d for d in manifest["images"] if d["error"] is None]
    assert any(d["hasSMask"] for d in ok)
    for d in ok:
        if d["hasSMask"]:
            assert d["path"] is not None
            with Image.open(d["path"]) as im:
                assert im.mode in {"RGBA", "LA"}


def test_extract_synthetic_image(tmp_path: Path) -> None:
    """A rasterized page yields an extractable sRGB image — no corpus needed (runs in CI)."""
    manifest = extract_images(make_scanned(make_text_pdf()), out_dir=tmp_path)
    ok = [d for d in manifest["images"] if d["error"] is None]
    assert ok, "expected at least one extractable image"
    for d in ok:
        assert d["path"] is not None
        assert d["width"] > 0 and d["height"] > 0
        with Image.open(d["path"]) as im:
            assert im.mode in {"RGB", "RGBA", "L", "LA"}


def test_cmyk_and_smask_converted(hybrid_om: bytes, tmp_path: Path) -> None:
    manifest = extract_images(hybrid_om, out_dir=tmp_path)
    ok = [d for d in manifest["images"] if d["error"] is None]
    assert ok, "expected at least one extractable image"
    # the CMYK doc surfaces at least one CMYK-origin image and at least one SMask image
    assert any("CMYK" in d["colorspace"] for d in manifest["images"])
    assert any(d["hasSMask"] for d in manifest["images"])
    assert isinstance(manifest["deduped"], int)
    # every emitted PNG is sRGB/grayscale (never CMYK) and RGBA when it had a soft mask
    for d in ok:
        assert d["path"] is not None
        with Image.open(d["path"]) as im:
            assert im.mode in {"RGB", "RGBA", "L", "LA"}
            if d["hasSMask"]:
                assert im.mode in {"RGBA", "LA"}
