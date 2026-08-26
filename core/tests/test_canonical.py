r"""Task 2: canonicalization keystone (spec section C).

Oracle is real, not the spec's worked-example hashes: each test asserts the exact canonical
bytes (hand-verifiable) and a SHA-256 computed in-test over those same bytes, so a one-byte
divergence fails loudly. The source file is pure ASCII: NFC/NFD strings are derived with
``unicodedata`` from ``\u`` escapes, so nothing depends on the file's encoding.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from openom_core.canonical import canonicalize, hash_bytes, payload_hash, strip_signature
from openom_core.errors import CanonicalizationError

NFC_CAFE = unicodedata.normalize("NFC", "café")   # "caf" + e-acute (one code point)
NFD_CAFE = unicodedata.normalize("NFD", "café")   # "caf" + e + combining acute
EURO = "€"


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def test_nfc_literal_utf8_no_ascii_escape() -> None:
    nfc = {"tenantEntity": NFC_CAFE}
    data = canonicalize(nfc)
    assert data == b'{"tenantEntity":"caf\xc3\xa9"}'  # literal UTF-8 c3 a9
    assert payload_hash(nfc) == _sha(data)


def test_nfd_input_normalizes_to_nfc_output() -> None:
    assert canonicalize({"tenantEntity": NFD_CAFE}) == b'{"tenantEntity":"caf\xc3\xa9"}'


def test_forward_slash_not_escaped_and_euro_literal() -> None:
    data = canonicalize({"x": "a/b" + EURO})  # euro sign -> e2 82 ac
    assert data == b'{"x":"a/b\xe2\x82\xac"}'


def test_key_sorting_deterministic() -> None:
    a = canonicalize({"b": 1, "a": 2})
    b = canonicalize({"a": 2, "b": 1})
    assert a == b == b'{"a":2,"b":1}'


def test_number_normalization() -> None:
    assert canonicalize({"n": 1850000}) == b'{"n":1850000}'
    assert canonicalize({"n": 1850000.0}) == b'{"n":1850000}'
    assert canonicalize({"r": 12.70}) == b'{"r":12.7}'
    assert canonicalize({"c": 0.0625}) == b'{"c":0.0625}'


def test_safe_integer_rejected() -> None:
    with pytest.raises(CanonicalizationError) as ei:
        canonicalize({"n": 9007199254740993})  # 2^53 + 1
    assert ei.value.code == "OM-IO-NUMRANGE"


def test_non_finite_rejected() -> None:
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(CanonicalizationError) as ei:
            canonicalize({"n": bad})
        assert ei.value.code == "OM-IO-NUMRANGE"


def test_duplicate_key_after_nfc_rejected() -> None:
    payload = {NFC_CAFE: 1, NFD_CAFE: 2}
    assert len(payload) == 2  # distinct code-point sequences before normalization
    with pytest.raises(CanonicalizationError) as ei:
        canonicalize(payload)
    assert ei.value.code == "OM-IO-DUPKEY"


def test_signature_excluded_from_hash() -> None:
    base = {"specVersion": "0.1", "meta": {"supersedes": None}}
    with_sig = {"specVersion": "0.1", "meta": {"supersedes": None, "signature": None}}
    assert payload_hash(base) == payload_hash(with_sig)
    assert "signature" not in strip_signature(with_sig)["meta"]


def test_hash_bytes_matches_manual() -> None:
    data = b'{"a":1}'
    assert hash_bytes(data) == _sha(data)


# --- Boundary / edge cases (backlog §2) -------------------------------------------------

def test_boundary_numbers() -> None:
    # ES-number formatting at the thresholds a naive serializer gets wrong.
    assert canonicalize({"n": 1e-7}) == b'{"n":1e-7}'
    assert canonicalize({"n": -0.0}) == b'{"n":0}'  # negative zero -> "0"
    assert canonicalize({"n": 2**53 - 1}) == b'{"n":9007199254740991}'  # max safe int
    for bad in (1e21, 2**53, -(2**53)):  # 1e21's integer value is not safely representable
        with pytest.raises(CanonicalizationError) as ei:
            canonicalize({"n": bad})
        assert ei.value.code == "OM-IO-NUMRANGE"


def test_top_level_must_be_object() -> None:
    for bad in ([1, 2], "x", 5, None):
        with pytest.raises(CanonicalizationError) as ei:
            canonicalize(bad)  # type: ignore[arg-type]
        assert ei.value.code == "OM-IO-STRUCTURE"


def test_unpaired_surrogate_rejected() -> None:
    with pytest.raises(CanonicalizationError) as ei:
        canonicalize({"tenantEntity": "bad\ud800end"})
    assert ei.value.code == "OM-IO-BADUTF8"


def test_es6_number_formatting_reference() -> None:
    """Independent oracle: assert rfc8785's output equals ES6 Number-to-String, hand-derived
    from the ECMAScript rules (§C [OM-CANON-011]) - not circularly from rfc8785 itself.

    ES rule: use exponential form when the decimal exponent < -6 or >= 21; otherwise plain.
    All values here are within openOM's safe-number policy (|int value| <= 2^53-1).
    """
    # A list, not a dict: 0.0 and -0.0 compare equal and would collapse into one dict key.
    cases: list[tuple[float, bytes]] = [
        (0.0, b"0"),
        (-0.0, b"0"),  # negative zero collapses to "0"
        (1.0, b"1"),
        (1.5, b"1.5"),
        (12.70, b"12.7"),  # trailing zero dropped
        (0.0625, b"0.0625"),
        (100.0, b"100"),
        (1e-6, b"0.000001"),  # exponent -6 -> still plain form
        (1e-7, b"1e-7"),  # exponent -7 -> exponential form (the switch point)
        (5e-324, b"5e-324"),  # smallest positive double (denormal)
        (float(2**53 - 1), b"9007199254740991"),  # max safe integer as a float
    ]
    for value, expected in cases:
        assert canonicalize({"n": value}) == b'{"n":' + expected + b"}", f"failed on {value!r}"


def test_nesting_within_limit_ok() -> None:
    obj: Any = {"leaf": 1}
    for _ in range(50):  # within MAX_DEPTH (64)
        obj = {"child": obj}
    assert canonicalize(obj).startswith(b'{"child":')


def test_nesting_over_limit_rejected() -> None:
    obj: Any = {"leaf": 1}
    for _ in range(100):  # beyond MAX_DEPTH (64) - matches the JS parser's guard
        obj = {"child": obj}
    with pytest.raises(CanonicalizationError) as ei:
        canonicalize(obj)
    assert ei.value.code == "OM-IO-STRUCTURE"


def test_parse_hardened_deep_nesting_is_structured_not_recursionerror() -> None:
    # Pathologically deep raw JSON blows json.loads's stack while BUILDING the object, before the
    # depth check can run - parse_hardened must convert it to OM-IO-STRUCTURE, not a RecursionError.
    from openom_core.canonical import parse_hardened

    raw = "[" * 5000 + "]" * 5000
    with pytest.raises(CanonicalizationError) as ei:
        parse_hardened(raw)
    assert ei.value.code == "OM-IO-STRUCTURE"


# --- Property-based differential invariants (backlog §0 #3, §2) -------------------------
# Random JSON objects: safe numbers, surrogate-free text, bounded depth.

_text = st.text(alphabet=st.characters(codec="utf-8"), max_size=12)
_scalars = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-(2**53 - 1), max_value=2**53 - 1)
    | st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6)
    | _text
)
_json = st.recursive(
    _scalars,
    lambda ch: st.lists(ch, max_size=4) | st.dictionaries(_text, ch, max_size=4),
    max_leaves=15,
)
_objects = st.dictionaries(_text, _json, max_size=5)


@given(_objects)
def test_property_reparse_is_a_fixed_point(obj: dict[str, Any]) -> None:
    """Canonical bytes, parsed and re-canonicalized, are byte-identical (JCS is idempotent)."""
    once = canonicalize(obj)
    assert canonicalize(json.loads(once)) == once


@given(_objects)
def test_property_key_insertion_order_irrelevant(obj: dict[str, Any]) -> None:
    reordered = dict(reversed(list(obj.items())))
    assert canonicalize(reordered) == canonicalize(obj)


@given(_text)
def test_property_nfd_and_nfc_collapse_to_same_bytes(s: str) -> None:
    nfd = unicodedata.normalize("NFD", s)
    nfc = unicodedata.normalize("NFC", s)
    assert canonicalize({"k": nfd}) == canonicalize({"k": nfc})
