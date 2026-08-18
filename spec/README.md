# openOM specification (the product)

The versioned contract every implementation conforms to — **CC-BY-4.0** (see [LICENSE](LICENSE)).

- `om-0.1.schema.json` — the payload JSON Schema (2020-12).
- `context/openom-0.1.jsonld` — JSON-LD `@context` / vocabulary (datatype-coerced per [OM-LD-004]).
- `codes.json` — canonical finding-code registry (code → requirement + severity); both cores drift-lock to it.
- `webhook-envelope-0.1.schema.json` — the §Y change-notification envelope.
- `samples/` — valid + invalid conformance samples.
- `vectors/` — the anti-fork oracle: JCS expected bytes/hashes, golden PDFs, negatives, and the
  differential-fuzz corpus. Both `core` and `js` reproduce these byte-for-byte.
- `CHANGELOG.md` — spec version history.

Regenerate the vectors (must be a no-op = no drift): `python core/scripts/gen_vectors.py`.
