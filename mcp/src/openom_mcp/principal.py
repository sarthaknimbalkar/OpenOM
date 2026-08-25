# SPDX-License-Identifier: MIT
"""Principal identity for per-principal rate limits/quotas on the hosted transport.

Pluggable and auth-optional: an ``Authorization: Bearer <token>`` names a principal (the Vervelio
public instance issues keys); otherwise the client IP is the principal (self-host needs no auth).
The token is hashed, never echoed, so a principal string is safe to log.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping


def extract_principal(
    headers: Mapping[str, str], client_ip: str, *, trusted_ip_header: str | None = None
) -> str:
    """Return ``key:<hash>`` for a Bearer token, else ``ip:<client_ip>``. Header lookup is
    case-insensitive.

    Behind a reverse proxy or CDN the socket ``client_ip`` is the PROXY's address, identical for
    every request, so an IP-keyed rate limit would put all unauthenticated callers in one bucket.
    When the deployment sets ``trusted_ip_header`` (e.g. ``CF-Connecting-IP`` behind Cloudflare, or
    ``X-Forwarded-For``), the leftmost value of that header is the client IP instead. This is
    OPT-IN and unset by default because a client can forge such a header - only enable it when the
    proxy in front overwrites the header and the origin accepts traffic only from that proxy.
    """
    auth = next((v for k, v in headers.items() if k.lower() == "authorization"), "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return "key:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    ip = client_ip
    if trusted_ip_header:
        fwd = next((v for k, v in headers.items() if k.lower() == trusted_ip_header.lower()), "")
        first = fwd.split(",")[0].strip()
        if first:
            ip = first
    return f"ip:{ip}"
