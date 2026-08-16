# SPDX-License-Identifier: MIT
"""Principal identity for per-principal rate limits/quotas on the hosted transport.

Pluggable and auth-optional: an ``Authorization: Bearer <token>`` names a principal (the Vervelio
public instance issues keys); otherwise the client IP is the principal (self-host needs no auth).
The token is hashed, never echoed, so a principal string is safe to log.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping


def extract_principal(headers: Mapping[str, str], client_ip: str) -> str:
    """Return ``key:<hash>`` for a Bearer token, else ``ip:<client_ip>``. Header lookup is
    case-insensitive."""
    auth = next((v for k, v in headers.items() if k.lower() == "authorization"), "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return "key:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    return f"ip:{client_ip}"
