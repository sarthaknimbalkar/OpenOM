# Writing a structured connector (Buildout MCP, DealGround, a CRM)

A **connector** feeds author mode the broker's own structured record — at the source, with **no PDF
and no inference** — so the review draft is higher-fidelity than OCR/model extraction. This is the
deterministic ingestion path (decision memo §3). The generic seam is `source.ts`; a connector is a
thin adapter over it.

## The contract (all you implement)

Implement `StructuredConnector` (from `source.ts`):

```ts
interface StructuredConnector {
  readonly id: string;                 // "buildout"
  readonly label: string;              // "Buildout"
  available(): Promise<boolean>;       // is a connection configured + reachable?
  fetch(ref: string): Promise<Record<string, unknown>>;  // → a PARTIAL openOM payload
}
```

`fetch` returns a **partial openOM payload** — the same shape as `spec/om-0.1.schema.json`, with only
the members you have. That is the single intermediate; there is **no third vocabulary**. Your only
real work is mapping your source's fields onto openOM JSON pointers, e.g.:

```ts
// EXAMPLE — replace with your source's actual response fields (this is the Q2 fill-in).
async fetch(ref) {
  const l = await buildoutClient.getListing(ref);      // your MCP/OAuth call
  return {
    property: { propertyType: l.assetType, units: l.unitCount, occupancy: l.occupancyPct / 100 },
    deal: { askingPrice: l.price, capRate: l.capRate, noi: l.noi, pricePerUnit: l.pricePerUnit },
    // lease / rentSchedule when present; omit anything you don't have — never guess.
  };
}
```

Wrap it and hand it to the picker:

```ts
const src = connectorSource(buildoutConnector, listingRef);
const chosen = await pickDraftSource([src, extractorSource(onDeviceExtractor, "On-device")]);
```

`pickDraftSource` prefers the deterministic connector and falls back to the on-device model.

## Decided defaults (decision memo §3.3 — you don't need to re-litigate these)

- **Provenance:** connector fields are drafted as `source: "extracted"` and promoted to `"asserted"`
  at the human review gate — the same path as model extraction. No new `source` value; no spec change.
- **Human gate still applies:** a connector pull is a *draft*, never an auto-assertion.
  `assertedBy` / `assertedDate` are stamped by the human at the gate and are **never** imported —
  `partialPayloadToFields` skips them (and the structural `@context`/`@type`/`specVersion`/`meta`).
- **Token custody:** reuse the source's own OAuth. openOM consumes the authenticated client; it does
  not re-implement token storage (in-extension: `chrome.identity`; Node/CLI: the client's own store).
- **Where it runs:** default is extension author mode (authoring is where the human already is). If
  your MCP is stdio-only rather than HTTP/OAuth-web-flow, host the connector in a Node/CLI companion
  instead — the interface above is identical either way.

## Reference Buildout connector (Q2 decided by design)

`connectors/buildout.ts` is a complete, tested reference: `makeBuildoutConnector(client)` maps a
`BuildoutListing` → a partial openOM payload (percent→fraction conversions, omit-if-absent, human-only
identity excluded). The wire call is an injected `BuildoutClient`, so transport is irrelevant (HTTP/
OAuth MCP, stdio client, or a hosted proxy all fit).

**What's left to make it live** is only reconciliation, not design: rename the `BuildoutListing`
fields + adjust units to match your real Buildout MCP response, implement `BuildoutClient` against
your MCP (the transport), and pick the run-location. The seam, mapper, picker, gate, and mapping are
all built and tested.
