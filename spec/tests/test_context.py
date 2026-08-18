"""M2 (#13): the JSON-LD `@context` is the published vocabulary — the second half of "the spec is
the product". These tests keep the vocabulary provably complete and drift-locked to the schema,
deterministically and offline (no network to schema.org):

  * completeness vs the schema  — every property name the JSON Schema defines has an IRI mapping;
  * completeness vs the wire    — every term a conformant sample uses is mapped;
  * structural soundness        — every mapping resolves to a declared prefix (om/schema/xsd).

A term added to the schema without a vocabulary mapping (or vice versa) fails here, so the two
halves of the contract cannot silently diverge.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SPEC = Path(__file__).resolve().parents[1]
CONTEXT_FILE = SPEC / "context" / "openom-0.1.jsonld"
SCHEMA_FILE = SPEC / "om-0.1.schema.json"

# Forward-compat samples deliberately carry unknown terms to prove tolerance ([OM-VER-003]);
# those terms are NOT part of the 0.1 vocabulary, so they are excluded from the wire check.
_FORWARD_COMPAT_TERMS = {"addedInAFutureVersion", "futureUnknownField"}
_PREFIXES = {"om", "schema", "xsd"}


def _context_map() -> dict[str, Any]:
    doc = json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
    return doc["@context"]


def _context_terms() -> set[str]:
    return {k for k in _context_map() if not k.startswith("@") and k not in _PREFIXES}


def _schema_property_names(node: Any, acc: set[str]) -> None:
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            acc.update(k for k in props if not k.startswith("@"))
        for value in node.values():
            _schema_property_names(value, acc)
    elif isinstance(node, list):
        for item in node:
            _schema_property_names(item, acc)


def _payload_terms(payload: Any, acc: set[str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if not key.startswith("@"):
                acc.add(key)
            _payload_terms(value, acc)
    elif isinstance(payload, list):
        for item in payload:
            _payload_terms(item, acc)


def test_context_file_is_valid_and_wired() -> None:
    ctx = _context_map()
    assert ctx.get("@version") == 1.1
    for prefix in _PREFIXES:
        assert prefix in ctx and isinstance(ctx[prefix], str) and ctx[prefix].endswith(("#", "/"))


def test_every_mapping_resolves_to_a_declared_prefix() -> None:
    ctx = _context_map()
    bad: dict[str, Any] = {}
    for term, mapping in ctx.items():
        if term.startswith("@") or term in _PREFIXES:
            continue
        iri = mapping["@id"] if isinstance(mapping, dict) else mapping
        if not isinstance(iri, str) or iri.split(":", 1)[0] not in _PREFIXES:
            bad[term] = mapping
        if isinstance(mapping, dict) and "@type" in mapping:
            at = mapping["@type"]
            # A coercion is either a JSON-LD keyword (@id, @vocab) or a prefixed datatype IRI.
            if not (at.startswith("@") or at.split(":", 1)[0] in _PREFIXES):
                bad[term] = mapping
    assert not bad, f"mappings not resolving to a declared prefix: {bad}"


def test_vocabulary_covers_every_schema_property() -> None:
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    schema_terms: set[str] = set()
    _schema_property_names(schema, schema_terms)
    missing = schema_terms - _context_terms()
    assert not missing, f"schema properties with no vocabulary mapping: {sorted(missing)}"


def test_vocabulary_covers_every_conformant_sample_term() -> None:
    terms = _context_terms()
    for name in ("valid-stnl", "valid-proforma"):
        payload = json.loads((SPEC / "samples" / f"{name}.json").read_text(encoding="utf-8"))
        used: set[str] = set()
        _payload_terms(payload, used)
        missing = used - terms - _FORWARD_COMPAT_TERMS
        assert not missing, f"{name}: terms used on the wire but not in the vocabulary: {missing}"


# [OM-LD-004] #111: every non-string term MUST carry an explicit datatype coercion, else a JSON-LD
# consumer can't tell a decimal from a string. Derive the expectation from the schema so the context
# cannot silently drift back to bare numeric/boolean/date terms.
_TYPE_TO_XSD = {
    "number": {"xsd:decimal", "xsd:double"},  # xsd:double allowed for geo coords (schema.org norm)
    "integer": {"xsd:integer"},
    "boolean": {"xsd:boolean"},
}


def _schema_typed_terms(node: Any, acc: dict[str, set[str]]) -> None:
    """Map each property name → the set of scalar JSON types (+ 'date') the schema declares for it,
    across oneOf/anyOf/allOf branches."""

    def note(name: str, d: dict[str, Any]) -> None:
        t = d.get("type")
        if t == "string" and d.get("format") == "date":
            acc.setdefault(name, set()).add("date")
        elif isinstance(t, str) and t in ("number", "integer", "boolean"):
            acc.setdefault(name, set()).add(t)
        for branch in ("oneOf", "anyOf", "allOf"):
            for b in d.get(branch, []) or []:
                if isinstance(b, dict):
                    note(name, b)

    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            for name, d in props.items():
                if not name.startswith("@") and isinstance(d, dict):
                    acc.setdefault(name, set())
                    note(name, d)
        for value in node.values():
            _schema_typed_terms(value, acc)
    elif isinstance(node, list):
        for item in node:
            _schema_typed_terms(item, acc)


def test_typed_terms_carry_matching_datatype_coercion() -> None:
    """[OM-LD-004]: unambiguously number/integer/boolean/date schema terms must be coerced in the
    context (mixed oneOf terms like abatement are skipped — they cannot carry a single @type)."""
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    typed: dict[str, set[str]] = {}
    _schema_typed_terms(schema, typed)
    ctx = _context_map()
    bad: dict[str, Any] = {}
    for name, kinds in typed.items():
        if len(kinds) != 1:
            continue  # untyped or mixed-type (ambiguous) — no single coercion applies
        (kind,) = tuple(kinds)
        expected = {"xsd:date"} if kind == "date" else _TYPE_TO_XSD[kind]
        mapping = ctx.get(name)
        got = mapping.get("@type") if isinstance(mapping, dict) else None
        if got not in expected:
            bad[name] = {"json_type": kind, "expected": sorted(expected), "got": got}
    assert not bad, f"terms missing/wrong @type coercion ([OM-LD-004]): {bad}"
