"""Task 4: omspec XMP marker read/write (spec §D.2)."""

from __future__ import annotations

import io

import pikepdf

from openom_core.xmp import read_marker, write_marker


def _blank_pdf() -> pikepdf.Pdf:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    return pdf


def _roundtrip(pdf: pikepdf.Pdf) -> pikepdf.Pdf:
    buf = io.BytesIO()
    pdf.save(buf)
    return pikepdf.open(io.BytesIO(buf.getvalue()))


def test_write_then_read() -> None:
    pdf = _blank_pdf()
    write_marker(
        pdf,
        spec_version="0.1",
        payload_filename="om.json",
        payload_hash="sha256:" + "a" * 64,
        asserted_date="2026-08-15",
        supersedes=None,
    )
    got = read_marker(_roundtrip(pdf))
    assert got is not None
    assert got["specName"] == "OpenOM"
    assert got["specVersion"] == "0.1"
    assert got["payloadFilename"] == "om.json"
    assert got["payloadHash"] == "sha256:" + "a" * 64
    assert got["assertedDate"] == "2026-08-15"
    assert "supersedes" not in got  # absent when None


def test_supersedes_written_when_present() -> None:
    pdf = _blank_pdf()
    prior = "sha256:" + "b" * 64
    write_marker(
        pdf,
        spec_version="0.1",
        payload_filename="om.json",
        payload_hash="sha256:" + "c" * 64,
        asserted_date="2026-08-16",
        supersedes=prior,
    )
    got = read_marker(_roundtrip(pdf))
    assert got is not None
    assert got["supersedes"] == prior


def test_no_marker_reads_none() -> None:
    assert read_marker(_roundtrip(_blank_pdf())) is None


def test_existing_xmp_preserved() -> None:
    pdf = _blank_pdf()
    with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
        meta["dc:title"] = "Existing Title"
    write_marker(
        pdf,
        spec_version="0.1",
        payload_filename="om.json",
        payload_hash="sha256:" + "d" * 64,
        asserted_date="2026-08-15",
    )
    pdf2 = _roundtrip(pdf)
    with pdf2.open_metadata(set_pikepdf_as_editor=False) as meta:
        assert meta.get("dc:title") == "Existing Title"
    assert read_marker(pdf2) is not None
