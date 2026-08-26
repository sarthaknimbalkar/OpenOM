"""Cover the Buildout->openOM mapper helper branches (pure, deterministic)."""

from __future__ import annotations

from openom_cli.buildout import (
    _int,
    _iso_date,
    _lease_type,
    _months_between,
    _num,
    _pct_to_fraction,
    _state_code,
)


def test_num_drops_non_finite() -> None:
    # A non-finite cell (1e400/inf/nan) must be omitted, not propagated - mirrors the JS connector's
    # Number.isFinite guard and stops _int() raising OverflowError (which aborted the whole batch).
    assert _num("1e400") is None
    assert _num("inf") is None
    assert _num("nan") is None
    assert _int("1e400") is None


def test_num_and_pct() -> None:
    assert _num("1,850,000") == 1850000.0
    assert _num("nope") is None
    assert _num(None) is None
    assert _pct_to_fraction("6.25") == 0.0625
    assert _pct_to_fraction(None) is None


def test_iso_date_variants() -> None:
    assert _iso_date("10/1/2026") == "2026-10-01"
    assert _iso_date("") is None
    assert _iso_date("2026-10-01") is None  # not M/D/Y
    assert _iso_date("13/1/2026") is None  # bad month
    assert _iso_date("a/b/c") is None


def test_state_code() -> None:
    assert _state_code("GA - Georgia") == "GA"
    assert _state_code("GA") == "GA"
    assert _state_code("Georgia") is None
    assert _state_code(None) is None


def test_lease_type() -> None:
    assert _lease_type("Absolute NNN") == "NNN"
    assert _lease_type("NN lease") == "NN"
    assert _lease_type("Gross") == "gross"
    assert _lease_type("Custom") == "Custom"
    assert _lease_type(None) is None


def test_months_between() -> None:
    assert _months_between("2021-06-01", "2031-06-01") == 120
    assert _months_between("2021-06-15", "2021-07-10") == 0  # partial trailing month
    assert _months_between(None, "2031-06-01") is None
    assert _months_between("bad", "2031-06-01") is None
    assert _months_between("2031-06-01", "2021-06-01") is None  # negative
