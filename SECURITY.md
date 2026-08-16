# Security Policy

## Reporting a vulnerability

Email **hello@vervelio.com** with details and a reproduction. Please do not open a public issue
for security-sensitive reports. We aim to acknowledge within 3 business days.

## Threat model

openOM's core processes **untrusted PDF input** and produces deterministic output. The design
constraints below are security properties, not just style:

- **No inference, no network, no telemetry in the core.** `core/`, `cli`, and `mcp` make zero
  outbound calls and hold no credentials. There is nothing to exfiltrate and no key to leak.
  CI's `boundary` job fails if a network/inference client enters the dependency tree.
- **Decompression bombs.** Embedded payloads are capped (`MAX_PAYLOAD_BYTES`, 5 MB) and rejected
  with `OM-IO-BOMB` rather than expanded unboundedly. _(Hardening the pre-decompression bound on
  the read path is tracked for a follow-up; see the backlog.)_
- **Malformed / hostile Unicode.** Canonicalization rejects unpaired surrogates
  (`OM-IO-BADUTF8`), duplicate member names after NFC (`OM-IO-DUPKEY`), non-representable
  numbers (`OM-IO-NUMRANGE`), and non-object top levels (`OM-IO-TOPLEVEL`).
- **Non-destructive by construction.** Embedding appends an attachment + XMP marker without
  touching page content; the visual document is unchanged.
- **Integrity, not authenticity (0.1).** The integrity hash (SHA-256 over the canonical bytes)
  detects tampering/corruption of the payload. Cryptographic *signatures* (authenticity of the
  asserting party) are reserved for a future version; `meta.signature` must be absent in 0.1.

## What is explicitly out of scope

- **Market truth.** openOM never asserts a claim is *correct*, only internally consistent. A
  payload is an identified party's opinion as of a date.
- **Extraction correctness of third-party authoring tools.** The standard defines the payload
  and its verification, not the accuracy of any particular producer's mapping.

## Supported versions

Pre-1.0: only the latest `main` receives fixes. The `0.1` schema may change until 1.0.
