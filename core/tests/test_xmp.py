"""Task 4: omspec XMP marker read/write (spec §D.2)."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET

import pikepdf

from openom_core.xmp import OMSPEC_NS, read_marker, write_marker


def _blank_pdf() -> pikepdf.Pdf:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    return pdf


def _roundtrip(pdf: pikepdf.Pdf) -> pikepdf.Pdf:
    buf = io.BytesIO()
    pdf.save(buf)
    return pikepdf.open(io.BytesIO(buf.getvalue()))


_PDFA_EXT_NS = "http://www.aiim.org/pdfa/ns/extension/"
_PDFA_SCHEMA_NS = "http://www.aiim.org/pdfa/ns/schema#"
_PDFA_PROP_NS = "http://www.aiim.org/pdfa/ns/property#"


def _metadata_xml(pdf: pikepdf.Pdf) -> bytes:
    return bytes(pdf.Root.Metadata.read_bytes())


def test_pdfa_extension_schema_describes_omspec() -> None:
    """#2: the omspec namespace carries a PDF/A Extension Schema Description (well-formed,
    correct namespaceURI/prefix, one property entry per marker field)."""
    pdf = _blank_pdf()
    write_marker(
        pdf, spec_version="0.1", payload_filename="om.json",
        payload_hash="sha256:" + "b" * 64, asserted_date="2026-08-15",
        supersedes="sha256:" + "c" * 64,
    )
    xml = _metadata_xml(_roundtrip(pdf))
    root = ET.fromstring(xml)  # must be well-formed
    schemas = root.iter(f"{{{_PDFA_SCHEMA_NS}}}namespaceURI")
    assert any((e.text or "") == OMSPEC_NS for e in schemas), "omspec namespace not described"
    prefixes = [e.text for e in root.iter(f"{{{_PDFA_SCHEMA_NS}}}prefix")]
    assert "omspec" in prefixes
    names = {e.text for e in root.iter(f"{{{_PDFA_PROP_NS}}}name")}
    assert {"specName", "specVersion", "payloadFilename", "payloadHash", "assertedDate",
            "supersedes"} <= names


def test_pdfa_extension_schema_is_idempotent() -> None:
    """Re-writing the marker MUST NOT stack a second extension-schema block."""
    pdf = _blank_pdf()
    for date in ("2026-08-15", "2026-08-16", "2026-08-17"):
        write_marker(pdf, spec_version="0.1", payload_filename="om.json",
                     payload_hash="sha256:" + "d" * 64, asserted_date=date)
        pdf = _roundtrip(pdf)
    xml = _metadata_xml(pdf).decode("utf-8")
    assert xml.count("xmlns:pdfaExtension") == 1
    assert xml.count("xmlns:omspec") == 1


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
    assert got["specName"] == "openOM"
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


def _set_metadata(pdf: pikepdf.Pdf, data: bytes) -> None:
    stream = pdf.make_stream(data)
    stream.Type = pikepdf.Name.Metadata
    stream.Subtype = pikepdf.Name.XML
    pdf.Root.Metadata = stream


def test_written_xmp_is_well_formed_and_namespaced() -> None:
    """Peak: the marker MUST be well-formed RDF/XML with the omspec namespace (cross-impl)."""
    pdf = _blank_pdf()
    write_marker(
        pdf,
        spec_version="0.1",
        payload_filename="om.json",
        payload_hash="sha256:" + "a" * 64,
        asserted_date="2026-08-15",
    )
    pdf2 = _roundtrip(pdf)
    raw = bytes(pdf2.Root.Metadata.read_bytes()).lstrip(b"\xef\xbb\xbf")
    root = ET.fromstring(raw)  # bytes: honors any <?xml encoding?>; raises if not well-formed
    tags = {e.tag for e in root.iter()}
    assert "{" + OMSPEC_NS + "}payloadHash" in tags
    assert "{" + OMSPEC_NS + "}specName" in tags


def test_malformed_existing_xmp_replaced_with_valid_marker() -> None:
    """A document with garbage /Metadata still gets a valid, readable marker."""
    pdf = _blank_pdf()
    _set_metadata(pdf, b"this is <<< not >>> xml at all")
    write_marker(
        pdf,
        spec_version="0.1",
        payload_filename="om.json",
        payload_hash="sha256:" + "e" * 64,
        asserted_date="2026-08-15",
    )
    got = read_marker(_roundtrip(pdf))
    assert got is not None
    assert got["payloadHash"] == "sha256:" + "e" * 64


def test_read_marker_none_on_unparseable_metadata() -> None:
    # Read without a save roundtrip: pikepdf sanitizes invalid XML on save, so this exercises
    # the parser's own ParseError -> None path on genuinely unparseable metadata.
    pdf = _blank_pdf()
    _set_metadata(pdf, b"<not-xml <<<")
    assert read_marker(pdf) is None


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
