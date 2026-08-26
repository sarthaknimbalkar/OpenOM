# SPDX-License-Identifier: MIT
"""Embed / read the om.json payload in a PDF via pikepdf (spec §D).

Non-destructive by construction: pikepdf appends the embedded file + XMP marker without
touching page content. The catalog ``/AF`` array is added manually - assigning to
``Pdf.attachments`` populates the ``/EmbeddedFiles`` name tree but NOT ``/AF`` ([OM-EMB-002]).
The exact JCS bytes are stored verbatim ([OM-EMB-010]); the integrity hash is over those bytes.
"""

from __future__ import annotations

import io
import os
import re
import tempfile
import zlib
from dataclasses import dataclass
from typing import Any

import pikepdf

from .canonical import canonicalize, hash_bytes, parse_hardened, strip_signature
from .errors import Finding, PayloadTooLargeError, SignedEmbedError
from .xmp import _marker_props, read_marker, render_marker_xml, write_marker

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
    source_doc_hash: str | None = None  # #5: marker sourceDocHash (provenance of the source PDF)
    payload_hash: str | None = None  # hash of the stored payload bytes (the dedupe/audit key)
    encrypted: bool = False  # the PDF is password-protected and could not be opened to read


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


def input_encrypted(pdf_bytes: bytes) -> bool:
    """True if the input PDF is encrypted (permission encryption with an empty user password, which
    pikepdf opens transparently and embed() then writes out UNENCRYPTED - a silent security-posture
    change worth signaling to the author). A password-protected PDF raises on open and never reaches
    here, so this is specifically the restrictions-only case (#4)."""
    try:
        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            return bool(pdf.is_encrypted)
    except pikepdf.PasswordError:
        return False


def _is_signed(pdf: pikepdf.Pdf) -> bool:
    """True if the PDF carries a digital signature (§10 layer 4 / #3 [OM-EMB-020]).

    A full-rewrite save invalidates a byte-range signature; when this is True, embed uses an
    incremental-update save instead, appending the payload so the signed bytes stay untouched.
    Detects the AcroForm ``SigFlags`` "signatures exist" bit, any ``/FT /Sig`` field carrying a
    ``/V``, or a ``/Perms`` (DocMDP/UR) entry - covering approval and certification signatures.
    """
    root = pdf.Root
    if "/Perms" in root:
        return True
    acro = root.get("/AcroForm")
    if acro is None:
        return False
    sig_flags = acro.get("/SigFlags")
    if sig_flags is not None and int(sig_flags) & 1:
        return True
    fields = acro.get("/Fields")
    if fields is None:
        return False
    return any(f.get("/FT") == pikepdf.Name.Sig and "/V" in f for f in fields)


@dataclass
class _EmbedFields:
    data: bytes
    payload_hash: str
    spec_version: str
    supersedes: str | None
    source_doc_hash: str


def _plan_embed(pdf: pikepdf.Pdf, pdf_bytes: bytes, payload: dict[str, Any]) -> _EmbedFields:
    """Compute the payload bytes + marker fields (supersedes/sourceDocHash) - shared by both the
    full-rewrite and incremental save paths so a signed OM gets identical provenance semantics."""
    # signature excluded from the integrity preimage ([OM-CANON-003])
    data = canonicalize(strip_signature(payload))
    if len(data) > MAX_PAYLOAD_BYTES:
        raise PayloadTooLargeError(len(data), MAX_PAYLOAD_BYTES)
    payload_hash = hash_bytes(data)
    # §D.4 re-embed semantics:
    #  - a *different* prior payload is superseded (supersedes = prior hash);
    #  - an *identical* re-embed carries the prior supersedes forward (no lineage wipe, no
    #    self-supersede); a first embed has no predecessor (supersedes = None).
    prior = read_marker(pdf)
    prior_hash = prior.get("payloadHash") if prior else None
    prior_supersedes = prior.get("supersedes") if prior else None
    if prior_hash and prior_hash != payload_hash:
        supersedes: str | None = prior_hash
    elif prior_hash == payload_hash:
        supersedes = prior_supersedes
    else:
        supersedes = None
    # #5: sourceDocHash identifies the underlying source PDF, held STABLE across reprices - computed
    # once (first embed) and carried forward from the prior marker on every re-embed.
    prior_source = prior.get("sourceDocHash") if prior else None
    source_doc_hash = prior_source or hash_bytes(pdf_bytes)
    return _EmbedFields(
        data=data,
        payload_hash=payload_hash,
        spec_version=str(payload.get("specVersion", "0.1")),
        supersedes=supersedes,
        source_doc_hash=source_doc_hash,
    )


def embed(
    pdf_bytes: bytes, payload: dict[str, Any], *, asserted_date: str, badge: bool = False
) -> bytes:
    """Embed ``payload`` as om.json and return the new PDF bytes. Never mutates the input.

    A *signed* input (#3 [OM-EMB-020]) is embedded via an incremental-update save - the payload is
    appended after the signed byte range so the signature stays cryptographically intact - rather
    than the default full-rewrite (which would invalidate it). Both paths write the identical
    payload bytes and XMP marker, so the result reads the same regardless of the save method.
    """
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        fields = _plan_embed(pdf, pdf_bytes, payload)
        signed = _is_signed(pdf)

    if signed:
        return _embed_incremental(pdf_bytes, fields, asserted_date)

    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        _remove_existing(pdf)
        # pikepdf's stub marks description/filename/dates as required; runtime defaults them.
        # We intentionally omit dates for determinism (§D [OM-EMB-011]).
        filespec = pikepdf.AttachedFileSpec(pdf, fields.data, mime_type=MIME)  # type: ignore[call-arg]
        filespec.relationship = pikepdf.Name.Data  # /AFRelationship (kwarg missing from stub)
        pdf.attachments[PAYLOAD_NAME] = filespec
        spec_obj = pdf.attachments[PAYLOAD_NAME].obj
        _ensure_af(pdf, spec_obj)
        _set_subtype(spec_obj)
        write_marker(
            pdf,
            spec_version=fields.spec_version,
            payload_filename=PAYLOAD_NAME,
            payload_hash=fields.payload_hash,
            asserted_date=asserted_date,
            supersedes=fields.supersedes,
            source_doc_hash=fields.source_doc_hash,
        )
        out = io.BytesIO()
        pdf.save(out, deterministic_id=True)
        return out.getvalue()


def _embed_incremental(pdf_bytes: bytes, fields: _EmbedFields, asserted_date: str) -> bytes:
    """Append the payload to a *signed* PDF via a fitz incremental-update save (#3 [OM-EMB-020]).

    Builds the om.json embedded-file stream, an indirect /Filespec (/AFRelationship /Data,
    /Subtype application/ld+json), the /EmbeddedFiles name-tree entry, the catalog /AF reference,
    and the XMP marker - then saves incrementally so the original signed bytes are preserved as a
    byte-exact prefix. The marker bytes come from the same ``render_marker_xml`` the full-rewrite
    path uses, so the two producers agree. fitz's incremental save requires a real file whose bytes
    equal the source, so the work happens in a temp file.
    """
    # PyMuPDF is the optional [render] extra; the signed-OM incremental path is the one embed case
    # that needs it. Imported lazily with a clear hint so the pikepdf-only core stays MIT-clean.
    try:
        import pymupdf
    except ImportError as exc:
        raise SignedEmbedError(
            "embedding a signed PDF needs PyMuPDF: pip install 'openom-core[render]'"
        ) from exc

    props = _marker_props(
        spec_version=fields.spec_version,
        payload_filename=PAYLOAD_NAME,
        payload_hash=fields.payload_hash,
        asserted_date=asserted_date,
        supersedes=fields.supersedes,
        source_doc_hash=fields.source_doc_hash,
    )
    # A TemporaryDirectory (vs NamedTemporaryFile + os.unlink) so cleanup can't mask the real error
    # with a Windows "file in use" (WinError 32) in the finally block.
    with tempfile.TemporaryDirectory(prefix="openom_signed_") as tmpdir:
        path = os.path.join(tmpdir, "in.pdf")
        with open(path, "wb") as fh:
            fh.write(pdf_bytes)
        doc = pymupdf.open(path)
        try:
            # If pymupdf had to REBUILD the xref to open this file, an incremental append is not a
            # byte-exact extension of the original - the signed prefix would change and the
            # signature break. Refuse cleanly (OM-EMB-021) rather than ship an invalid signature.
            if getattr(doc, "is_repaired", False):
                raise SignedEmbedError(
                    "this signed PDF needed its cross-reference table rebuilt to open, so an "
                    "incremental (signature-preserving) embed is not safe; embed an unsigned copy "
                    "or re-issue the signature after embedding"
                )
            cat = doc.pdf_catalog()
            # 1. embedded-file stream (verbatim JCS bytes; pikepdf read decodes the filter)
            ef = doc.get_new_xref()
            doc.update_object(ef, "<< /Type /EmbeddedFile /Subtype /application#2Fld+json >>")
            doc.update_stream(ef, fields.data, compress=True)
            # 2. indirect /Filespec ([OM-EMB-002]/[OM-EMB-004])
            spec = doc.get_new_xref()
            doc.update_object(
                spec,
                f"<< /Type /Filespec /F ({PAYLOAD_NAME}) /UF ({PAYLOAD_NAME}) "
                f"/AFRelationship /Data /Desc (openOM payload) "
                f"/EF << /F {ef} 0 R /UF {ef} 0 R >> >>",
            )
            # 3. /EmbeddedFiles name tree - drop any prior om.json, keep other attachments
            entries = [
                f"({nm}) {xr} 0 R"
                for nm, xr in _name_tree_entries(doc, cat)
                if nm != PAYLOAD_NAME
            ]
            entries.append(f"({PAYLOAD_NAME}) {spec} 0 R")
            doc.xref_set_key(cat, "Names/EmbeddedFiles/Names", "[" + " ".join(entries) + "]")
            # 4. catalog /AF - drop any prior om.json filespec ref (by resolving each ref's /F,
            # since a re-embed's prior filespec has a different xref), append ours
            af = [r for r in _af_refs(doc, cat) if not _is_om_filespec(doc, r)]
            af.append(f"{spec} 0 R")
            doc.xref_set_key(cat, "AF", "[" + " ".join(af) + "]")
            # 5. XMP marker (identical bytes to the full-rewrite path)
            existing = _existing_metadata_xml(doc, cat)
            meta = doc.get_new_xref()
            doc.update_object(meta, "<< /Type /Metadata /Subtype /XML >>")
            marker_xml = render_marker_xml(existing, props).encode("utf-8")
            doc.update_stream(meta, marker_xml, compress=False)
            doc.xref_set_key(cat, "Metadata", f"{meta} 0 R")
            try:
                doc.saveIncr()
            except Exception as exc:  # noqa: BLE001 - any fitz save failure -> typed refusal
                raise SignedEmbedError(
                    f"incremental save failed on this signed PDF: {exc}"
                ) from exc
        finally:
            doc.close()
        with open(path, "rb") as fh:
            out = fh.read()
    # Postcondition the whole feature promises: the original signed bytes stay a byte-exact prefix,
    # so every byte the /ByteRange signs is unchanged. Never return a doc that broke it.
    if not out.startswith(pdf_bytes):
        raise SignedEmbedError("incremental embed did not preserve the signed byte prefix")
    return out


def _name_tree_entries(doc: Any, cat: int) -> list[tuple[str, str]]:
    """(name, 'N 0 R') pairs already in /Names/EmbeddedFiles/Names, or [] if none."""
    kind, val = doc.xref_get_key(cat, "Names/EmbeddedFiles/Names")
    if kind != "array":
        return []
    return re.findall(r"\(([^)]*)\)\s*(\d+ 0 R)", val)


def _af_refs(doc: Any, cat: int) -> list[str]:
    """Existing catalog /AF indirect refs ('N 0 R'), or [] if none."""
    kind, val = doc.xref_get_key(cat, "AF")
    if kind != "array":
        return []
    return re.findall(r"\d+ 0 R", val)


def _is_om_filespec(doc: Any, ref: str) -> bool:
    """True if the /AF ref 'N 0 R' points to a filespec whose /F is our om.json (drop it on
    re-embed so /AF never stacks duplicate payload references)."""
    m = re.match(r"(\d+) 0 R", ref)
    if not m:
        return False
    kind, val = doc.xref_get_key(int(m.group(1)), "F")
    return bool(kind == "string" and val == PAYLOAD_NAME)


def _existing_metadata_xml(doc: Any, cat: int) -> str | None:
    """The current catalog /Metadata XML, or None - so our marker merges alongside existing XMP."""
    kind, val = doc.xref_get_key(cat, "Metadata")
    if kind != "xref":
        return None
    meta_xref = int(re.match(r"(\d+) 0 R", val).group(1))  # type: ignore[union-attr]
    raw = doc.xref_stream(meta_xref)
    return raw.decode("utf-8", "replace") if raw else None


def reembed_warnings(
    pdf_bytes: bytes, payload: dict[str, Any], *, asserted_date: str
) -> list[Finding]:
    """Non-blocking re-embed warnings against an existing PDF (§H). Pure; ``embed`` stays
    bytes→bytes, so callers (CLI/MCP) compose this to surface provenance issues.

    OMW-W051: the new assertedDate precedes the payload it would supersede (time going
    backwards on a reprice). Warnings never block.
    """
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        prior = read_marker(pdf)
    if not prior:
        return []
    payload_hash = hash_bytes(canonicalize(strip_signature(payload)))
    prior_hash = prior.get("payloadHash")
    prior_date = prior.get("assertedDate")
    out: list[Finding] = []
    if prior_hash and prior_hash != payload_hash and prior_date and asserted_date < prior_date:
        out.append(
            Finding(
                "OMW-W051",
                "warning",
                "/assertedDate",
                "assertedDate precedes the superseded payload's assertedDate",
                expected=prior_date,
                actual=asserted_date,
            )
        )
    return out


def _find_ef_stream(pdf: pikepdf.Pdf) -> pikepdf.Object | None:
    """Locate the om.json embedded-file stream in spec detection order ([OM-XMP-003]).

    Authoritative path: catalog ``/AF`` → Filespec (``/UF`` or ``/F`` == om.json) → ``/EF``.
    Falls back to the ``/EmbeddedFiles`` name tree for producers that populate only that.
    """

    def _ef_of(spec: pikepdf.Object) -> pikepdf.Object | None:
        if "/EF" not in spec:
            return None
        ef = spec.EF
        for key in ("/UF", "/F"):
            if key in ef:
                return ef[key]
        return None

    if "/AF" in pdf.Root:
        for spec in pdf.Root.AF:
            names = {str(spec[k]) for k in ("/UF", "/F") if k in spec}
            if PAYLOAD_NAME in names:
                stream = _ef_of(spec)
                if stream is not None:
                    return stream
    if PAYLOAD_NAME in pdf.attachments:  # fallback: EmbeddedFiles name tree
        return _ef_of(pdf.attachments[PAYLOAD_NAME].obj)
    return None


def _decoded_payload_bytes(stream: pikepdf.Object) -> bytes:
    """Decode the EF stream to raw payload bytes, bounding size *before* full materialization.

    A malicious PDF can hide a decompression bomb in a tiny compressed stream. We read the
    stored (compressed) bytes - always bounded by the file itself - reject if already over the
    cap, then inflate with a hard ceiling rather than decompressing unbounded into memory.
    """
    raw = bytes(stream.read_raw_bytes())
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise PayloadTooLargeError(len(raw), MAX_PAYLOAD_BYTES)

    filt = stream.get("/Filter")
    names = [str(filt)] if isinstance(filt, pikepdf.Name) else [str(n) for n in (filt or [])]
    # Plain FlateDecode (no predictor) - the common case for our writes and pdf-lib - can be
    # inflated with a bounded zlib object. Anything exotic (predictors, other filters) defers
    # to pikepdf's decoder, still guarded by the compressed-size cap above and a post-check.
    if names == ["/FlateDecode"] and "/DecodeParms" not in stream and "/DP" not in stream:
        data = _bounded_inflate(raw)
    elif not names:
        data = raw  # stored uncompressed
    else:
        data = bytes(stream.read_bytes())
    if len(data) > MAX_PAYLOAD_BYTES:
        raise PayloadTooLargeError(len(data), MAX_PAYLOAD_BYTES)
    return data


def _bounded_inflate(raw: bytes) -> bytes:
    obj = zlib.decompressobj()
    out = obj.decompress(raw, MAX_PAYLOAD_BYTES + 1)
    if obj.unconsumed_tail:  # hit the ceiling before the input was exhausted
        raise PayloadTooLargeError(MAX_PAYLOAD_BYTES + 1, MAX_PAYLOAD_BYTES)
    return out + obj.flush()


def read(pdf_bytes: bytes) -> ReadResult:
    """Read + integrity-verify the om.json payload (detection order [OM-XMP-003]). A password-
    protected PDF returns an encrypted ReadResult rather than raising (§I 'encrypted' state)."""
    try:
        pdf_ctx = pikepdf.open(io.BytesIO(pdf_bytes))
    except pikepdf.PasswordError:
        return ReadResult(present=False, payload=None, hash_valid=None, encrypted=True)
    with pdf_ctx as pdf:
        marker = read_marker(pdf)
        stream = _find_ef_stream(pdf)
        if stream is None:
            return ReadResult(present=False, payload=None, hash_valid=None)
        raw = _decoded_payload_bytes(stream)
        payload = parse_hardened(raw)  # §J read-side hardening: dup-key + depth guard [Mi18]
        stored_hash = hash_bytes(raw)
        xmp_hash = marker.get("payloadHash") if marker else None
        hash_valid = (stored_hash == xmp_hash) if xmp_hash else None
        return ReadResult(
            present=True,
            payload=payload,
            hash_valid=hash_valid,
            source_doc_hash=marker.get("sourceDocHash") if marker else None,
            payload_hash=stored_hash,  # the actual content hash - dedupe key + audit anchor
        )
