# SPDX-License-Identifier: MIT
"""Paid inference-extraction boundary (seam only) - spec §6a cardinal rule, §15.1.

Hosted inference extraction is a SEPARATE commercial service, never part of the open server. This
module is only the seam the commercial service plugs into: the ``InferenceExtractor`` Protocol and
a ``payment_required()`` helper. The open distribution registers NO extraction tool and imports NO
model client - the ``boundary`` CI job (pip-freeze) and ``test_boundary.py`` (module scan) both
enforce that. Nothing here performs inference.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .tools import ToolError


@runtime_checkable
class InferenceExtractor(Protocol):
    """Implemented ONLY by the separate commercial extraction service - never in the open server."""

    def extract(self, pdf_bytes: bytes) -> dict[str, Any]: ...


def payment_required() -> ToolError:
    """The 402 seam a hosted deployment would return if inference extraction were requested but the
    principal is not entitled. Never raised by the deterministic tools."""
    return ToolError(
        "OM-IO-402", "hosted inference extraction is a separate commercial service", retryable=False
    )
