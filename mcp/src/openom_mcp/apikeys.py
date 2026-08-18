# SPDX-License-Identifier: MIT
"""API-key lifecycle for the hosted transport (#52): issue/verify/rotate/revoke + per-key quota.

Deterministic logic over a pluggable ``KeyStore`` (+ the ``CounterStore`` seam from ratelimit.py for
quota accounting). The hosted deploy binds a real KV/DB + Redis; ``InMemoryKeyStore`` is the
test/self-host impl. No inference — this is the paid instance's access layer over the
same deterministic engine.

Security posture: the plaintext key (``omk_<token>``) is shown EXACTLY ONCE, at issue; only its
SHA-256 hash is ever stored or logged. Verification is hash-lookup + status check; rotation issues a
new key and revokes the old; revocation is immediate. Quota is a per-key volume cap over a window,
distinct from the short-window burst rate limit.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal, Protocol

from .ratelimit import CounterStore
from .tools import ToolError

KEY_PREFIX = "omk_"
KeyStatus = Literal["active", "revoked"]


def hash_key(plaintext: str) -> str:
    """The stored/loggable identifier for a key: its SHA-256 hex. Never store the plaintext."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ApiKeyRecord:
    key_id: str  # public, non-secret handle (safe to show in a dashboard/logs)
    key_hash: str  # sha256(plaintext); the lookup key
    owner: str  # principal that owns the key
    created: float
    status: KeyStatus = "active"
    quota_limit: int = 0  # max calls per quota window; 0 = unlimited
    quota_window_seconds: int = 86_400  # default: per day
    revoked_at: float | None = None


class KeyStore(Protocol):
    """Persistence seam. The hosted deploy backs this with a KV/DB; tests use InMemoryKeyStore."""

    def get_by_hash(self, key_hash: str) -> ApiKeyRecord | None: ...
    def get_by_id(self, key_id: str) -> ApiKeyRecord | None: ...
    def put(self, record: ApiKeyRecord) -> None: ...


class InMemoryKeyStore:
    """Single-process KeyStore for tests / self-host."""

    def __init__(self) -> None:
        self._by_hash: dict[str, ApiKeyRecord] = {}
        self._by_id: dict[str, ApiKeyRecord] = {}

    def get_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        return self._by_hash.get(key_hash)

    def get_by_id(self, key_id: str) -> ApiKeyRecord | None:
        return self._by_id.get(key_id)

    def put(self, record: ApiKeyRecord) -> None:
        self._by_hash[record.key_hash] = record
        self._by_id[record.key_id] = record


class ApiKeyManager:
    """Issue / verify / rotate / revoke API keys and enforce per-key quota."""

    def __init__(
        self,
        store: KeyStore,
        counters: CounterStore,
        *,
        now: Callable[[], float] = time.time,
        rng: Callable[[], str] = lambda: secrets.token_urlsafe(24),
    ) -> None:
        self.store = store
        self.counters = counters
        self.now = now
        self._rng = rng  # injectable for deterministic tests

    def issue(
        self, owner: str, *, quota_limit: int = 0, quota_window_seconds: int = 86_400
    ) -> tuple[str, ApiKeyRecord]:
        """Mint a new key for ``owner``. Returns (plaintext_shown_once, record). Store keeps only
        the hash — the plaintext is unrecoverable after this call."""
        plaintext = KEY_PREFIX + self._rng()
        record = ApiKeyRecord(
            key_id="k_" + secrets.token_hex(8),
            key_hash=hash_key(plaintext),
            owner=owner,
            created=self.now(),
            quota_limit=quota_limit,
            quota_window_seconds=quota_window_seconds,
        )
        self.store.put(record)
        return plaintext, record

    def verify(self, plaintext: str) -> ApiKeyRecord | None:
        """Return the ACTIVE record for a plaintext key, or None (unknown / revoked / malformed)."""
        if not plaintext.startswith(KEY_PREFIX):
            return None
        record = self.store.get_by_hash(hash_key(plaintext))
        if record is None or record.status != "active":
            return None
        return record

    def revoke(self, key_id: str) -> bool:
        """Immediately deactivate a key. Returns True if a key was revoked, False if unknown."""
        record = self.store.get_by_id(key_id)
        if record is None or record.status == "revoked":
            return False
        self.store.put(replace(record, status="revoked", revoked_at=self.now()))
        return True

    def rotate(self, key_id: str) -> tuple[str, ApiKeyRecord] | None:
        """Issue a replacement key for the same owner (same quota policy) and revoke the old one.
        Returns the new (plaintext, record), or None if ``key_id`` is unknown."""
        old = self.store.get_by_id(key_id)
        if old is None:
            return None
        new = self.issue(
            old.owner,
            quota_limit=old.quota_limit,
            quota_window_seconds=old.quota_window_seconds,
        )
        self.revoke(key_id)
        return new

    def check_quota(self, record: ApiKeyRecord) -> None:
        """Count one call against the key's quota window; raise OM-IO-014 when the cap is exceeded.
        A key with ``quota_limit == 0`` is unlimited (only the burst rate limit applies)."""
        if record.quota_limit <= 0:
            return
        window = record.quota_window_seconds
        idx = int(self.now() // window)
        count = self.counters.incr(f"quota:{record.key_id}:{idx}", window)
        if count > record.quota_limit:
            retry = max(1, int(window - (self.now() % window)))
            raise ToolError(
                "OM-IO-014", "quota exceeded", retryable=True, retry_after=retry
            )
