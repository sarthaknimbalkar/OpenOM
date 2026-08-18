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


def _vector_only_pdf() -> bytes:
    """A page drawn with vector graphics (a rectangle + line) and NO raster image (#16)."""
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=200, height=200)
        page.draw_rect(pymupdf.Rect(20, 20, 180, 120), color=(0, 0, 1), fill=(0.8, 0.9, 1), width=2)
        page.draw_line(pymupdf.Point(20, 150), pymupdf.Point(180, 150), color=(1, 0, 0), width=3)
        return doc.tobytes()
    finally:
        doc.close()


def test_vector_only_page_yields_nothing_without_the_flag() -> None:
    manifest = extract_images(_vector_only_pdf())
    assert manifest["images"] == []  # no raster images, and the fallback is opt-in


def test_render_vector_pages_rasterizes_a_vector_only_page(tmp_path: Path) -> None:
    manifest = extract_images(_vector_only_pdf(), out_dir=tmp_path, render_vector_pages=True)
    rendered = [i for i in manifest["images"] if i.get("source") == "rendered-page"]
    assert len(rendered) == 1
    d = rendered[0]
    assert d["page"] == 1 and d["error"] is None and d["mime"] == "image/png"
    assert d["width"] == 400 and d["height"] == 400  # 200pt at 144 DPI (zoom 2.0)
    assert d["contentHash"] and d["contentHash"].startswith("sha256:")
    assert d["path"] is not None and Path(d["path"]).is_file()
    # The rendered pixels actually carry the drawn vector content (not a blank page).
    with Image.open(d["path"]) as im:
        assert im.getextrema() != ((255, 255), (255, 255), (255, 255))  # some non-white pixels


def test_render_vector_pages_skips_pages_that_already_have_rasters() -> None:
    # A page WITH a raster image must not also be rendered as a page (no double-count).
    manifest = extract_images(_one_image_pdf(), render_vector_pages=True)
    assert all(i.get("source") != "rendered-page" for i in manifest["images"])
    assert len(manifest["images"]) == 1


# --- #7: exotic image-codec coverage (CCITT G4 + JPEG2000) ---------------------------------------
def _ccitt_g4_pdf(w: int = 64, h: int = 48) -> bytes:
    """A PDF whose only image is a real /CCITTFaxDecode (Group-4 fax) XObject — the encoding a
    scanned/faxed B&W OM page uses. Extracts the raw G4 codestream from a libtiff group4 TIFF."""
    im = Image.new("1", (w, h), 1)
    for y in range(h):
        for x in range(w):
            if (x // 8 + y // 8) % 2 == 0:
                im.putpixel((x, y), 0)  # a checkerboard so it isn't blank
    buf = io.BytesIO()
    im.save(buf, format="TIFF", compression="group4")
    tif = Image.open(io.BytesIO(buf.getvalue()))
    off, cnt = tif.tag_v2[273][0], tif.tag_v2[279][0]  # StripOffsets / StripByteCounts
    g4 = buf.getvalue()[off : off + cnt]

    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(w, h))
    img = pikepdf.Stream(pdf, g4)
    img.Type, img.Subtype = pikepdf.Name.XObject, pikepdf.Name.Image
    img.Width, img.Height, img.BitsPerComponent = w, h, 1
    img.ColorSpace, img.Filter = pikepdf.Name.DeviceGray, pikepdf.Name.CCITTFaxDecode
    img.DecodeParms = pikepdf.Dictionary(K=-1, Columns=w, Rows=h, BlackIs1=False)
    page = pdf.pages[0]
    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=img))
    page.Contents = pikepdf.Stream(pdf, f"q {w} 0 0 {h} 0 0 cm /Im0 Do Q".encode())
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


def _jpx_pdf(w: int = 40, h: int = 30) -> bytes:
    """A PDF whose only image is a real /JPXDecode (JPEG 2000) XObject."""
    im = Image.new("RGB", (w, h))
    for y in range(h):
        for x in range(w):
            im.putpixel((x, y), (x * 6 % 256, y * 8 % 256, 120))
    buf = io.BytesIO()
    im.save(buf, format="JPEG2000")

    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(w, h))
    img = pikepdf.Stream(pdf, buf.getvalue())
    img.Type, img.Subtype = pikepdf.Name.XObject, pikepdf.Name.Image
    img.Width, img.Height, img.BitsPerComponent = w, h, 8
    img.ColorSpace, img.Filter = pikepdf.Name.DeviceRGB, pikepdf.Name.JPXDecode
    page = pdf.pages[0]
    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=img))
    page.Contents = pikepdf.Stream(pdf, f"q {w} 0 0 {h} 0 0 cm /Im0 Do Q".encode())
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


def _inline_image_pdf(w: int = 4, h: int = 4) -> bytes:
    """A page whose only image is an INLINE image (BI/ID/EI in the content stream, not XObject)."""
    px = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 0] * (w * h // 4))
    head = b"q 40 0 0 40 0 0 cm\nBI /W %d /H %d /CS /RGB /BPC 8 ID\n" % (w, h)
    content = head + px + b"\nEI\nQ"
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(40, 40))
    page = pdf.pages[0]
    page.Contents = pikepdf.Stream(pdf, content)
    page.Resources = pikepdf.Dictionary()
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


def test_extracts_ccitt_g4_image() -> None:
    manifest = extract_images(_ccitt_g4_pdf())
    imgs = [i for i in manifest["images"] if i["error"] is None]
    assert len(imgs) == 1
    assert (imgs[0]["width"], imgs[0]["height"]) == (64, 48)
    assert imgs[0]["contentHash"] is not None  # decoded to real pixels, not an error stub


def test_extracts_jpeg2000_image() -> None:
    manifest = extract_images(_jpx_pdf())
    imgs = [i for i in manifest["images"] if i["error"] is None]
    assert len(imgs) == 1
    assert (imgs[0]["width"], imgs[0]["height"]) == (40, 30)
    assert imgs[0]["contentHash"] is not None


def test_inline_image_page_captured_by_vector_render_fallback() -> None:
    """Inline images aren't XObjects, so get_images (and thus plain extraction) misses them — but a
    page carrying one has no raster XObject, so the #16 render_vector_pages fallback captures it."""
    assert extract_images(_inline_image_pdf())["images"] == []  # not seen without the fallback
    rendered = extract_images(_inline_image_pdf(), render_vector_pages=True)["images"]
    assert any(i.get("source") == "rendered-page" and i["error"] is None for i in rendered)
