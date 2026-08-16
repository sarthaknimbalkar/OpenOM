# SPDX-License-Identifier: MIT
"""Read/write the OpenOM ``omspec:`` XMP marker in a PDF's document metadata (spec §D.2).

Uses pikepdf's ``open_metadata`` with ``set_pikepdf_as_editor=False`` so pikepdf does not inject
its own Producer/ModifyDate (which would make output non-deterministic; §D [OM-EMB-011]).
Custom-namespace properties are set directly by prefixed key — pikepdf handles the ``omspec``
prefix without explicit registration (verified against pikepdf 10.x).
"""

from __future__ import annotations

import pikepdf

OMSPEC_NS = "https://SPEC-DOMAIN-TBD/ns/0.1#"  # placeholder until Q1 (name lock)
OMSPEC_PREFIX = "omspec"
SPEC_NAME = "OpenOM"


def write_marker(
    pdf: pikepdf.Pdf,
    *,
    spec_version: str,
    payload_filename: str,
    payload_hash: str,
    asserted_date: str,
    supersedes: str | None = None,
) -> None:
    """Write the required omspec XMP properties ([OM-XMP-002]), preserving other XMP."""
    with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
        meta["omspec:specName"] = SPEC_NAME
        meta["omspec:specVersion"] = spec_version
        meta["omspec:payloadFilename"] = payload_filename
        meta["omspec:payloadHash"] = payload_hash
        meta["omspec:assertedDate"] = asserted_date
        if supersedes is not None:
            meta["omspec:supersedes"] = supersedes
        elif "omspec:supersedes" in meta:
            del meta["omspec:supersedes"]


def read_marker(pdf: pikepdf.Pdf) -> dict[str, str] | None:
    """Return the omspec marker properties, or ``None`` if no ``payloadHash`` is present."""
    with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
        payload_hash = meta.get("omspec:payloadHash")
        if not payload_hash:
            return None
        out: dict[str, str] = {"payloadHash": payload_hash}
        for short, key in (
            ("specName", "omspec:specName"),
            ("specVersion", "omspec:specVersion"),
            ("payloadFilename", "omspec:payloadFilename"),
            ("assertedDate", "omspec:assertedDate"),
            ("supersedes", "omspec:supersedes"),
        ):
            value = meta.get(key)
            if value is not None:
                out[short] = value
        return out
