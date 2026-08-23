# SPDX-License-Identifier: MIT
"""Plain-English rendering of validation findings for the terminal, so "all validation errors, haha"
never happens again.

Lives in the CLI, NOT the deterministic core (the core stays a pure library emitting stable codes).
The machine-readable JSON still goes to stdout unchanged; these strings are the friendly stderr
coaching. Every line leads with what to do and keeps the raw code in a trailing parenthetical.
"""

from __future__ import annotations

import re

_FOOTER = (
    "Fix these in your payload and re-run. Starting from scratch? `om init` writes a valid "
    "template. Not a developer? https://openom.app/embed/ builds the payload for you."
)


def _word(w: str) -> str:
    # keep acronyms (PSF, SF, NOI, APN) as-is; lowercase ordinary words (Rate -> rate)
    return w if w.isupper() else w.lower()


def humanize_path(path: str) -> str:
    """'/deal/capRate' -> 'deal > cap rate' (acronyms like PSF/NOI/SF kept uppercase)."""
    parts = [p for p in path.strip("/").split("/") if p]
    out: list[str] = []
    for p in parts:
        if p.isdigit():
            out.append(f"#{int(p) + 1}")
        else:
            words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", p).split(" ")
            out.append(" ".join(_word(w) for w in words))
    return " > ".join(out) or "(payload root)"


def humanize_finding(code: str, path: str, message: str) -> str:
    """One plain-English line for a finding, keyed on the codes a broker actually hits."""
    label = humanize_path(path)
    if code == "OMV-E001" and path == "/deal/capRate":
        return (
            "Cap rate must be a decimal fraction between 0 and 1 - enter 6.25% as 0.0625 "
            "(not 6.25). Fix deal.capRate. (OMV-E001)"
        )
    if code == "OMV-E002":
        return (
            "You set an NOI, so you must also say whether it's 'in-place' or 'pro-forma' "
            "(deal.noiType) and its as-of date (deal.noiAsOfDate). Add both. (OMV-E002)"
        )
    if "currency" in path.lower():
        return f"{label}: currency must be a 3-letter ISO 4217 code like USD. ({code})"
    return f"{label}: {message} ({code})"


def footer() -> str:
    return _FOOTER
