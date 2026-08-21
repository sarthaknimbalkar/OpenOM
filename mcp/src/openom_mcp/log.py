# SPDX-License-Identifier: MIT
"""Structured operational logging for the HOSTED MCP transport (#152).

The deterministic core is silent by design, but the M3 hosted server is a network service and needs
diagnosability - request outcomes, rate-limit rejections, SSRF blocks, blob lifecycle. This logs to
stderr as `key=value` events (grep/ship-friendly) confined to the transport/security/blob layers; it
NEVER touches the deterministic tool bodies (the cardinal boundary, §V) and emits NO telemetry off
box (§M - local operational logging, not egress). Level controlled by OPENOM_MCP_LOG
(default INFO); set to a higher level or CRITICAL to quiet it.
"""

from __future__ import annotations

import logging
import os

_LOGGER = "openom.mcp"


def get_logger() -> logging.Logger:
    log = logging.getLogger(_LOGGER)
    if not log.handlers:
        handler = logging.StreamHandler()  # stderr
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s openom.mcp %(message)s"))
        log.addHandler(handler)
        level = os.environ.get("OPENOM_MCP_LOG", "INFO").upper()
        log.setLevel(getattr(logging, level, logging.INFO))
        log.propagate = False
    return log


def event(level: int, name: str, **fields: object) -> None:
    """Emit a `name key=value ...` event; values stringified, None-valued keys dropped."""
    parts = [name]
    for key, value in fields.items():
        if value is not None:
            parts.append(f"{key}={value}")
    get_logger().log(level, " ".join(parts))
