"""Shared test fixtures.

Real OMs live in the git-ignored ``OMs/`` corpus (191 MB, confidential). Tests that need
them load via :func:`load_om` and ``pytest.skip`` cleanly when the corpus is absent, so the
suite still runs on a fresh clone / in CI without the private fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

OMS_DIR = Path(__file__).resolve().parents[2] / "OMs"
REPO_ROOT = Path(__file__).resolve().parents[2]


def pytest_addoption(parser: pytest.Parser) -> None:
    """--corpus <dir> selects the seeded-defect corpus for the [OM-DoD-002] gate."""
    parser.addoption(
        "--corpus",
        action="store",
        default="fixtures/seeded_defects",
        help="Path to the seeded-defect corpus (dir containing manifest.json) for the M1.x gate.",
    )


@pytest.fixture
def corpus_dir(request: pytest.FixtureRequest) -> Path:
    raw = Path(request.config.getoption("--corpus"))
    return raw if raw.is_absolute() else REPO_ROOT / raw

# The M1 fixture matrix (2026-08-16 corpus characterization).
NATIVE_OM = "O'Reilly Auto Parts/O'Reilly Auto Parts - Statesboro, GA - 15 Yr NN with 6% Inc.pdf"
HYBRID_OM = "Family Dollar/Family Dollar - East Camp Dallas, TX.pdf"  # the CMYK doc
# A genuinely scanned (image-only, ~0.14 text coverage) OM in the corpus — real scanned proof.
SCANNED_OM = (
    "O'Reilly Auto Parts/O'Reilly Auto Parts - Marietta, GA - SUPER HUB - "
    "14,400 Square Feet - All Brick - Outstanding Location - 15 Year NN Lease.pdf"
)


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


@pytest.fixture
def scanned_om() -> bytes:
    return load_om(SCANNED_OM)
