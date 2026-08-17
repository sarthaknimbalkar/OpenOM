# SPDX-License-Identifier: MIT
"""Blob storage for the hosted transport (spec §K, [OM-SEC-006/013], Q4 retention).

Uploaded/produced PDFs live as short-lived blobs (≤24h TTL + delete-on-completion). ``BlobStore``
is the interface; ``LocalBlobStore`` (tmpdir + an injected clock) proves the TTL/delete/authz
semantics offline for the gate. ``S3BlobStore`` (the R2 adapter, Task 8) implements the same
interface for production. Zero inference, zero network in this module's tested path.
"""

from __future__ import annotations

import secrets
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .tools import ToolError


def new_blob_id() -> str:
    """An unguessable blob id (≥128 bits of entropy, URL-safe) ([OM-SEC-013])."""
    return secrets.token_urlsafe(32)


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat()


class BlobStore(ABC):
    """Single-tenant, TTL-bounded blob storage keyed by an unguessable ``blobId``."""

    @abstractmethod
    def create_upload(self, principal: str) -> dict[str, str]:
        """Reserve a blob and return ``{blobId, presignedPut, expiresAt}`` for a client upload."""

    @abstractmethod
    def get(self, blob_id: str, principal: str) -> bytes:
        """Return the blob bytes, or raise OM-IO-006 (missing/expired) / OM-IO-007 (authz)."""

    @abstractmethod
    def put_result(self, data: bytes, principal: str) -> dict[str, str]:
        """Store produced bytes; return ``{blobId, presignedGet, expiresAt}``."""

    @abstractmethod
    def delete(self, blob_id: str) -> None:
        """Remove a blob (idempotent)."""


class LocalBlobStore(BlobStore):
    """Filesystem-backed store for tests/self-host. Presigned URLs are loopback stubs."""

    def __init__(
        self, root: Path, *, ttl_seconds: int = 86400, now: Callable[[], float] = time.time
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds
        self.now = now
        self._meta: dict[str, dict[str, float | str]] = {}

    def _record(self, blob_id: str, principal: str) -> str:
        created = self.now()
        self._meta[blob_id] = {"owner": principal, "created": created}
        return _iso(created + self.ttl)

    def create_upload(self, principal: str) -> dict[str, str]:
        blob_id = new_blob_id()
        expires = self._record(blob_id, principal)
        return {"blobId": blob_id, "presignedPut": f"local://put/{blob_id}", "expiresAt": expires}

    def put_result(self, data: bytes, principal: str) -> dict[str, str]:
        blob_id = new_blob_id()
        expires = self._record(blob_id, principal)
        (self.root / blob_id).write_bytes(data)
        return {"blobId": blob_id, "presignedGet": f"local://get/{blob_id}", "expiresAt": expires}

    def get(self, blob_id: str, principal: str) -> bytes:
        meta = self._meta.get(blob_id)
        path = self.root / blob_id
        if meta is None or not path.exists():
            raise ToolError("OM-IO-006", "blobId not found or expired")
        if self.now() - float(meta["created"]) > self.ttl:  # TTL backstop
            self.delete(blob_id)
            raise ToolError("OM-IO-006", "blobId not found or expired")
        if meta["owner"] != principal:  # existence-then-authz (anti-IDOR, OM-SEC-013)
            raise ToolError("OM-IO-007", "blobId not authorized for this principal")
        return path.read_bytes()

    def delete(self, blob_id: str) -> None:
        self._meta.pop(blob_id, None)
        (self.root / blob_id).unlink(missing_ok=True)


class S3BlobStore(BlobStore):  # pragma: no cover - integration-tested via MinIO/R2 (#53)
    """R2/S3 adapter with **server-bound ownership** (#50). Ownership is recorded by a companion
    ``_owners/<blobId>`` object that ONLY this server writes — never derived from client-supplied
    object metadata — so a presigned PUT (which can write only the data object) cannot forge or
    omit ownership. ``get`` reads the server-written owner for authz; TTL is enforced both by a
    ≤24h bucket lifecycle rule and from the object's ``LastModified``. boto3 is an optional extra;
    inject ``client`` for tests. authz/TTL semantics match ``LocalBlobStore``.
    """

    def __init__(
        self, *, bucket: str, endpoint_url: str = "", access_key: str = "", secret_key: str = "",
        ttl_seconds: int = 86400, client: Any = None,
    ) -> None:
        self.bucket = bucket
        self.ttl = ttl_seconds
        self.s3 = client if client is not None else self._make_client(
            endpoint_url, access_key, secret_key
        )

    @staticmethod
    def _make_client(endpoint_url: str, access_key: str, secret_key: str) -> Any:
        import boto3  # type: ignore[import-not-found,import-untyped]

        return boto3.client(
            "s3", endpoint_url=endpoint_url,
            aws_access_key_id=access_key, aws_secret_access_key=secret_key,
        )

    def _expires(self) -> str:
        return _iso(time.time() + self.ttl)

    @staticmethod
    def _owner_key(blob_id: str) -> str:
        return f"_owners/{blob_id}"

    def _bind_owner(self, blob_id: str, principal: str) -> None:
        # Server-written, not client-controlled: the presigned PUT covers only the data key.
        self.s3.put_object(
            Bucket=self.bucket, Key=self._owner_key(blob_id), Body=principal.encode()
        )

    def create_upload(self, principal: str) -> dict[str, str]:
        blob_id = new_blob_id()
        self._bind_owner(blob_id, principal)
        url = self.s3.generate_presigned_url(
            "put_object", Params={"Bucket": self.bucket, "Key": blob_id},
            ExpiresIn=min(self.ttl, 3600),
        )
        return {"blobId": blob_id, "presignedPut": url, "expiresAt": self._expires()}

    def put_result(self, data: bytes, principal: str) -> dict[str, str]:
        blob_id = new_blob_id()
        self._bind_owner(blob_id, principal)
        self.s3.put_object(Bucket=self.bucket, Key=blob_id, Body=data)
        url = self.s3.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": blob_id},
            ExpiresIn=min(self.ttl, 3600),
        )
        return {"blobId": blob_id, "presignedGet": url, "expiresAt": self._expires()}

    def get(self, blob_id: str, principal: str) -> bytes:
        from botocore.exceptions import ClientError  # type: ignore[import-not-found,import-untyped]

        try:  # authz first, from the server-written owner record (anti-IDOR, anti-forge)
            owner = self.s3.get_object(Bucket=self.bucket, Key=self._owner_key(blob_id))
        except ClientError as exc:
            raise ToolError("OM-IO-006", "blobId not found or expired") from exc
        if owner["Body"].read().decode() != principal:
            raise ToolError("OM-IO-007", "blobId not authorized for this principal")
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=blob_id)
        except ClientError as exc:
            raise ToolError("OM-IO-006", "blobId not found or expired") from exc
        if time.time() - obj["LastModified"].timestamp() > self.ttl:
            self.delete(blob_id)
            raise ToolError("OM-IO-006", "blobId not found or expired")
        body: bytes = obj["Body"].read()
        return body

    def delete(self, blob_id: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=blob_id)
        self.s3.delete_object(Bucket=self.bucket, Key=self._owner_key(blob_id))
