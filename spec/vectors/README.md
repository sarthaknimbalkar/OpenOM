# openOM conformance vectors (the anti-fork oracle)

These are the golden vectors an **independent implementation** must reproduce byte-for-byte to be
conformant. The reference `core` (Python) and `js` (TypeScript) both reproduce them exactly; a third
party runs their own embed/canonicalize/read/validate against the same inputs and compares to
`expected/`.

## `manifest.json`

```jsonc
{
  "specVersion": "0.1",
  "suite": "…",
  "vectors": [
    {
      "name": "stnl-basic",              // vector id
      "payload": "payloads/<name>.json", // input payload (JCS canonicalized + hashed)
      "expected": "expected/<name>.json",// { canonical: <JCS bytes>, payloadHash: "sha256:…" }
      "pdf": "pdfs/<name>.pdf",          // golden embedded PDF (optional)
      "dimensions": {
        "level": ["L1"],                  // conformance level (see GOVERNANCE.md)
        "role":  ["producer", "consumer"],// which role(s) the vector exercises
        "pathology": []                   // non-empty for the pathologies/ + negatives/ corpora
      }
    }
  ]
}
```

Sibling manifests: `pathologies/`, `negatives/`, `fuzz/` (differential-fuzz corpus), and
`samples/manifest.json` (valid/invalid schema samples with expected error codes).

## Running against your implementation (language-agnostic)

For each vector in `manifest.json`:

1. **Producer** - canonicalize `payloads/<name>.json` with RFC 8785 JCS (dropping `meta.signature`
   from the preimage, [OM-CANON-003]). Assert your bytes == `expected/<name>.json.canonical` and your
   `sha256:` digest == `.payloadHash`.
2. **Consumer** - read `pdfs/<name>.pdf`, extract the `om.json` stream, and assert its byte-hash
   equals the marker `payloadHash` without re-canonicalizing ([OM-CANON-008]).
3. **Validator** - run `samples/*` through your validator; the resulting error codes must match
   `samples/manifest.json` (enable full `format` assertion, [OM-VAL-002]).

Every `OM-*` requirement referenced here is defined in
[`/spec/requirements.json`](../requirements.json) (rendered at https://openom.app/docs/requirements).

The reference cores regenerate these with `python core/scripts/gen_vectors.py` (must be a no-op -
that is a maintainer regen, not the third-party conformance run above).
