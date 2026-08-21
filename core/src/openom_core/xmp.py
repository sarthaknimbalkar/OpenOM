# SPDX-License-Identifier: MIT
"""Read/write the openOM ``omspec:`` XMP marker in a PDF's document metadata (spec §D.2).

The marker MUST be **cross-implementation interoperable**: the JS (pdf-lib/pdf.js) writer emits
a namespaced ``omspec:`` packet, so the Python side emits and parses the identical namespaced
form. pikepdf's ``open_metadata`` cannot serialize a custom namespace (it drops the prefix and
writes unqualified elements that no conformant reader keys as ``omspec:*``), so we write the
``omspec`` ``rdf:Description`` directly as XML and read it by namespace URI. Existing XMP
(dc/pdf/…) is preserved: our block is injected alongside it, never replacing the packet.

Deterministic: no timestamps are written (§D [OM-EMB-011]).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pikepdf

OMSPEC_NS = "https://openom.app/ns/0.1#"
OMSPEC_PREFIX = "omspec"
SPEC_NAME = "openOM"

# Property order matches the Track B writer for cross-impl parity.
_ORDER = (
    "specName", "specVersion", "payloadFilename", "payloadHash", "assertedDate",
    "supersedes", "sourceDocHash",
)

# Matches our own prior omspec Description block (for idempotent re-embed).
_OMSPEC_DESC_RE = re.compile(
    r"[ \t]*<rdf:Description\b[^>]*xmlns:omspec=[^>]*>.*?</rdf:Description>\s*",
    re.DOTALL,
)
# Matches our own prior PDF/A extension-schema Description block (idempotent re-embed).
_PDFA_DESC_RE = re.compile(
    r"[ \t]*<rdf:Description\b[^>]*xmlns:pdfaExtension=[^>]*>.*?</rdf:Description>\s*",
    re.DOTALL,
)

# PDF/A requires every custom XMP namespace to be described by an embedded Extension Schema
# ([OM-XMP], PDF/A-3 §6.6.2.3). Without this, a PDF/A validator (veraPDF) flags the `omspec`
# namespace as undescribed. The block is static (it describes the fixed 0.1 marker properties) and
# is written by BOTH implementations so the PDF/A claim is producer-independent.
_PDFA_PROPS = (
    ("specName", "name of the embedded data standard"),
    ("specVersion", "version of the embedded data standard"),
    ("payloadFilename", "filename of the embedded om.json attachment"),
    ("payloadHash", "sha256 integrity hash of the canonical payload"),
    ("assertedDate", "assertion date of the embedded payload"),
    ("supersedes", "prior payload hash this payload replaces"),
)


def _pdfa_extension_description() -> str:
    props = "\n".join(
        "        <rdf:li rdf:parseType=\"Resource\">\n"
        f"         <pdfaProperty:name>{name}</pdfaProperty:name>\n"
        "         <pdfaProperty:valueType>Text</pdfaProperty:valueType>\n"
        "         <pdfaProperty:category>internal</pdfaProperty:category>\n"
        f"         <pdfaProperty:description>{_xml_escape(desc)}</pdfaProperty:description>\n"
        "        </rdf:li>"
        for name, desc in _PDFA_PROPS
    )
    return (
        '  <rdf:Description rdf:about=""\n'
        '      xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/"\n'
        '      xmlns:pdfaSchema="http://www.aiim.org/pdfa/ns/schema#"\n'
        '      xmlns:pdfaProperty="http://www.aiim.org/pdfa/ns/property#">\n'
        "   <pdfaExtension:schemas>\n"
        "    <rdf:Bag>\n"
        '     <rdf:li rdf:parseType="Resource">\n'
        "      <pdfaSchema:schema>openOM offering-memorandum payload marker</pdfaSchema:schema>\n"
        f"      <pdfaSchema:namespaceURI>{OMSPEC_NS}</pdfaSchema:namespaceURI>\n"
        f"      <pdfaSchema:prefix>{OMSPEC_PREFIX}</pdfaSchema:prefix>\n"
        "      <pdfaSchema:property>\n"
        "       <rdf:Seq>\n"
        f"{props}\n"
        "       </rdf:Seq>\n"
        "      </pdfaSchema:property>\n"
        "     </rdf:li>\n"
        "    </rdf:Bag>\n"
        "   </pdfaExtension:schemas>\n"
        "  </rdf:Description>"
    )

_EMPTY_PACKET = (
    '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="openOM 0.1">\n'
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
    source_doc_hash: str | None = None,
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
    if source_doc_hash is not None:
        props["sourceDocHash"] = source_doc_hash  # #5: provenance of the underlying source PDF
    # The PDF/A extension schema precedes the marker so a validator sees the namespace described.
    block = f"{_pdfa_extension_description()}\n{_omspec_description(props)}"

    if "/Metadata" in pdf.Root:
        xml = bytes(pdf.Root.Metadata.read_bytes()).decode("utf-8", "replace")
        xml = _OMSPEC_DESC_RE.sub("", xml)  # drop our prior blocks (no stacking)
        xml = _PDFA_DESC_RE.sub("", xml)
        if "</rdf:RDF>" in xml:
            xml = xml.replace("</rdf:RDF>", f"{block}\n </rdf:RDF>", 1)
        else:  # malformed/absent RDF - fall back to a fresh packet
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

    Parses the XMP XML by namespace URI, so it reads any conformant producer's marker,
    not only pikepdf-written metadata.
    """
    if "/Metadata" not in pdf.Root:
        return None
    return _parse_marker(bytes(pdf.Root.Metadata.read_bytes()))
