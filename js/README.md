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

**ESM-only** (`"type": "module"`, Node ≥ 20 - no CommonJS `require`). The package is side-effect-free
and ships fine-grained subpaths so a read-only or summarize-only consumer tree-shakes away the rest:
`openom-js/read`, `/validate`, `/summary`, `/badge`, `/codes`. **Dependency footprint:** the read/
verify/validate/summarize paths are pure JS. **`pdfjs-dist` is an OPTIONAL peer dependency** - it is
loaded only by `extractPageText` and the encrypted-read fallback, so read/verify/validate/summarize
consumers never install it; `npm install pdfjs-dist` only if you use those paths (a clear error tells
you if it's missing). `pdf-lib` (embed/read structure) stays a normal dependency.

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

const report = validatePayload(payload); // the 0.1 schema is bundled - no separate file needed
// report.errors (block embed) · report.warnings (OMW-W###) · report.info (OMI-I###)

// Need the schema itself (e.g. to feed another validator)? It ships with the package:
import { OM_SCHEMA, SPEC_VERSION } from "openom-js"; // SPEC_VERSION === "0.1"
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
(empty-password AES) · `assertSafeUrl` (SSRF host guard) · `summarizeDeal` · `OM_SCHEMA`/`SPEC_VERSION`
· `OM_CODES`/`OmCode` (the finding-code registry + union) · the `OMPayload` type. See `src/index.ts`.

> **Browser text extraction:** `extractPageText` uses pdf.js and, in a browser, needs a worker URL -
> call `setPdfWorkerSrc("<url-to>/pdf.worker.min.mjs")` once before using it. Node needs no worker.

## Stability

0.x: the **consumer surface** - `readPayloadFromBytes`, `validatePayload`, `summarizeDeal`,
`verifyOrigin`, `badgeState`/`honestLabel`, `OM_SCHEMA`/`OM_CODES` - is stable within `0.x`; author-
mode/advanced exports (`finalizePayload`, `assertAndEmbed`, `captureFromBytes`, …) may change in a
minor. The embedded payload contract is versioned by `specVersion` and only changes with the spec.
See [CHANGELOG.md](./CHANGELOG.md).

## Development

```sh
npm ci && npm test        # vitest (unit + cross-impl vectors + JCS differential fuzz)
npm run typecheck && npm run lint
```

The spec, JSON Schema, and conformance vectors live in [`/spec`](../spec); the Python core in
[`/core`](../core). Contributions: see the repo root [`CONTRIBUTING.md`](../CONTRIBUTING.md).
