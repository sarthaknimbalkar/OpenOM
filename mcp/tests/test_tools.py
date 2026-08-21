"""M1 /mcp stdio tool surface (spec §I) - deterministic, path input, no network."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pikepdf
import pymupdf
from openom_core.embed import embed

from openom_mcp import tools

SPEC = Path(__file__).resolve().parents[2] / "spec"


def _sample() -> dict[str, Any]:
    return json.loads((SPEC / "samples" / "valid-stnl.json").read_text(encoding="utf-8"))


def _blank_pdf(path: Path) -> Path:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    buf = io.BytesIO()
    pdf.save(buf)
    path.write_bytes(buf.getvalue())
    return path


def _text_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Offering memorandum text layer. " * 12, fontsize=11)
    path.write_bytes(doc.tobytes())
    doc.close()
    return path


def _image_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40))
    pix.set_rect(pix.irect, (10, 20, 30))
    page.insert_image(pymupdf.Rect(10, 10, 90, 90), pixmap=pix)
    path.write_bytes(doc.tobytes())
    doc.close()
    return path


def _embedded(path: Path, tmp: Path) -> Path:
    base = _blank_pdf(tmp / "base.pdf").read_bytes()
    path.write_bytes(embed(base, _sample(), asserted_date="2026-08-15"))
    return path


# --- PdfRef + error envelope (OM-MCP-003/004) ------------------------------------------

def test_url_input_rejected_on_stdio() -> None:
    out = tools.om_inspect({"url": "https://example.com/x.pdf"})
    assert out["error"]["code"] == "OM-IO-008"
    assert out["error"]["retryable"] is False


def test_missing_path_is_clean_error() -> None:
    out = tools.om_read({"path": "does-not-exist.pdf"})
    assert out["error"]["code"] == "OM-IO-010"


def test_bad_page_range_maps_to_code(tmp_path: Path) -> None:
    pdf = _text_pdf(tmp_path / "t.pdf")
    out = tools.om_extract_text({"path": str(pdf)}, page_range="9-9")
    assert out["error"]["code"] == "OM-IO-012"


# --- read-only tools --------------------------------------------------------------------

def test_inspect(tmp_path: Path) -> None:
    pdf = _text_pdf(tmp_path / "t.pdf")
    out = tools.om_inspect({"path": str(pdf)})
    assert out["class"] in {"native", "hybrid", "scanned"}
    assert out["payload"] == {"present": False, "specVersion": None, "hashValid": None,
                              "originVerified": None}


def test_read_roundtrip_and_tamper(tmp_path: Path) -> None:
    good = _embedded(tmp_path / "e.pdf", tmp_path)
    out = tools.om_read({"path": str(good)})
    assert out["payload"] is not None
    assert out["verification"]["hashValid"] is True
    assert out["payloadHash"].startswith("sha256:")

    # tamper the XMP hash → read MUST surface null payload with hashValid false (OM-MCP-011)
    with pikepdf.open(str(good)) as pdf:
        from openom_core.xmp import write_marker

        write_marker(pdf, spec_version="0.1", payload_filename="om.json",
                     payload_hash="sha256:" + "0" * 64, asserted_date="2026-08-15")
        pdf.save(str(tmp_path / "tampered.pdf"))
    bad = tools.om_read({"path": str(tmp_path / "tampered.pdf")})
    assert bad["payload"] is None
    assert bad["verification"]["hashValid"] is False


def test_extract_text_paginates(tmp_path: Path) -> None:
    pdf = _text_pdf(tmp_path / "t.pdf")
    first = tools.om_extract_text({"path": str(pdf)}, max_chars=40)
    assert first["truncated"] is True and first["nextCursor"]
    second = tools.om_extract_text({"path": str(pdf)}, max_chars=40, cursor=first["nextCursor"])
    assert second["text"] and second["text"] != first["text"]


def test_extract_images_manifest_paths(tmp_path: Path) -> None:
    pdf = _image_pdf(tmp_path / "img.pdf")
    out = tools.om_extract_images({"path": str(pdf)}, out_dir=str(tmp_path / "out"))
    assert out["manifest"], "expected at least one image"
    entry = out["manifest"][0]
    assert Path(entry["path"]).exists() and entry["bytes"] > 0
    assert "link" not in entry  # stdio uses local paths, never inline bytes


# --- validate + embed -------------------------------------------------------------------

def test_validate_report(tmp_path: Path) -> None:
    ok = tools.om_validate(_sample())
    assert ok["ok"] is True and ok["errors"] == []
    assert ok["canonical"]["hash"].startswith("sha256:")
    bad = tools.om_validate({"@type": "RealEstateListing"})  # missing required fields
    assert bad["ok"] is False and bad["errors"]


def test_embed_valid_then_refuse_invalid(tmp_path: Path) -> None:
    base = _blank_pdf(tmp_path / "base.pdf")
    out = tools.om_embed({"path": str(base)}, _sample(), out_path=str(tmp_path / "out.pdf"))
    assert Path(out["pdf"]["path"]).exists()
    assert out["payloadHash"].startswith("sha256:")
    assert out["xmp"]["specName"] == "openOM"

    refused = tools.om_embed({"path": str(base)}, {"@type": "RealEstateListing"})
    assert "error" in refused
    assert refused["error"]["details"]["errors"]  # §H findings carried in details
