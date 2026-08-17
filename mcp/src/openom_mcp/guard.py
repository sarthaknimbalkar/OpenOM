# SPDX-License-Identifier: MIT
"""Resource-bounded execution of untrusted-PDF parsing ([OM-SEC-010]).

A network-facing server must not be taken down by a malicious PDF that hangs or exhausts memory in
a C parser (pikepdf/PyMuPDF). ``bounded_call`` runs a parse in a **killable subprocess** with a
wall-clock timeout (a Python thread cannot interrupt a hung C call) and a best-effort memory cap
(RLIMIT_AS on POSIX; skipped where unsupported). A timeout maps to ``OM-IO-003`` and any crash or
in-child exception to ``OM-IO-010`` — never a server takedown ([OM-SEC-010], [OM-MCP-008]).

The subprocess uses the ``spawn`` context so behavior is identical on POSIX and Windows; the target
must be an importable top-level callable and its args/result must be picklable (true for the core
verbs on ``bytes`` → dict/dataclass/bytes).
"""

from __future__ import annotations

import multiprocessing as mp
import queue as _queue
from collections.abc import Callable, Sequence
from typing import Any

from .tools import ToolError


def _worker(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    memory_bytes: int | None,
    q: Any,
) -> None:
    try:
        if memory_bytes is not None:
            try:  # POSIX only; a no-op elsewhere
                import resource  # type: ignore[import-not-found,unused-ignore]  # POSIX-only

                lim = resource.RLIMIT_AS  # type: ignore[attr-defined,unused-ignore]
                resource.setrlimit(lim, (memory_bytes, memory_bytes))  # type: ignore[attr-defined,unused-ignore]
            except (ImportError, ValueError, OSError):
                pass
        q.put(("ok", func(*args, **kwargs)))
    except BaseException as exc:  # noqa: BLE001 - report MemoryError/parser errors as a crash
        q.put(("err", f"{type(exc).__name__}: {exc}"))


def bounded_call(
    func: Callable[..., Any],
    args: Sequence[Any] = (),
    *,
    kwargs: dict[str, Any] | None = None,
    timeout: float,
    memory_mb: int | None = None,
) -> Any:
    """Run ``func(*args, **kwargs)`` in a killable subprocess (timeout → 003, crash → 010)."""
    ctx = mp.get_context("spawn")
    q: Any = ctx.Queue()
    mem = memory_mb * 1024 * 1024 if memory_mb else None
    proc = ctx.Process(target=_worker, args=(func, tuple(args), dict(kwargs or {}), mem, q))
    proc.start()
    proc.join(timeout)
    if proc.is_alive():
        proc.terminate()
        proc.join()
        raise ToolError("OM-IO-003", f"operation exceeded {timeout}s", retryable=True)
    try:
        status, payload = q.get(timeout=1.0)
    except (_queue.Empty, EOFError, OSError) as exc:  # hard crash: no result on the queue
        raise ToolError("OM-IO-010", f"parser crashed (exit {proc.exitcode})") from exc
    if status == "err":
        raise ToolError("OM-IO-010", f"parser failed: {payload}")
    return payload
