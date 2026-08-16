# SPDX-License-Identifier: MIT
"""Embed / read the om.json payload in a PDF via pikepdf (spec §D).

Non-destructive by construction: pikepdf appends the embedded file + XMP marker without
touching page content. The catalog ``/AF`` array is added manually — assigning to
``Pdf.attachments`` populates the ``/EmbeddedFiles`` name tree but NOT ``/AF`` ([OM-EMB-002]).
The exact JCS bytes are stored verbatim ([OM-EMB-010]); the integrity hash is over those bytes.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Any

import pikepdf

from .canonical import canonicalize, hash_bytes, strip_signature
from .errors import PayloadTooLargeError
from .xmp import read_marker, write_marker

#: Decompressed-payload cap (§J [OM-SEC-002]).
MAX_PAYLOAD_BYTES = 5_000_000

PAYLOAD_NAME = "om.json"
MIME = "application/ld+json"
SUBTYPE = pikepdf.Name("/application/ld+json")  # serialized name-escaped as /application#2Fld+json


@dataclass
class ReadResult:
    """Result of reading a payload from a PDF (§I om_read shape)."""

    present: bool
    payload: dict[str, Any] | None
    hash_valid: bool | None
    origin_verified: None = None  # read-time origin check is a Consumer concern; null in core
    signature_valid: None = None  # reserved (§10 layer 4)


def _remove_existing(pdf: pikepdf.Pdf) -> None:
    """Remove any existing om.json attachment and its /AF reference (idempotent embed)."""
    if PAYLOAD_NAME not in pdf.attachments:
        return
    old_objgen = pdf.attachments[PAYLOAD_NAME].obj.objgen
    # Filter /AF while the referenced object is still live, then delete the attachment.
    if "/AF" in pdf.Root:
        kept = [f for f in pdf.Root.AF if f.objgen != old_objgen]
        if kept:
            pdf.Root.AF = pikepdf.Array(kept)
        else:
            del pdf.Root.AF
    del pdf.attachments[PAYLOAD_NAME]


def _ensure_af(pdf: pikepdf.Pdf, spec: pikepdf.Object) -> None:
    """Ensure the catalog /AF array references the payload's Filespec ([OM-EMB-002])."""
    if "/AF" not in pdf.Root:
        pdf.Root.AF = pikepdf.Array([spec])
        return
    if all(f.objgen != spec.objgen for f in pdf.Root.AF):
        pdf.Root.AF.append(spec)


def _set_subtype(spec: pikepdf.Object) -> None:
    """Set /Subtype application/ld+json on the embedded-file stream(s) ([OM-EMB-004])."""
    ef = spec.EF
    for key in ("/F", "/UF"):
        if key in ef:
            ef[key].Subtype = SUBTYPE


def embed(
    pdf_bytes: bytes, payload: dict[str, Any], *, asserted_date: str, badge: bool = False
) -> bytes:
    """Embed ``payload`` as om.json and return the new PDF bytes. Never mutates the input."""
    # signature excluded from the integrity preimage ([OM-CANON-003])
    data = canonicalize(strip_signature(payload))
    if len(data) > MAX_PAYLOAD_BYTES:
        raise PayloadTooLargeError(len(data), MAX_PAYLOAD_BYTES)
    payload_hash = hash_bytes(data)
    spec_version = str(payload.get("specVersion", "0.1"))

    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        # §D.4 idempotent re-embed: a *different* prior payload is superseded; an identical
        # re-embed is a no-op (no self-supersede, cf. OMW-W050).
        prior = read_marker(pdf)
        prior_hash = prior.get("payloadHash") if prior else None
        supersedes = prior_hash if (prior_hash and prior_hash != payload_hash) else None

        _remove_existing(pdf)
        # pikepdf's stub marks description/filename/dates as required; runtime defaults them.
        # We intentionally omit dates for determinism (§D [OM-EMB-011]).
        filespec = pikepdf.AttachedFileSpec(pdf, data, mime_type=MIME)  # type: ignore[call-arg]
        filespec.relationship = pikepdf.Name.Data  # /AFRelationship (kwarg missing from stub)
        pdf.attachments[PAYLOAD_NAME] = filespec
        spec_obj = pdf.attachments[PAYLOAD_NAME].obj
        _ensure_af(pdf, spec_obj)
        _set_subtype(spec_obj)
        write_marker(
            pdf,
            spec_version=spec_version,
            payload_filename=PAYLOAD_NAME,
            payload_hash=payload_hash,
            asserted_date=asserted_date,
            supersedes=supersedes,
        )
        out = io.BytesIO()
        pdf.save(out, deterministic_id=True)
        return out.getvalue()


def read(pdf_bytes: bytes) -> ReadResult:
    """Read + integrity-verify the om.json payload (detection order [OM-XMP-003])."""
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        marker = read_marker(pdf)
        if PAYLOAD_NAME not in pdf.attachments:
            return ReadResult(present=False, payload=None, hash_valid=None)
        raw = pdf.attachments[PAYLOAD_NAME].get_file().read_bytes()
        if len(raw) > MAX_PAYLOAD_BYTES:
            raise PayloadTooLargeError(len(raw), MAX_PAYLOAD_BYTES)
        payload = json.loads(raw)
        xmp_hash = marker.get("payloadHash") if marker else None
        hash_valid = (hash_bytes(raw) == xmp_hash) if xmp_hash else None
        return ReadResult(present=True, payload=payload, hash_valid=hash_valid)
