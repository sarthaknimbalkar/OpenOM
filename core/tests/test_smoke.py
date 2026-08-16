"""Task 1 smoke test: the package imports and the corpus loader works (or skips cleanly)."""

from __future__ import annotations

import openom_core


def test_imports() -> None:
    assert isinstance(openom_core.__version__, str)
    assert openom_core.__version__


def test_corpus_present_or_skipped(native_om: bytes) -> None:
    # Skips cleanly when OMs/ is absent; otherwise confirms it's a real PDF.
    assert native_om[:5] == b"%PDF-"
