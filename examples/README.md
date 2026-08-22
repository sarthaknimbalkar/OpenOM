# openOM examples

Runnable, copy-paste snippets for the three integration audiences. The library APIs are stable and
byte-parity across the Python (`openom-core`) and TypeScript (`openom-js`) cores.

## Try it in 60 seconds

- **In your browser** - drop a PDF into the verifier at **<https://openom.app/verify/>** (or download
  the [sample OM](https://openom.app/sample/openom-sample.pdf) first). Nothing leaves your machine.
- **End to end, locally** - from a clone, `pip install -e core && python examples/quickstart.py`
  ([quickstart.py](quickstart.py)) embeds → reads → validates a payload and prints the result.
  _(Published `openom-core` on PyPI is on the way; until then install from the checkout.)_
- **Ground an AI agent** - point any MCP client at the free endpoint with
  [mcp-config.json](mcp-config.json) (`https://mcp.openom.app/mcp`), then ask it to `om_read` an OM.
- **A trust badge on a page** - [badge.html](badge.html) is a drop-in `<script>` + file input that
  reads and labels a PDF entirely client-side.
- **Seed a whole back-catalog** - `om embed-batch --dir ./catalog ...` (see [`/cli`](../cli)).

## Embed at the source (Node - a producer/authoring tool)

```ts
import { readFileSync, writeFileSync } from "node:fs";
import { embedPayload } from "openom-js";

const pdf = new Uint8Array(readFileSync("offering.pdf"));
const payload = JSON.parse(readFileSync("deal.json", "utf8"));
writeFileSync("offering.openom.pdf", await embedPayload(pdf, payload)); // page content untouched
```

Python equivalent (`pip install -e core` from a clone; PyPI package coming soon):

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

## Receive change-notification webhooks (§Y - a portal/CRM)

The canonical receiver flow - **verify signature → validate envelope → verify payloadHash binds the
payload → guard `sourceUrl` (SSRF) → dedupe by event id** - is
[`js/examples/webhook-receiver.ts`](../js/examples/webhook-receiver.ts) (CI-tested). Copy that file
into your project and change its one import to `openom-js`; then wire it into any HTTP server, passing
the RAW request body text (never a re-serialized object):

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
    if (r.accepted) ingest(r.payload); // record r.eventId to dedupe retries (pass `seen` next time)
  });
}).listen(8099);
```

**Responding to deliveries (the retry contract):** return **2xx** = accepted (the sender stops);
**4xx** = permanent, do NOT retry (a bad signature / malformed envelope — don't 4xx a transient outage
or you lose the update); **5xx / timeout** = the sender retries with backoff (the reference publisher:
3 attempts). Delivery is **at-least-once**: retries re-send the same `OpenOM-Event-Id`, so record
processed ids and pass a `seen(eventId)` to `receiveWebhook` to drop duplicates. Treat the envelope's
`verification.*` as the **sender's self-report** — recompute your own; never surface it as your trust.

See [`/js`](../js) for the full SDK surface and [`/spec`](../spec) for the schema, vectors, the
webhook-envelope + [subscription](../spec/webhook-subscription-0.1.schema.json) contracts.
