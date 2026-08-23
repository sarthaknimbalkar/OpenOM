"""[Mi22] Python summarize_deal parity with /js summarizeDeal + [Mi18] hardened read parse."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openom_core import summarize_deal
from openom_core.canonical import parse_hardened
from openom_core.errors import CanonicalizationError

SAMPLES = Path(__file__).resolve().parents[2] / "spec" / "samples"


def test_summarize_formats_like_the_js_view() -> None:
    p = json.loads((SAMPLES / "valid-stnl.json").read_text(encoding="utf-8"))
    s = summarize_deal(p)
    assert s["capRate"] == 0.0625 and s["capRateText"] == "6.25%"  # raw + formatted
    assert s["askingPriceText"] == "$1,850,000"  # USD Intl parity
    assert s["noiText"] == "$115,625"
    assert s["currency"] == "USD"  # default when absent
    assert s["noiType"] == "in-place"


def test_summarize_is_null_safe_on_an_empty_payload() -> None:
    s = summarize_deal({})
    assert s["askingPrice"] is None and s["askingPriceText"] is None
    assert s["capRateText"] is None
    assert s["currency"] == "USD"


def test_parse_hardened_rejects_duplicate_keys() -> None:
    with pytest.raises(CanonicalizationError):
        parse_hardened(b'{"a": 1, "a": 2}')


def test_parse_hardened_rejects_over_deep_nesting() -> None:
    deep = "[" * 70 + "]" * 70  # exceeds MAX_DEPTH (64)
    with pytest.raises(CanonicalizationError):
        parse_hardened(deep)


def test_parse_hardened_accepts_a_normal_payload() -> None:
    assert parse_hardened(b'{"a": {"b": [1, 2, 3]}}') == {"a": {"b": [1, 2, 3]}}
