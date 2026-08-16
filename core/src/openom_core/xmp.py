# SPDX-License-Identifier: MIT
"""Read/write the OpenOM ``omspec:`` XMP marker in a PDF's document metadata (spec §D.2).

The marker MUST be **cross-implementation interoperable**: the Track B (pdf-lib/pdf.js)
writer emits a namespaced ``omspec:`` packet, so Track A must emit and parse the identical
namespaced form. pikepdf's ``open_metadata`` cannot serialize a custom namespace (it drops the
prefix and writes unqualified elements that no conformant reader keys as ``omspec:*``), so we
write the ``omspec`` ``rdf:Description`` directly as XML and read it by namespace URI. Existing
XMP (dc/pdf/…) is preserved: our block is injected alongside it, never replacing the packet.

Deterministic: no timestamps are written (§D [OM-EMB-011]).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pikepdf

OMSPEC_NS = "https://SPEC-DOMAIN-TBD/ns/0.1#"  # placeholder until Q1 (name lock)
OMSPEC_PREFIX = "omspec"
SPEC_NAME = "OpenOM"

# Property order matches the Track B writer for cross-impl parity.
_ORDER = ("specName", "specVersion", "payloadFilename", "payloadHash", "assertedDate", "supersedes")

# Matches our own prior omspec Description block (for idempotent re-embed).
_OMSPEC_DESC_RE = re.compile(
    r"[ \t]*<rdf:Description\b[^>]*xmlns:omspec=[^>]*>.*?</rdf:Description>\s*",
    re.DOTALL,
)

_EMPTY_PACKET = (
    '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="OpenOM 0.1">\n'
    ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
    " </rdf:RDF>\n"
    "</x:xmpmeta>\n"
    '<?xpacket end="w"?>'
)


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _omspec_description(props: dict[str, str]) -> str:
    rows = "\n".join(
        f"   <omspec:{k}>{_xml_escape(props[k])}</omspec:{k}>" for k in _ORDER if k in props
    )
    return (
        f'  <rdf:Description rdf:about="" xmlns:omspec="{OMSPEC_NS}">\n'
        f"{rows}\n"
        "  </rdf:Description>"
    )


def write_marker(
    pdf: pikepdf.Pdf,
    *,
    spec_version: str,
    payload_filename: str,
    payload_hash: str,
    asserted_date: str,
    supersedes: str | None = None,
) -> None:
    """Write the required omspec XMP properties ([OM-XMP-002]) as a conformant, namespaced
    ``omspec:`` block, preserving any existing XMP. Idempotent: replaces our prior block."""
    props = {
        "specName": SPEC_NAME,
        "specVersion": spec_version,
        "payloadFilename": payload_filename,
        "payloadHash": payload_hash,
        "assertedDate": asserted_date,
    }
    if supersedes is not None:
        props["supersedes"] = supersedes
    block = _omspec_description(props)

    if "/Metadata" in pdf.Root:
        xml = bytes(pdf.Root.Metadata.read_bytes()).decode("utf-8", "replace")
        xml = _OMSPEC_DESC_RE.sub("", xml)  # drop our prior block (no stacking)
        if "</rdf:RDF>" in xml:
            xml = xml.replace("</rdf:RDF>", f"{block}\n </rdf:RDF>", 1)
        else:  # malformed/absent RDF — fall back to a fresh packet
            xml = _EMPTY_PACKET.replace(" </rdf:RDF>", f"{block}\n </rdf:RDF>", 1)
    else:
        xml = _EMPTY_PACKET.replace(" </rdf:RDF>", f"{block}\n </rdf:RDF>", 1)

    stream = pdf.make_stream(xml.encode("utf-8"))
    stream.Type = pikepdf.Name.Metadata
    stream.Subtype = pikepdf.Name.XML
    pdf.Root.Metadata = stream


def _parse_marker(raw: bytes) -> dict[str, str] | None:
    # Parse from bytes so ElementTree honors any <?xml encoding?> declaration a PDF writer
    # may prepend; a str with an encoding declaration would raise ValueError. Strip a leading
    # UTF-8 BOM which would otherwise make the document ill-formed.
    raw = raw.lstrip(b"\xef\xbb\xbf")
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, ValueError):
        return None
    out: dict[str, str] = {}
    prefix = "{" + OMSPEC_NS + "}"
    for el in root.iter():
        if isinstance(el.tag, str) and el.tag.startswith(prefix) and el.text is not None:
            out[el.tag[len(prefix) :]] = el.text
    return out if "payloadHash" in out else None


def read_marker(pdf: pikepdf.Pdf) -> dict[str, str] | None:
    """Return the omspec marker properties, or ``None`` if no ``payloadHash`` is present.

    Parses the XMP XML by namespace URI, so it reads any conformant producer's marker
    (Track A or Track B), not only pikepdf-written metadata.
    """
    if "/Metadata" not in pdf.Root:
        return None
    return _parse_marker(bytes(pdf.Root.Metadata.read_bytes()))
