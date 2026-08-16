"""Shared test fixtures.

Real OMs live in the git-ignored ``OMs/`` corpus (191 MB, confidential). Tests that need
them load via :func:`load_om` and ``pytest.skip`` cleanly when the corpus is absent, so the
suite still runs on a fresh clone / in CI without the private fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

OMS_DIR = Path(__file__).resolve().parents[2] / "OMs"

# The M1 fixture matrix (2026-08-16 corpus characterization).
NATIVE_OM = "O'Reilly Auto Parts/O'Reilly Auto Parts - Statesboro, GA - 15 Yr NN with 6% Inc.pdf"
HYBRID_OM = "Family Dollar/Family Dollar - East Camp Dallas, TX.pdf"  # the CMYK doc


def load_om(rel: str) -> bytes:
    """Return the bytes of a corpus OM, or skip the test if the corpus is not present."""
    path = OMS_DIR / rel
    if not path.exists():
        pytest.skip(f"corpus file missing (OMs/ not present): {rel}")
    return path.read_bytes()


@pytest.fixture
def native_om() -> bytes:
    return load_om(NATIVE_OM)


@pytest.fixture
def hybrid_om() -> bytes:
    return load_om(HYBRID_OM)
