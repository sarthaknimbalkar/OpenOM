r"""Task 2: canonicalization keystone (spec section C).

Oracle is real, not the spec's worked-example hashes: each test asserts the exact canonical
bytes (hand-verifiable) and a SHA-256 computed in-test over those same bytes, so a one-byte
divergence fails loudly. The source file is pure ASCII: NFC/NFD strings are derived with
``unicodedata`` from ``\u`` escapes, so nothing depends on the file's encoding.
"""

from __future__ import annotations

import hashlib
import unicodedata

import pytest

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
