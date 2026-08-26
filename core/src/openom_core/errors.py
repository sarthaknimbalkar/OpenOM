# SPDX-License-Identifier: MIT
"""Error/finding types and stable codes (spec §H, §I [OM-MCP-004])."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Severity = Literal["error", "warning", "info"]

# Transport/parse-layer I/O rejection codes (§I [OM-MCP-004]).
IO_DUPKEY = "OM-IO-DUPKEY"
IO_BADUTF8 = "OM-IO-BADUTF8"
IO_NUMRANGE = "OM-IO-NUMRANGE"
IO_BOMB = "OM-IO-BOMB"
IO_STRUCTURE = "OM-IO-STRUCTURE"  # top-level not an object, or nesting too deep


class CanonicalizationError(Exception):
    """Raised when a payload cannot be canonicalized (§C preprocessing failures)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class PayloadTooLargeError(Exception):
    """Payload exceeds the decompressed-size cap (§J [OM-SEC-002] / OM-IO-BOMB)."""

    def __init__(self, size: int, limit: int) -> None:
        super().__init__(f"{IO_BOMB}: payload {size} bytes exceeds cap {limit}")
        self.code = IO_BOMB


class SignedEmbedError(Exception):
    """The signature-preserving incremental embed cannot be performed safely on this signed PDF
    ([OM-EMB-021]) - e.g. its xref had to be rebuilt on open, or the append did not preserve the
    signed byte prefix. A clean typed refusal (embed via a full rewrite, or use a different tool)
    is correct where silently shipping an invalidated signature would be catastrophic."""

    def __init__(self, message: str) -> None:
        super().__init__(f"OM-EMB-021: {message}")
        self.code = "OM-EMB-021"


IO_ENCRYPTED = "OM-IO-011"  # password-protected PDF: can't be opened to read/inspect/extract


class EncryptedPdfError(Exception):
    """A password-protected PDF (real user password) cannot be opened to read/inspect/extract
    ([OM-IO-011]). Distinct from the empty-user-password *permission* encryption the author path
    decrypts: this one needs a password we don't have - a clean typed refusal, not a crash."""

    def __init__(self, message: str = "password-protected PDF (a password is required to open it)"):
        super().__init__(message)  # code is carried in .code; callers prefix it once
        self.code = IO_ENCRYPTED


@dataclass(frozen=True)
class Finding:
    """A single validation result (spec §H [OM-ERR-001])."""

    code: str
    severity: Severity
    path: str
    message: str
    expected: Any | None = None
    actual: Any | None = None
    #: Back-reference to the spec requirement this finding enforces (§H.1 [OM-ERR-008]).
    requirement: str | None = None
