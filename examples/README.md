# openOM examples

Runnable, copy-paste snippets for the three integration audiences. The library APIs are stable and
byte-parity across the Python (`openom-core`) and TypeScript (`openom-js`) cores.

## Embed at the source (Node — a producer/authoring tool)

```ts
import { readFileSync, writeFileSync } from "node:fs";
import { embedPayload } from "openom-js";

const pdf = new Uint8Array(readFileSync("offering.pdf"));
const payload = JSON.parse(readFileSync("deal.json", "utf8"));
writeFileSync("offering.openom.pdf", await embedPayload(pdf, payload)); // page content untouched
```

Python equivalent (`pip install openom-core`):

```python
from openom_core.embed import embed
open("offering.openom.pdf", "wb").write(embed(open("offering.pdf","rb").read(), payload, asserted_date="2026-08-16"))
```

## Read + verify downstream (any consumer)

```ts
import { readPayloadFromBytes } from "openom-js";
const r = await readPayloadFromBytes(pdfBytes);
if (r.state === "present" && r.verification.hashValid) useIt(r.payload); // "unaltered since embed"
```

## Validate in CI (a producer's publishing pipeline)

```ts
import { validatePayload } from "openom-js";
import schema from "./om-0.1.schema.json" with { type: "json" };
const { errors } = validatePayload(payload, schema);
if (errors.length) process.exit(1); // schema errors block; warnings/info never do
```

## Receive change-notification webhooks (§Y — a portal/CRM)

The canonical receiver flow — **verify signature → validate envelope → verify payloadHash binds the
payload** — is [`js/examples/webhook-receiver.ts`](../js/examples/webhook-receiver.ts) (CI-tested).
Copy that file into your project and change its one import to `openom-js`; then wire it into any HTTP
server, passing the RAW request body text (never a re-serialized object):

```ts
import { createServer } from "node:http";
import { receiveWebhook } from "./webhook-receiver.js"; // the copied file (imports openom-js)

createServer((req, res) => {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => {
    const r = receiveWebhook({
      secret: process.env.OPENOM_WEBHOOK_SECRET!,
      signatureHeader: req.headers["openom-signature"] as string,
      rawBody: raw,
      nowUnix: Math.floor(Date.now() / 1000),
    });
    res.writeHead(r.accepted ? 200 : 400).end(r.reason);
    if (r.accepted) ingest(r.payload);
  });
}).listen(8099);
```

See [`/js`](../js) for the full SDK surface and [`/spec`](../spec) for the schema, vectors, and the
webhook-envelope contract.
