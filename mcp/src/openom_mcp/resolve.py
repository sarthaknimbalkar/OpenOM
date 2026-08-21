# SPDX-License-Identifier: MIT
"""PdfRef → bytes resolution under the transport policy (spec §I, §6d).

A ``PdfRef`` is exactly one of ``{path}`` / ``{url}`` / ``{blobId}``. On **stdio** only ``path`` is
allowed (url/blobId → OM-IO-008). On **http** ``path`` is rejected (no client filesystem, §6d) and
``url``/``blobId`` are resolved via the injected SafeFetcher / BlobStore. The deterministic tool
bodies are unchanged - only how they obtain the input bytes.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from .blobstore import BlobStore
from .fetch import SafeFetcher
from .tools import ToolError

_KEYS = ("path", "url", "blobId")


class PdfResolver:
    def __init__(
        self,
        *,
        transport: Literal["stdio", "http"],
        fetcher: SafeFetcher | None = None,
        blobstore: BlobStore | None = None,
    ) -> None:
        self.transport = transport
        self.fetcher = fetcher
        self.blobstore = blobstore

    def resolve(self, ref: Any, principal: str | None = None) -> bytes:
        if not isinstance(ref, Mapping):
            raise ToolError("OM-IO-008", "pdf must be a PdfRef object (one of path/url/blobId)")
        present = [k for k in _KEYS if k in ref]
        if len(present) != 1:
            raise ToolError("OM-IO-008", "PdfRef must have exactly one of path/url/blobId")
        key = present[0]

        if key == "path":
            if self.transport == "http":
                raise ToolError("OM-IO-008", "path is not accepted on the hosted transport")
            try:
                return Path(ref["path"]).read_bytes()
            except (FileNotFoundError, IsADirectoryError, PermissionError) as exc:
                raise ToolError("OM-IO-010", f"cannot read PDF at path: {exc}") from exc

        if key == "url":
            if self.transport != "http" or self.fetcher is None:
                raise ToolError("OM-IO-008", "url needs the hosted transport")
            return self.fetcher.get(str(ref["url"]))

        # key == "blobId"
        if self.transport != "http" or self.blobstore is None:
            raise ToolError("OM-IO-008", "blobId needs the hosted transport")
        return self.blobstore.get(str(ref["blobId"]), principal or "")
