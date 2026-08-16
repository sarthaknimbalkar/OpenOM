# SPDX-License-Identifier: MIT
"""RFC 8785 JSON Canonicalization (JCS) + the openOM integrity hash (spec §C).

The keystone of cross-implementation fidelity: two conformant implementations MUST produce
byte-identical output here, and therefore the same SHA-256. RFC 8785 itself performs no
Unicode normalization and assumes unique member names (RFC 8785 §3.1), so §C.1 mandates the
preprocessing done here (NFC, duplicate-key rejection, number-range checks) *before* JCS.
Serialization (key sorting, minimal escaping, ES number formatting) is delegated to the
vetted ``rfc8785`` library.

Producer vs Consumer contract (§C, §D)
--------------------------------------
The **producer** normalizes (NFC), canonicalizes, hashes the resulting bytes, and stores
*those exact bytes* as the payload plus the hash in the XMP marker. The **consumer** hashes
the stored bytes *as received* — it does NOT re-canonicalize before verifying. Verification
is therefore a byte comparison of ``sha256(stored_bytes)`` against the marker hash; it never
depends on the consumer re-running NFC/JCS. This asymmetry is deliberate: normalization
happens once, at authoring time, so a consumer on a different platform/library cannot perturb
the hash. ``canonicalize`` is the producer path; ``hash_bytes`` over stored bytes is the
consumer path (see :func:`openom_core.embed.read`).
"""

from __future__ import annotations

import copy
import hashlib
import math
from collections.abc import Mapping
from typing import Any
from unicodedata import normalize

import rfc8785

from .errors import IO_BADUTF8, IO_DUPKEY, IO_NUMRANGE, IO_STRUCTURE, CanonicalizationError

#: ECMAScript safe-integer limit; integers beyond this are silently rounded by the number
#: model, which would be data corruption (§C [OM-CANON-013]).
MAX_SAFE_INT = 2**53 - 1

#: Max nesting depth (§J JSON-hardening guard) — matches the JS parser for cross-impl parity.
MAX_DEPTH = 64


def _prepare(obj: Any, depth: int = 0) -> Any:
    """NFC-normalize strings + member names, reject duplicate keys and non-representable numbers.

    Returns a new structure ready for RFC 8785 serialization. Mutates nothing.
    """
    if depth > MAX_DEPTH:
        raise CanonicalizationError(IO_STRUCTURE, f"nesting exceeds {MAX_DEPTH}")
    # bool is an int subclass — must be checked first.
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, str):
        # A lone UTF-16 surrogate cannot be encoded as UTF-8; reject it explicitly with a
        # stable code rather than letting the serializer raise a bare UnicodeEncodeError.
        if any(0xD800 <= ord(ch) <= 0xDFFF for ch in obj):
            raise CanonicalizationError(IO_BADUTF8, "string contains an unpaired surrogate")
        return normalize("NFC", obj)
    if isinstance(obj, Mapping):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            if not isinstance(key, str):
                raise CanonicalizationError(IO_DUPKEY, f"non-string member name: {key!r}")
            nkey = normalize("NFC", key)
            if nkey in out:
                raise CanonicalizationError(IO_DUPKEY, f"duplicate member name after NFC: {nkey!r}")
            out[nkey] = _prepare(value, depth + 1)
        return out
    if isinstance(obj, (list, tuple)):
        return [_prepare(item, depth + 1) for item in obj]
    if isinstance(obj, int):
        if abs(obj) > MAX_SAFE_INT:
            raise CanonicalizationError(IO_NUMRANGE, f"integer exceeds 2^53-1: {obj}")
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise CanonicalizationError(IO_NUMRANGE, f"non-finite number: {obj}")
        if obj.is_integer() and abs(obj) > MAX_SAFE_INT:
            raise CanonicalizationError(IO_NUMRANGE, f"float integer exceeds 2^53-1: {obj}")
        return obj
    if obj is None:
        return None
    raise CanonicalizationError(IO_NUMRANGE, f"unsupported JSON type: {type(obj).__name__}")


def canonicalize(payload: Mapping[str, Any]) -> bytes:
    """Serialize a payload to its RFC 8785 JCS bytes (UTF-8, no BOM). Producer path.

    Applies the §C.1 preprocessing (NFC, unique keys, number range) then delegates
    serialization to ``rfc8785``. The top level MUST be a JSON object (§C.10); a bare
    array/scalar is rejected rather than hashed.
    """
    if not isinstance(payload, Mapping):
        raise CanonicalizationError(
            IO_STRUCTURE, f"top-level value must be an object, got {type(payload).__name__}"
        )
    prepared = _prepare(payload)
    try:
        return rfc8785.dumps(prepared)
    except CanonicalizationError:
        raise
    except Exception as exc:  # noqa: BLE001 — normalize any serializer failure to our code
        raise CanonicalizationError(IO_NUMRANGE, str(exc)) from exc


def hash_bytes(data: bytes) -> str:
    """The openOM integrity hash of already-canonical bytes: ``sha256:<lowercase-hex>``.

    Used on both the write path (over the bytes just produced) and the read/verify path
    (over the decompressed stored bytes, as received — no re-canonicalization; §C, §D).
    """
    return "sha256:" + hashlib.sha256(data).hexdigest()


def strip_signature(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep copy with ``meta.signature`` *removed* (not nulled), per [OM-CANON-003].

    In 0.1 the signature is always absent/null, so this is a no-op on real payloads; it exists
    so that adding a signature in a future version does not change the integrity hash.
    """
    out = copy.deepcopy(dict(payload))
    meta = out.get("meta")
    if isinstance(meta, dict) and "signature" in meta:
        meta.pop("signature", None)
    return out


def payload_hash(payload: Mapping[str, Any]) -> str:
    """Convenience: the integrity hash of a payload object (strip signature → JCS → sha256)."""
    return hash_bytes(canonicalize(strip_signature(payload)))
