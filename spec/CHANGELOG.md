# openOM Spec Changelog

All notable changes to the openOM payload schema, `@context`, and conformance vectors are
recorded here. The spec is the product; every payload-shape change is a versioned contract
change ([OM-VER]). Format: [Keep a Changelog](https://keepachangelog.com/); the schema follows
its own `specVersion` (currently `0.1`), independent of tool package versions.

## [Unreleased]

### Added
- Optional lease fields `lease.termMonths` (stated total term) and `lease.remainingTermMonths`
  (stated remaining term as of assertedDate) — inputs for the date/term consistency checks
  OMW-W031 and OMW-W030. Additive/minor (§F); older payloads remain valid.
- Conformance sample matrix (`spec/samples/manifest.json`) with expected schema-tier outcomes,
  reproduced by both implementations.
- Edge canonicalization vectors: `edge-numbers` (denormals, negative zero, max-safe-int) and
  `edge-unicode` (NFD, astral surrogate pairs, RTL override).

### Changed
- `format` constraints (`date`) are now **asserted**, not annotation-only, in both
  implementations (Python: jsonschema format-checker; TypeScript: ajv-formats `mode: full`),
  with calendar-strict date validation.
- The `omspec:` XMP integrity marker is written and read as conformant, namespaced XML in both
  implementations (fixes a cross-implementation marker fork).

### Notes
- `additionalProperties` is intentionally left open across the schema: unknown OPTIONAL members
  are permitted for forward compatibility ([OM-VER-003]).
- **Name lock (Q1):** the standard is **openOM**, published by Vervelio Labs. The `@context`,
  XMP namespace, and schema `$id` are now anchored at `https://verveliolabs.com/openom/...`
  (was the `SPEC-DOMAIN-TBD` placeholder). Vectors + golden PDFs were regenerated once against
  the real namespace; cross-implementation byte-identity re-verified.

## [0.1] — seed

- Initial JSON Schema (2020-12) for the offering-memorandum payload.
- RFC 8785 (JCS) canonicalization + SHA-256 integrity hash; signature excluded from the
  preimage ([OM-CANON-003]).
- Seed canonicalization vectors (`cafe`, `numbers`, `unicode`, `sample-stnl`) with golden
  embedded PDFs for the cross-implementation round-trip ([OM-VEC-002]).
