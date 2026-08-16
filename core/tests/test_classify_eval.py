"""Task 8 peak: a labeled classifier eval (confusion matrix) that runs in CI, plus confidence
and sampling checks. Real-corpus threshold tuning is a local exercise (see
core/scripts/characterize_corpus.py); this gate proves the classifier on known-label fixtures.
"""

from __future__ import annotations

from _make_scan import make_hybrid_pdf, make_scanned, make_text_pdf
from openom_core.inspect import _sample_indices, classification_confidence, inspect


def test_classifier_confusion_matrix_is_diagonal() -> None:
    cases = {
        "native": make_text_pdf(),
        "scanned": make_scanned(make_text_pdf()),
        "hybrid": make_hybrid_pdf(),
    }
    confusion: dict[tuple[str, str], int] = {}
    for true_label, pdf in cases.items():
        predicted = inspect(pdf)["class"]
        confusion[(true_label, predicted)] = confusion.get((true_label, predicted), 0) + 1
    # Perfect diagonal: each label predicted correctly, nothing off-diagonal.
    for true_label in cases:
        assert confusion.get((true_label, true_label)) == 1, f"misclassified: {confusion}"


def test_confidence_high_for_clear_cases() -> None:
    assert inspect(make_text_pdf())["classConfidence"] > 0.5
    assert inspect(make_scanned(make_text_pdf()))["classConfidence"] > 0.5
    assert inspect(make_hybrid_pdf())["classConfidence"] > 0.3


def test_confidence_bounds_and_boundary() -> None:
    # On a threshold, confidence collapses toward 0; deep in a region it approaches 1.
    assert classification_confidence("scanned", 0.20, 0.0, 0.0) == 0.0  # exactly at boundary
    assert classification_confidence("scanned", 0.0, 0.0, 0.0) == 1.0  # zero text: certain
    assert 0.0 <= classification_confidence("hybrid", 0.5, 0.6, 1.0) <= 1.0


def test_sample_indices_spread_across_document() -> None:
    assert _sample_indices(5, 12) == [0, 1, 2, 3, 4]  # fewer pages than cap -> all
    idx = _sample_indices(100, 12)
    assert len(idx) == 12
    assert idx[0] == 0 and idx[-1] == 99  # spans the whole doc, not just the first 12
