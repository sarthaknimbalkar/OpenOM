# Changelog - openom-js

All notable changes to the `openom-js` package. This project follows [SemVer](https://semver.org);
while at `0.x`, the **consumer surface** (read/validate/summarize/verify/badge, `OM_SCHEMA`,
`OM_CODES`, the `OMPayload` type) is stable within the `0.x` line, and author-mode/advanced exports
may change in a minor. The embedded payload contract is versioned separately by `specVersion`.

## [Unreleased]

## [0.1.1] - 2026-08-25

### Added

- Bundled JSON Schema: `OM_SCHEMA`, `SPEC_VERSION`, `loadSchema()`; `validatePayload(payload)` now
  defaults to the bundled schema (no separate schema file needed).
- Generated, exported payload type `OMPayload` / `RealEstateListing`; `readPayloadFromBytes` returns
  `OMPayload | null`.
- Finding-code registry `OM_CODES` + the `OmCode` string-literal union; `Finding.code` is now `OmCode`.
- `ReadResult.sourceDocHash` (read from the marker), for parity with the Python `om_read` shape.
- Fine-grained subpath exports (`openom-js/read`, `/validate`, `/summary`, `/badge`, `/codes`) and
  `"sideEffects": false` for tree-shaking.
- `prepare` build hook so a git/`file:` install builds automatically.

### Changed

- `ValidationReport.specVersion` is derived from the validated schema's `specVersion` const rather
  than a hard-coded literal.

## [0.1.0]

- Initial reference implementation: canonicalization (RFC 8785 JCS), embed/read, schema + consistency
  validation, webhook envelope/subscription, origin verification, the `<openom-badge>` widget - at
  byte-parity with the Python core.
