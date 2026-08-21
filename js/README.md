# openom-js

The TypeScript reference implementation of the **openOM** standard - canonicalization, embed/read,
verify, schema + consistency validation, in-browser decryption, and the §Y webhook helpers. Deterministic
and **inference-free**; byte-for-byte parity with the Python core (a cross-implementation oracle enforces
it). Powers the openOM browser extension and any Node/web consumer.

> openOM embeds a machine-readable, broker-asserted JSON-LD payload inside CRE offering-memorandum PDFs
> (the Factur-X mechanism) and mirrors it as JSON-LD on the web. One extraction at the source, infinite
> cheap consumption downstream. Published by **Vervelio Labs** (MIT; the spec is CC-BY-4.0).

## Install

```sh
npm install openom-js
```

Runtime: Node ≥ 20 or a modern browser. No build step needed by consumers.

## Read + verify a payload from a PDF

```ts
import { readPayloadFromBytes } from "openom-js";

const r = await readPayloadFromBytes(pdfBytes); // Uint8Array
// r.state: "absent" | "present" | "hash-mismatch" | "encrypted"
if (r.state === "present" && r.verification.hashValid) {
  console.log("unaltered since embed:", r.payload);
}
```

## Embed a payload (author side)

```ts
import { embedPayload } from "openom-js";

const out = await embedPayload(pdfBytes, payload); // non-destructive: page content untouched
```

## Validate (schema errors block; consistency warnings never do)

```ts
import { validatePayload } from "openom-js";
import schema from "openom-js/spec/om-0.1.schema.json"; // or your copy of the schema

const report = validatePayload(payload, schema);
// report.errors (block embed) · report.warnings (OMW-W###) · report.info (OMI-I###)
```

## Verify a webhook delivery (receiver side, §Y)

```ts
import { verifyWebhookSignature, verifyEnvelopePayloadHash, validateEnvelope } from "openom-js";

if (!verifyWebhookSignature({ secret, body, signatureHeader })) throw new Error("bad signature");
if (!validateEnvelope(envelope).valid) throw new Error("bad shape");
if (!verifyEnvelopePayloadHash(envelope)) throw new Error("payloadHash does not bind payload");
```

## Other exports

`canonicalize` · `payloadHash` · `verifyOrigin` · `badgeState`/`honestLabel` · `decryptPdf`
(empty-password AES) · `assertSafeUrl` (SSRF host guard) · `extractPageText`. See `src/index.ts`.

## Development

```sh
npm ci && npm test        # vitest (unit + cross-impl vectors + JCS differential fuzz)
npm run typecheck && npm run lint
```

The spec, JSON Schema, and conformance vectors live in [`/spec`](../spec); the Python core in
[`/core`](../core). Contributions: see the repo root [`CONTRIBUTING.md`](../CONTRIBUTING.md).
