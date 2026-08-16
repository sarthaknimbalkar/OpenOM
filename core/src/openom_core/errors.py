"""Error/finding types and stable codes (spec §H, §I [OM-MCP-004])."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Severity = Literal["error", "warning", "info"]

# Transport/parse-layer I/O rejection codes (§I [OM-MCP-004]).
IO_DUPKEY = "OM-IO-DUPKEY"
IO_BADUTF8 = "OM-IO-BADUTF8"
IO_NUMRANGE = "OM-IO-NUMRANGE"


class CanonicalizationError(Exception):
    """Raised when a payload cannot be canonicalized (§C preprocessing failures)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class Finding:
    """A single validation result (spec §H [OM-ERR-001])."""

    code: str
    severity: Severity
    path: str
    message: str
    expected: Any | None = None
    actual: Any | None = None
