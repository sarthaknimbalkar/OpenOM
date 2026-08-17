# openOM author — agent instructions (any MCP client)

> Client-agnostic playbook for driving an offering-memorandum PDF to a reviewed, embedded openOM
> payload using the openOM MCP tools. For Claude, `SKILL.md` wraps this; for a broker's own AI
> (Path 3, via an MCP connector) or any other MCP client, follow this file directly. All field
> detail lives in [`./mapping-guide.md`](./mapping-guide.md) — read it first.

## Preconditions

- An MCP client connected to the openOM server, exposing the deterministic tools: `om_inspect`,
  `om_extract_text`, `om_extract_images`, `om_validate`, `om_embed` (and `om_read`,
  `om_request_upload` on the hosted transport).
- A target OM PDF reachable as a `PdfRef`: `{"path": ...}` on stdio, or `{"url": ...}` /
  `{"blobId": ...}` on the hosted transport (`path` is rejected on hosted).
- You (the client's AI) supply the reading/mapping inference. The tools never do — they hold no
  model and never call one (§6a). Never route this through a logged-in third-party chat session
  (no chat-UI puppeteering); use the MCP connector, on-device, or manual paths only.

## Steps

1. **Classify** — call `om_inspect(pdf)`. Read `class`, `pages`, `textCoverage`, `payloadPresent`.
   If a payload is already present, this is a re-embed (reprice): you will set `meta.supersedes`
   later. If `class` is `scanned`, read the pages with your own vision/OCR.
2. **Gather text** — call `om_extract_text(pdf, pageRange, cursor)`. If the result has
   `truncated: true`, call again passing `nextCursor` verbatim until complete. Capture the rent
   schedule, deal terms, lease abstract, and property details.
3. **Gather images (context)** — call `om_extract_images(pdf)` for site plans / figures if they
   clarify the property; the manifest returns links, never inline bytes.
4. **Map** — construct the payload from what you read, following
   [`./mapping-guide.md`](./mapping-guide.md): correct paths, enums, and units; `capRate` as a
   decimal fraction; money in major units; ISO dates; each rent-schedule period
   `source: "extracted"`. **Omit any field the document does not state — never invent.**
5. **Validate & iterate** — call `om_validate(payload, schema)`. Fix every `OMV-E###` (schema
   error). For every `OMW-W###` (consistency warning), **re-read the source** — a warning means a
   number you transcribed is internally inconsistent, i.e. probably wrong. Do **not** silence it.
   Loop until schema-clean and warning-clean (or a residual warning is explained to the reviewer).
6. **Stop for human review** — you MUST NOT self-assert. Present exactly what
   [`./review-contract.md`](./review-contract.md) requires: per-field value + source evidence +
   `source` tag, deliberate omissions, residual warnings, and (on reprice) a diff vs the prior
   payload. Wait for explicit approval.
7. **Assert & embed** — on approval: set `assertedBy` to the reviewing broker, set `assertedDate`
   (today), confirm `noiType`/`noiAsOfDate`, and promote each rentPeriod `source`
   `"extracted"` → `"asserted"`. Then call `om_embed(pdf, payload, assertedDate)`. On a reprice,
   set `meta.supersedes` to the prior payload hash (from the earlier `om_read`/`om_inspect`).

## Hard rules

- **Never invent facts;** omit the unknown.
- **Never** record extraction as `source: "verified"`; unreviewed extraction is at most
  `"extracted"` ([OM-SCOPE-007]).
- **Never** offer valuation, investment, or legal advice; the payload is a transcription, not an
  appraisal.
- **Disclose the extraction path** and whether the document leaves the device *before* it does
  ([OM-EXTP-002], [OM-PRIV-001]).
- **The review gate is the assertion moment** — extraction output is a draft until a human approves
  it (§7a, [OM-EXTP-003]).
