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
            if mapping["@type"].split(":", 1)[0] not in _PREFIXES:
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
