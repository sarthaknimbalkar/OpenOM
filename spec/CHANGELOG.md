# openOM Spec Changelog

All notable changes to the openOM payload schema, `@context`, and conformance vectors are
recorded here. The spec is the product; every payload-shape change is a versioned contract
change ([OM-VER]). Format: [Keep a Changelog](https://keepachangelog.com/); the schema follows
its own `specVersion` (currently `0.1`), independent of tool package versions.

## [Unreleased]

## [0.1.1] - 2026-08-25

### Added
- Thin, common-denominator investment-property fields so a multifamily / mixed-use OM's headline is
  representable without deep underwriting schema (decision memo §2): `property.units` (integer unit
  count), `property.occupancy` (decimal fraction 0–1, matching the `capRate` convention), and
  `deal.pricePerUnit` (multifamily analog of `pricePerSF`). All OPTIONAL and additive (§F) - older
  payloads remain valid; `@context` coercions added (`units` → xsd:integer, `occupancy`/
  `pricePerUnit` → xsd:decimal); documented in `process/mapping-guide.md`; new `valid-multifamily`
  conformance sample. Deliberately NOT a rent-roll/T-12 module (underwriting is a deal-desk activity).
- Optional lease fields `lease.termMonths` (stated total term) and `lease.remainingTermMonths`
  (stated remaining term as of assertedDate) - inputs for the date/term consistency checks
  OMW-W031 and OMW-W030. Additive/minor (§F); older payloads remain valid.
- Consistency tier now implements the full §H.3 warning/info band, in both implementations:
  `OMW-W012` (pro-forma NOI without noiAsOfDate), `OMW-W013` (capRate outside the [0.02, 0.20]
  plausibility band; new tolerance `tol.capRateBand`), `OMW-W032` (assertedDate in the future
  vs a caller-supplied processing date), `OMW-W033` (noiAsOfDate after assertedDate), `OMW-W034`
  (expiration on/before commencement), `OMW-W041` (leaseType contradicts the responsibility set
  generally), `OMW-W050` (self-supersede), `OMW-W060` (`source: verified` without corroborating
  metadata), and info `OMI-I001` (currency defaulted), `OMI-I002` (source tag absent → asserted),
  `OMI-I003` (a cross-check skipped for absent inputs).
- **Published JSON-LD `@context` / vocabulary** (`spec/context/openom-0.1.jsonld`) - the term→IRI
  mappings that make an openOM payload valid JSON-LD: schema.org terms (address, geo, name) map to
  schema.org IRIs; openOM terms map to `https://openom.app/ns/0.1#`; date fields carry
  `xsd:date` coercion and `rentSchedule`/`options` are ordered `@list` containers. Vocabulary
  completeness is drift-locked to the schema by `spec/tests/test_context.py` (every schema property
  and every conformant-sample term must have a mapping).
- Conformance sample matrix (`spec/samples/manifest.json`) with expected schema-tier outcomes,
  reproduced by both implementations.
- `warn-realworld` sample (#9): a coherent, fully-redacted STNL payload exhibiting the
  multi-inconsistency pattern real marketing packages show - a marketing-rounded `capRate`
  (OMW-W010) plus a `monthlyRent` data slip (OMW-W025) - demonstrating the validator on a
  realistic payload rather than a single-field synthetic mutation. (The full adoption DoD - the
  validator run on *actually-embedded* real OMs - remains tracked until a broker embeds one.)
- Edge canonicalization vectors: `edge-numbers` (denormals, negative zero, max-safe-int) and
  `edge-unicode` (NFD, astral surrogate pairs, RTL override).

### Changed
- **PDF/A Extension Schema for the `omspec` namespace** (#2): both embedders now write the PDF/A
  Extension Schema Description (`pdfaExtension`/`pdfaSchema`/`pdfaProperty`) that describes the six
  `omspec` marker properties, so a PDF/A validator no longer flags the namespace as undescribed -
  a prerequisite for any PDF/A-3 conformance claim. Written idempotently (no stacking on re-embed)
  and identically by both engines, so the claim is producer-independent. Full veraPDF PDF/A-3
  conformance validation in CI remains tied to the **strict-PDF/A-3** parked item (§13); 0.1 ships
  relaxed PDF/A-3 per §8a.
- **Consistency-code corrections** (both implementations): `OMW-W014` now fires on non-positive
  `askingPrice`/`noi`/`buildingSF` (its §H.3 meaning), not on a zero rent-schedule `annualRent`
  (which has no allocated code and is usually legitimate free rent - the ad-hoc check is removed);
  `OMI-I001` now signals a defaulted field (currency → USD), not "NOI is pro-forma" (that state
  has no info code and is already explicit in `deal.noiType`). These align the emitted codes with
  their normative §H.3 definitions.
- **`OMW-W050` clarification.** The §C integrity hash covers `meta.supersedes`, so
  "supersedes == the payload's own hash" is an unreachable fixpoint. `OMW-W050` is therefore
  defined as: `meta.supersedes` equals the hash of the payload with the `supersedes` pointer
  removed - i.e. a no-op re-embed of byte-identical content.
- `format` constraints (`date`) are now **asserted**, not annotation-only, in both
  implementations (Python: jsonschema format-checker; TypeScript: ajv-formats `mode: full`),
  with calendar-strict date validation.
- The `omspec:` XMP integrity marker is written and read as conformant, namespaced XML in both
  implementations (fixes a cross-implementation marker fork).

### Notes
- `additionalProperties` is intentionally left open across the schema: unknown OPTIONAL members
  are permitted for forward compatibility ([OM-VER-003]).
- **Name lock (Q1):** the standard is **openOM**, published by Vervelio Labs. The `@context`,
  XMP namespace, and schema `$id` are now anchored at `https://openom.app/...`
  (was the `SPEC-DOMAIN-TBD` placeholder). Vectors + golden PDFs were regenerated once against
  the real namespace; cross-implementation byte-identity re-verified.

## [0.1] - seed

- Initial JSON Schema (2020-12) for the offering-memorandum payload.
- RFC 8785 (JCS) canonicalization + SHA-256 integrity hash; signature excluded from the
  preimage ([OM-CANON-003]).
- Seed canonicalization vectors (`cafe`, `numbers`, `unicode`, `sample-stnl`) with golden
  embedded PDFs for the cross-implementation round-trip ([OM-VEC-002]).
