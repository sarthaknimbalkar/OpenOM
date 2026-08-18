# SPDX-License-Identifier: MIT
"""Resource-bounded execution of untrusted-PDF parsing ([OM-SEC-010]).

A network-facing server must not be taken down by a malicious PDF that hangs or exhausts memory in
a C parser (pikepdf/PyMuPDF). ``bounded_call`` runs a parse in a **killable subprocess** with a
wall-clock timeout (a Python thread cannot interrupt a hung C call) and a memory cap (RLIMIT_AS on
POSIX). A timeout maps to ``OM-IO-003`` and any crash or in-child exception — INCLUDING a rejected
memory limit, which is no longer swallowed (#123) — to ``OM-IO-010``, never a server takedown
([OM-SEC-010], [OM-MCP-008]). Off-POSIX the in-process cap is impossible, so the deployment MUST
bound memory (container/cgroup or a Windows Job Object); ``bounded_call`` warns once if it cannot.

The subprocess uses the ``spawn`` context so behavior is identical on POSIX and Windows; the target
must be an importable top-level callable and its args/result must be picklable (true for the core
verbs on ``bytes`` → dict/dataclass/bytes).
"""

from __future__ import annotations

import importlib.util
import multiprocessing as mp
import queue as _queue
import sys
from collections.abc import Callable, Sequence
from typing import Any

from .tools import ToolError

# Whether an in-process address-space cap (RLIMIT_AS) is even possible on this platform. Off-POSIX
# (Windows) the `resource` module is absent, so the memory bound MUST come from the deployment
# (a container/cgroup limit or a Windows Job Object) — see SECURITY.md's threat model (#123/#128).
_RESOURCE_AVAILABLE = importlib.util.find_spec("resource") is not None
_warned_no_rlimit = False


def _apply_memory_limit(memory_bytes: int) -> None:
    """Cap the child's address space (POSIX). Non-POSIX → no-op (deploy must bound memory). A
    setrlimit rejection is NOT swallowed: it propagates so the parse fails loud rather than running
    unbounded while appearing capped (#123)."""
    if not _RESOURCE_AVAILABLE:
        return
    import resource  # type: ignore[import-not-found,unused-ignore]  # POSIX-only

    resource.setrlimit(  # type: ignore[attr-defined,unused-ignore]  # may raise → reported as OM-IO-010
        resource.RLIMIT_AS,  # type: ignore[attr-defined,unused-ignore]
        (memory_bytes, memory_bytes),
    )


def _worker(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    memory_bytes: int | None,
    q: Any,
) -> None:
    try:
        if memory_bytes is not None:
            _apply_memory_limit(memory_bytes)  # ValueError/OSError propagate → reported as a crash
        q.put(("ok", func(*args, **kwargs)))
    except BaseException as exc:  # noqa: BLE001 - report MemoryError/parser/limit errors as a crash
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
    global _warned_no_rlimit
    mem = memory_mb * 1024 * 1024 if memory_mb else None
    if mem is not None and not _RESOURCE_AVAILABLE and not _warned_no_rlimit:
        _warned_no_rlimit = True
        sys.stderr.write(
            "openom: RLIMIT_AS unavailable on this platform; the untrusted-PDF memory cap MUST be "
            "enforced by the deployment (container/cgroup limit or Windows Job Object).\n"
        )
    ctx = mp.get_context("spawn")
    q: Any = ctx.Queue()
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
