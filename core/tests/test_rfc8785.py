"""#134: independent RFC 8785 (JCS) anchor. The golden vectors and the drift gate are all produced
by gen_vectors.py + canonicalize(), so a shared bug there would make the generator, the vectors, and
the tests all agree on the WRONG bytes. These vectors are authored BY HAND from the RFC 8785 rules
(lexicographic key sort by UTF-16 code unit; minimal string escaping; ECMAScript Number.toString;
array order preserved; NFC non-ASCII emitted raw), so they anchor that canonicalize is CORRECT, not
merely self-consistent. Only cases inside openOM's accepted number range are used (§C rejects the
RFC's extreme-magnitude examples by design)."""

from __future__ import annotations

from openom_core.canonical import canonicalize

# (input, expected canonical text) - hand-derived from RFC 8785.
_VECTORS: list[tuple[dict, str]] = [
    ({"b": 1, "a": 2, "c": 3}, '{"a":2,"b":1,"c":3}'),  # key sort
    ({"z": {"y": 1, "x": 2}}, '{"z":{"x":2,"y":1}}'),  # nested sort
    ({"arr": [3, 1, 2]}, '{"arr":[3,1,2]}'),  # array order preserved
    ({"a": True, "b": False, "c": None}, '{"a":true,"b":false,"c":null}'),  # literals
    ({"s": 'a"b\\c'}, '{"s":"a\\"b\\\\c"}'),  # quote + backslash escaped
    ({"s": "tab\tnl\n"}, '{"s":"tab\\tnl\\n"}'),  # short control escapes
    ({"s": chr(1) + chr(0x1f)}, '{"s":"\\u0001\\u001f"}'),  # other controls -> \u00xx
    ({"s": "é"}, '{"s":"é"}'),  # NFC non-ASCII emitted raw (not \u)
    ({"s": "中文"}, '{"s":"中文"}'),
    ({"n": 4.50}, '{"n":4.5}'),  # ECMAScript Number.toString
    ({"n": 100}, '{"n":100}'),
    ({"n": -0.0}, '{"n":0}'),  # negative zero -> "0"
    ({"n": 0.002}, '{"n":0.002}'),
    ({"n": 2**53 - 1}, '{"n":9007199254740991}'),  # max safe integer
]


def test_canonicalize_matches_hand_authored_rfc8785_vectors() -> None:
    for value, expected in _VECTORS:
        got = canonicalize(value).decode("utf-8")
        assert got == expected, f"canonicalize({value!r}) = {got!r}, expected {expected!r}"
