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
      "expected": "expected/<name>.json",// { jcs_b64: base64(JCS bytes), jcs_sha256: "sha256:…", payload: "payloads/<name>.json" }
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

Each `expected/<name>.json` has three keys: **`jcs_b64`** (the RFC 8785 canonical bytes, base64-encoded
- decode it before a byte comparison), **`jcs_sha256`** (the payload hash as `"sha256:<64-hex>"`), and
**`payload`** (the RELATIVE PATH back to the input file, e.g. `"payloads/<name>.json"` - not the payload
object itself). There is no `canonical` or `payloadHash` key. Read the payload files as UTF-8.

Sibling corpora under `vectors/`: `pathologies/`, `negatives/`, and `fuzz/` (the differential-fuzz
corpus). The valid/invalid **schema samples** with expected error codes live one level up at
[`../samples/`](../samples) (`spec/samples/manifest.json`), NOT under `vectors/`.

## Running against your implementation (language-agnostic)

For each vector in `manifest.json`:

1. **Producer** - canonicalize `payloads/<name>.json` with RFC 8785 JCS (dropping `meta.signature`
   from the preimage, [OM-CANON-003]). Assert your bytes == `base64-decode(expected/<name>.json.jcs_b64)`
   and your `"sha256:"`-prefixed digest == `expected/<name>.json.jcs_sha256`.
2. **Consumer** - read `pdfs/<name>.pdf`, locate + extract the `om.json` attachment stream
   ([OM-EMB-014]; detect via the XMP marker [OM-XMP-005]), and assert its byte-hash equals the marker
   hash without re-canonicalizing ([OM-CANON-008]).
3. **Validator** - run `../samples/*` (i.e. `spec/samples/`) through your validator; the resulting
   error codes must match `../samples/manifest.json` (enable full `format` assertion, [OM-VAL-002]).

Every `OM-*` requirement referenced here is defined in
[`/spec/requirements.json`](../requirements.json) (rendered at https://openom.app/docs/requirements).

The reference cores regenerate these with `python core/scripts/gen_vectors.py` (must be a no-op -
that is a maintainer regen, not the third-party conformance run above).
