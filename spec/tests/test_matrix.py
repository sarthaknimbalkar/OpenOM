"""M1 fixture-matrix tool ([OM-DoD-001](e), §B.3). The pathology axis is synthetic (CI); the
producer axis needs the confidential corpus (local, exercised via `python -m spec.matrix
--assert-full`)."""

from __future__ import annotations

from spec import matrix


def test_every_pathology_fixture_builds() -> None:
    built = matrix.build_pathologies()
    assert set(built) == set(matrix.PATHOLOGIES)
    for name, data in built.items():
        assert data, f"pathology {name} produced no fixture"


def test_synthetic_axis_is_full() -> None:
    # Pathology axis only (no corpus) - the CI-checkable half of the matrix gate.
    assert matrix.assert_matrix(require_corpus=False) == []


def test_hash_mismatch_fixture_is_actually_mismatched() -> None:
    from openom_core.embed import read

    result = read(matrix.build_pathologies()["hash-mismatch"])
    assert result.present is True
    assert result.hash_valid is False  # the tampered marker must fail integrity
