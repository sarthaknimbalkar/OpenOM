"""Task 9: image extraction — SMask/CMYK/dedupe (spec §8b)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from _make_scan import make_scanned, make_text_pdf
from openom_core.images import extract_images


def test_no_images() -> None:
    manifest = extract_images(make_text_pdf())
    assert manifest["images"] == []
    assert manifest["deduped"] == 0


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
