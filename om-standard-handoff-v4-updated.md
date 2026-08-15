# OM Structured Data Standard + Tooling — Handoff Document

**Version:** v4.1 (2026-08-15) — publish resolved: neutral named webhooks only, no presets; webhook envelope mini-spec added
**Publisher:** Vervelio
**Audience:** Scott + developer + Claude Code
**Status:** Scoping complete enough to begin Milestone 1. Decisions log §13.
**Supersedes:** v0–v3. v4 adds extension **consumer mode** (payload detection while browsing, payload card, webhook publish, index submission future), detection mechanics (re-fetch, not viewer inspection), publish architecture, M5 split (consumer mode ships first).

---

## 1. What this is

An open (MIT) standard + toolchain that embeds a machine-readable, broker-asserted data payload inside commercial real estate offering memorandum PDFs, and exposes the same payload as JSON-LD on the web. One extraction at the source, infinite cheap consumption downstream.

Deliverables from one codebase:
1. **Engine** — Python library + CLI (deterministic PDF/data verbs)
2. **MCP server** — dual transport (stdio + hosted Streamable HTTP), works in any MCP client
3. **Process layer** — Claude Skill + generic agent-instructions file (the extraction playbook)
4. **JS subset** — TypeScript package: embed/read/validate, powering the Chrome extension
5. **Chrome extension** — dual persona: **author mode** (broker embeds) + **consumer mode** (anyone detects, views, routes payloads)

---

## 2. Vision & strategic thesis (the "why" — do not lose this)

**The problem.** OMs are human-readable PDFs. Every consumer — buyer, buyer's broker, lender, analyst, LLM agents — re-extracts the same facts (price, cap rate, NOI, lease terms) from scratch. A 40-page OM through a vision model is ~30–80k tokens, slow, lossy. Multiply by every party on every deal.

**The move.** Embed a canonical payload in the PDF itself. Precedent: **Factur-X / ZUGFeRD** — structured XML embedded in PDF/A-3; went from open spec to legal e-invoicing mandate in France/Germany. Same move for CRE OMs.

**The spec is the product; the tool is a commodity.** What compounds: versioned schema, JSON Schema validator, vocabulary namespace, governance. Ship `omspec 0.1` *with* the tool.

**Token asymmetry = the pitch.** Listing broker pays extraction once (~20–60k tokens in their existing AI client, or free on-device via the extension). Every downstream agent forever reads a ~2–5k broker-asserted payload. *"Make your deal legible to the buy-side's AI."*

**Two-sided flywheel (v4).** Author mode creates supply; **consumer mode creates visible demand** — buy-side tools lighting up on embedded OMs give listing brokers a reason to embed, and give buyers' brokers a reason to *ask* for embedded OMs.

**End state.** (a) Agents check for the payload first; vision fallback only on unembedded docs. (b) The standard becomes the substrate for a **distributed, free-market MLS** — JSON-LD listing pages + embedded payloads, crawlable by anyone, no central gatekeeper. Consumer-mode "submit to index" means the registry builds itself from the demand side (§10). Prerequisite: signatures/provenance — an unsigned free MLS is a spam magnet.

**Neutrality.** Published under **Vervelio**, not Fortis. Fortis = first adopter, seed corpus, reference consumer (via Phil).

---

## 3. The canonical workflow loop (adoption motion)

> **Generate OM → run it through the tool → rehost the embedded OM.**

Design consequences:
1. **Near-zero friction.** One command / one click / one agent instruction; slots behind existing OM producers (InDesign, Word-to-PDF, Buildout) unchanged.
2. **Non-destructive embed.** Visually identical output; preserves quality, bookmarks, links; no content recompression.
3. **Idempotent update semantics.** **Price reductions are the most common re-embed event.** Re-embed *replaces* the payload (never stacks), bumps `assertedDate`, records `supersedes` = prior payload hash. Repricing = first-class operation.
4. **Survival rules.** Attachments survive hosting, download, email, cloud storage. Destroyed by re-export, "print to PDF," flattening, aggressive optimizers. **Rehost the embedded file itself; never re-export.** `om_inspect(url)` verifies survival.
5. **Rehosted URL = crawl surface.** `om_read(url)` works for any agent; same payload emitted as JSON-LD in listing-page markup. Optional sidecar convention (§12 Q5).

### Future scope: the in-document badge (parked, captured)
Small visual mark on the OM itself (footer of page 2 or cover) — Factur-X logo convention. **Opt-in flag only.** Overlay stamp, spec name + version, possibly QR to public validator. Flywheel: every badged OM advertises the standard on competitors' deals. *Note: consumer-mode link badging (§4b) achieves much of this without modifying the document.*

---

## 4. Integration surfaces (getting into their build process)

Four surfaces, lowest friction → deepest integration:

### 4a. CLI / watch folder (ships with engine, free)
`om embed` in a script/CI, or a watcher on an "OM outbox" folder — coordinator exports into the folder, embedded file appears in "ready." Zero UI. Also the server-side path for platforms.

### 4b. Chrome extension (the human-facing surface — TWO PERSONAS)

**MV3.** Shared foundation: `/js` subset (pdf-lib embed/read, ajv validate, pdf.js text), side panel UI, chrome.storage.sync settings.

#### Consumer mode (ships first — no inference required, all deterministic)
*Anyone browsing encounters an embedded OM; the extension detects, displays, verifies, routes.*

- **Detection mechanics (important):** content scripts CANNOT inspect Chrome's built-in PDF viewer internals. Instead: the extension knows the **URL** of the viewed PDF, **re-fetches the same bytes itself** (typically served from HTTP cache — no real second download), and parses with the JS subset (check EmbeddedFiles + /AF + XMP marker). Same UX ("viewing a PDF → badge lights up"), different plumbing.
- **Trigger:** tab URL is a PDF (extension or content-type heuristics) → auto-check (setting, with size cap) or check-on-panel-open. Toolbar icon badge state: payload present / absent / hash-mismatch.
- **Payload card (side panel):** instant deal screen — address, price, cap, NOI + noiType, tenant, guarantor, remaining term, options — plus assertedBy/assertedDate, hash verification status, validation warnings. The "40 pages → 4 seconds" demo moment.
- **Publish (routing):** v1 = radically simple:
  - **Generic webhook:** POST payload JSON to any URL + optional bearer token (configs in storage.sync). Covers Zapier/Make/n8n → every CRM, Google Sheets, Slack, Airtable — zero connectors built.
  - **Copy JSON / download .json.**
  - **No presets, by design (SETTLED).** Every brokerage has a different database — the webhook is the universal adapter. Users configure **multiple named webhooks** ("My CRM", "Deal Sheet", …) with a test-fire button; fire-and-forget with success/fail toast. Phil is simply a webhook URL Fortis brokers configure — neutral in code, first-party in usage. (Fortis-internal note: Phil needs an inbound endpoint accepting the envelope below.)
  - **Webhook envelope mini-spec** (receiving systems build against this; version it with the spec):
    ```json
    {
      "event": "om.payload.published",
      "publishedAt": "2026-08-15T14:00:00Z",
      "sourceUrl": "https://example.com/om.pdf",
      "verification": { "hashValid": true, "signatureValid": null },
      "specVersion": "0.1",
      "payload": { "…the om.json…": "…" }
    }
    ```
  - **Future: "Submit to index"** — consumer extensions surface embedded OMs they encounter into the public registry (opt-in; hash-verified, later signature-verified → spam-resistant crowd-sourced discovery). See §10.
  - Named connectors (HubSpot, Salesforce, Sheets) only if demand proves out.
- **Link-level detection (optional, per-domain opt-in):** content script badges PDF *links* on listing pages (e.g., marketplace results) before anyone opens them — HTTP Range request on the file tail as a cheap heuristic (EmbeddedFiles/XMP marker scan; not 100% with object streams), confirmed on click. Achieves the badge vision without touching documents. Bandwidth etiquette: opt-in, cache results.
- **Local files:** require the user's "Allow access to file URLs" toggle — onboarding step, documented.

#### Author mode (ships second — needs extraction assist)
*Listing broker captures, extracts, reviews, asserts, embeds.*

- **Capture:** download interception (buildout.com + user-added domains) → "Embed machine-readable payload?" toast; context menu / toolbar on any PDF.
- **Flow:** extract → **review/edit fields** → validate (errors block, warnings inform) → **Assert & Embed** → save for rehosting.
- **Three extraction paths (ship progressively):**
  1. **Local-only (free, private):** Chrome built-in Prompt API (Gemini Nano, on-device) with schema-constrained JSON output; doc never leaves the machine. Small model — solid on clean OMs, weaker on messy rent schedules; review panel + consistency warnings are the net. **Answers the #1 brokerage objection: "I'm not uploading my unreleased OM to someone's server."** Verify Prompt API limits at build time.
  2. **Hosted extraction (commercial tier candidate):** presigned upload → Vervelio endpoint, real-model extraction → draft into same review panel. Best accuracy; natural front-end for the paid tier (§12 Q2).
  3. **Chat handoff (their subscription):** upload blob → deep-link into their chat client (prefill URLs — verify per client) → their logged-in assistant drives **our MCP connector**. *The assistant drives the tool; we never drive the assistant.*
- **HARD RULE — no chat-UI puppeteering.** Injecting into / scraping logged-in ChatGPT/Claude sessions: ToS violation, breaks on UI changes, risks the broker's account. Paths 1–3 achieve the outcome legitimately.
- **Review panel = the assertion gate.** Extraction output only *becomes* a broker assertion when a human reviews and clicks Assert & Embed. Spec: payloads SHOULD be human-reviewed before embed.

**Architecture impact:** TS subset (embed/read/validate) is **required** (`/js`); extraction stays wherever inference lives.

### 4c. Agentic browsers (Claude in Chrome, etc.)
In-browser agents run the loop as a shortcut/Skill against the MCP. Document in `/process`; no bespoke surface.

### 4d. Buildout partnership / API (endgame for this channel)
One native integration = thousands of brokerages embedding at export. **Approach as Vervelio (neutral steward), not Fortis (departing customer).** Extends to SharpLaunch, RCM/LightBox, in-house shops via 4a. **Timing: after 0.1 + tooling + traction.**

---

## 5. Architecture

### 5a. Layers, one repo

| Layer | Form | Purpose | Distribution |
|---|---|---|---|
| Engine | Python lib + CLI, MIT | Deterministic verbs | GitHub (Vervelio org) + PyPI |
| MCP server | Thin wrapper, dual transport | Agent access, any client | stdio (pipx) + hosted Streamable HTTP (Vervelio) |
| Process layer | SKILL.md + agent instructions | Extraction/mapping playbook | Skill (Claude) + AGENTS-style doc (all others) |
| JS subset | TS: embed/read/validate | Extension + web/Node consumers | npm |
| Extension | MV3, consumer + author modes | Human-facing detect/view/publish + capture/review/embed | Chrome Web Store (Vervelio) |

**Cardinal rule: MCP tools stay deterministic.** Zero inference server-side → no keys, no per-call costs, trivial hosting, testable. LLM mapping runs client-side (or on-device), guided by the process layer. Hosted inference-included extraction, if offered, is a separate commercial service — never the open server.

### 5b. Client compatibility target

| Client | Transport | Notes |
|---|---|---|
| Claude (web/desktop/mobile) | remote; desktop also stdio | + Skill |
| Claude Code / Cowork | stdio + remote | primary dev surface |
| ChatGPT | **remote only** | why remote ships at launch |
| Gemini (CLI) | stdio + remote | web-app connectors: verify |
| Copilot (VS Code agent mode) | stdio + remote | |
| Local LLMs (LM Studio, Continue, LibreChat…) | stdio | |
| Chrome (extension) | n/a — JS subset; Prompt API / hosted / chat-handoff | §4b |

### 5c. Token model ("will it cook through API tokens?" — no)
Server: zero inference, no keys. Client cost = context tokens on tool outputs; subscription users see normal usage limits, no API billing; extension local/consumer paths: zero tokens. Heavy op = one-time embedder extraction; consumers get ~2–5k `om_read`. **Tools return compact outputs** — text paginates, images return manifests + links.

### 5d. Remote file I/O
Remote can't reach client filesystems: tools accept **HTTPS URL** or **presigned upload** (→ blob id); outputs as **download links**, payload inline. stdio: plain paths. Path-or-URL polymorphic. Blobs: R2. **Retention policy needed** (unreleased OMs, §12 Q4).

---

## 6. The spec (design philosophy first)

### 6a. Assertions, not facts
**An OM is an advocacy document: broker opinion of value + seller expectations.** The payload encodes **assertions by an identified party as of a date**:
- `assertedBy` (broker, brokerage, license #) + `assertedDate` required.
- `noiType: "in-place" | "pro-forma"` **required** + `noiAsOfDate` — forces the disclosure most accuracy disputes are actually about.
- Labels derivable, not asserted: `landlordResponsibilities` boolean set (roof, structure, parking, HVAC, taxes, insurance, CAM) makes lease type *derivable and disputable* — kills "everything is NNN."
- Payloads SHOULD be human-reviewed before embed (extension review panel operationalizes).
- Tooling checks internal consistency, never market truth (§8).

### 6b. Format & governance
- **JSON-LD only** (XML dropped — no identified consumer).
- `@context`: schema.org (`RealEstateListing`, `Offer`, `Place`, `PostalAddress`, `Organization`) + custom vocab (capRate, noi, rentSchedule, guarantor, options…). Rent schedules unmodeled anywhere = the opportunity.
- `"specVersion": "0.1"` + published JSON Schema.
- Borrow RESO/OSCRE names for credibility; don't adopt wholesale.
- Name TBD — reserve **GitHub org + PyPI + npm + Chrome Web Store listing + domain as a set** before code. Candidates: OpenOM, omspec, ListingLD.

### 6c. v0.1 scope (confirmed)
STNL, **N through NNN**, retail/QSR/pharmacy. Multi-tenant/industrial/office later.

### 6d. Field sketch
- **Property:** address (parsed + geo), APN, building SF, lot, year built/renovated.
- **Deal:** asking price, cap rate, NOI + noiType + noiAsOfDate, price/SF, status.
- **Lease:** tenant entity, guarantor + type, landlordResponsibilities booleans, asserted lease type, commencement, expiration, remaining term, rentSchedule [{periodStart, periodEnd, annualRent, rentPSF}], escalations, options, ROFR/ROFO.
- **Parties:** listing broker(s), brokerage, license #s, contact.
- **Meta:** specVersion, assertedBy, assertedDate, sourceDocHash, supersedes, signature (v2), imageRights (optional).

### 6e. Sample payload (illustrative — fictional deal)
```json
{
  "@context": ["https://schema.org", "https://SPEC-DOMAIN-TBD/ns/0.1"],
  "@type": "RealEstateListing",
  "specVersion": "0.1",
  "assertedBy": { "broker": "Jane Example", "brokerage": "Example Net Lease Advisors", "license": "MI 6501-000000" },
  "assertedDate": "2026-08-15",
  "property": {
    "address": { "streetAddress": "1000 Example Rd", "addressLocality": "Sampleville", "addressRegion": "MI", "postalCode": "48000" },
    "geo": { "latitude": 42.0, "longitude": -83.0 },
    "apn": "00-000-000-000", "buildingSF": 9100, "lotAcres": 1.25, "yearBuilt": 2019
  },
  "deal": { "askingPrice": 1850000, "capRate": 0.0625, "noi": 115625, "noiType": "in-place", "noiAsOfDate": "2026-06-30", "status": "active" },
  "lease": {
    "tenantEntity": "Example Retail Stores, LLC",
    "guarantor": { "name": "Example Retail Corp.", "type": "corporate" },
    "landlordResponsibilities": { "roof": false, "structure": false, "parking": false, "hvac": false, "taxes": false, "insurance": false, "cam": false },
    "leaseTypeAsserted": "NNN",
    "commencement": "2019-05-01", "expiration": "2034-04-30",
    "rentSchedule": [
      { "periodStart": "2024-05-01", "periodEnd": "2029-04-30", "annualRent": 115625 },
      { "periodStart": "2029-04-30", "periodEnd": "2034-04-30", "annualRent": 127188 }
    ],
    "options": [ { "count": 4, "lengthYears": 5, "escalation": "10% per option" } ]
  },
  "meta": { "sourceDocHash": "sha256:…", "supersedes": null }
}
```

---

## 7. PDF mechanics

### 7a. Embedding
- `om.json` as **PDF embedded file** + **/AF**, `AFRelationship = Data` (Factur-X mechanism). **XMP block:** spec name, version, payload filename, payload hash.
- Pragmatic v1: PDF/A-3-*style*, strict conformance later.
- **Update semantics:** detect existing → replace attachment, update XMP, set `supersedes`. Never duplicate.
- Consumer path: /AF + XMP → attachment → schema validate. Fallback: full extraction.
- **Cross-implementation round-trip test:** pdf-lib output readable by pikepdf and vice versa, byte-for-byte payload fidelity. The kind of bug that silently kills a standard — named test from day one.

### 7b. Image extraction (settled: yes, no rendering)
Raster images = **Image XObjects**; extraction = locate + decompress (PyMuPDF primary; poppler `pdfimages -list` cross-check). Handle: SMasks (→RGBA), CMYK/ICC→sRGB, tiled/striped images (InDesign), dedupe by xref, vector content (paths → render fallback only), scanned/flattened (full-page image per page; Distiller-derived usually preserves XObjects). `om_inspect` classifies native/hybrid/scanned up front. Third-party photo licenses → imageRights field.

### 7c. Libraries
Python: pikepdf, PyMuPDF, jsonschema, typer, FastMCP. JS: pdf-lib, ajv, pdf.js.

---

## 8. MCP tool surface + validation philosophy

| Tool | Signature | Notes |
|---|---|---|
| `om_inspect` | pdf(path\|url) → profile | class, pages, payload present + version?, image inventory, text coverage |
| `om_extract_text` | pdf, page_range → text + tables | paginated |
| `om_extract_images` | pdf → manifest + links/paths | SMask, dedupe, colorspace |
| `om_read` | pdf(path\|url) → payload \| null | hash verify; the cheap consumer path |
| `om_validate` | payload → report | two-tier below |
| `om_embed` | pdf, payload → new pdf | invalid = refuse; warnings never block; §7a semantics |

### Validation: two tiers, hard boundary
1. **Errors (block):** JSON Schema violations.
2. **Warnings (never block):** internal consistency — NOI ÷ price vs. cap rate, schedule sums, date/term arithmetic, continuity. Self-contradiction is data-quality regardless of opinion.
3. **Out of scope forever:** market truth. Consuming LLMs editorialize anyway; spec/tools take no position.

**Trojan horse:** the consistency checker is independently useful — OMs fail their own math constantly; brokerages run the validator for typo-catching before they care about embedding.

Orchestration: inspect → extract → agent/on-device maps → human review → validate → embed → rehost → (consumer: detect → verify → publish).

---

## 9. Adoption strategy summary
1. **Embedder-pays-once token asymmetry** (§2).
2. **Validator as trojan horse** (§8).
3. **Consumer mode creates visible demand** (§4b) — buy-side lights up on embedded OMs; buyers' brokers start *asking* for them.
4. **Extension makes authoring one click; local path removes the confidentiality objection** (§4b).
5. **Publish/webhook makes payloads immediately useful** — into CRMs/Sheets/Phil on day one.
6. **Fortis seeds supply; Phil is the reference consumer** — wired in as an ordinary webhook, proving the neutral pattern.
7. **Buildout + peer integrations** (§4d).
8. **Badges** — link-level (consumer mode, no doc changes) now-ish; in-document overlay later.
9. **Neutral governance under Vervelio.**

## 10. Trust / provenance roadmap
- **Day one:** payload hash in XMP; extension shows hash-verification state.
- **v2:** broker signatures (key per brokerage/license #) — prerequisite for the open-MLS layer.
- **Later:** registry/index = the free-market MLS. **Crowd-sourced from the demand side:** consumer-mode "submit to index" surfaces embedded OMs as people encounter them (opt-in). Hash + signature verification keeps it spam-resistant. Anyone can build an index; Vervelio/Phil builds the reference.

## 11. Future scope (parked, not forgotten)
In-document badge overlay (§3) · signatures (§10) · registry + submit-to-index (§10) · named publish connectors (HubSpot/Salesforce/Sheets) · multi-tenant/industrial/office spec versions · strict PDF/A-3 · XMP mirror fields · hosted inference tier (§12 Q2) · sidecar convention (§12 Q5) · Buildout + peer native integrations · Firefox/Edge ports (Edge ≈ free via Chromium; check Prompt API availability).

## 12. Open questions
1. **Name:** sweep GitHub org + PyPI + npm + domain (+ Chrome Web Store) as a set. Gates `@context` + imports. Candidates: OpenOM, omspec, ListingLD.
2. **Free/paid boundary:** engine/MCP/extension local + consumer paths = free MIT. Hosted inference extraction = commercial tier? Shapes repo structure + extension monetization. **Decide before M3.**
3. **XMP mirror fields** for dumb crawlers.
4. **Blob storage + retention** (R2): unreleased OMs → expiry policy.
5. **Sidecar convention** (om.json beside om.pdf)?
6. **Verify at build time:** Gemini web connectors · Chrome Prompt API limits + structured output · chat prefill deep-links per client · Chrome Web Store publishing under Vervelio · Prompt API on Edge.
7. **Buildout approach:** timing + channel.
8. **Consumer-mode defaults:** auto-check every viewed PDF (with size cap) vs. check-on-open? Link-badging per-domain opt-in list? Cache TTL for detection results?
9. **Index submission consent model** (when registry exists): what exactly is shared, and when?

## 13. Decisions log
| Date | Decision | Rationale |
|---|---|---|
| 2026-08-15 | Layered architecture, one repo | Deterministic engine ≠ LLM process |
| 2026-08-15 | Python core (pikepdf + PyMuPDF) | PDF tooling maturity |
| 2026-08-15 | Factur-X-style PDF/A-3 embedding, relaxed v1 | Proven mechanism |
| 2026-08-15 | JSON-LD, schema.org + custom vocab, versioned + JSON Schema | Spec is the product |
| 2026-08-15 | XML dropped | No identified consumer |
| 2026-08-15 | v0.1 = STNL, N/NN/NNN | Most standardized; Fortis seeds |
| 2026-08-15 | Published under Vervelio | Neutral governance |
| 2026-08-15 | Dual transport; hosted Streamable HTTP — Vervelio hosts | ChatGPT/web reach |
| 2026-08-15 | Zero inference server-side | No keys/costs; "won't cook tokens" |
| 2026-08-15 | Validator = errors + consistency warnings; never market truth | Assertions, not facts |
| 2026-08-15 | noiType + asOfDate required; assertedBy/Date framing | Opinion-not-fact in the spec |
| 2026-08-15 | landlordResponsibilities booleans | Kills "everything is NNN" |
| 2026-08-15 | Workflow = generate → embed → rehost; idempotent updates | Repricing is the common case |
| 2026-08-15 | In-document badge = future, opt-in | Never silently modify visuals |
| 2026-08-15 | Chrome extension = primary human-facing surface | One-click authoring + detection |
| 2026-08-15 | HARD RULE: no chat-UI puppeteering | ToS, fragility, account risk |
| 2026-08-15 | TS subset required | Extension needs in-browser engine |
| 2026-08-15 | Review-before-embed = spec SHOULD; review panel = assertion gate | Extraction → assertion via human |
| 2026-08-15 | **Extension consumer mode: detect / payload card / verify / publish** | Demand side of the flywheel |
| 2026-08-15 | **Detection via re-fetch of the PDF URL, never viewer inspection** | Viewer internals are inaccessible; re-fetch hits cache anyway |
| 2026-08-15 | **Publish v1 = neutral named webhooks only + copy/download JSON; NO presets** | Every brokerage has a different database; webhook is the universal adapter; Phil = just a configured URL |
| 2026-08-15 | **Webhook envelope mini-spec, versioned with the spec** | Receiving systems need a stable contract |
| 2026-08-15 | **Consumer mode ships before author mode (M5a → M5b)** | Fully deterministic — no model needed; demo-able weeks earlier |

## 14. Development plan (Claude Code handoff)

**Repo layout:** `/core` (Python) · `/cli` · `/mcp` · `/process` · `/spec` · `/js` (TS subset) · `/extension` (MV3, consumer + author) · `/fixtures`.

**Fixtures before extraction logic.** 10–15 OMs across producers (InDesign, Word-to-PDF, Buildout, scans). Producer diversity is where PDF tooling breaks. (Scott sources.)

**M1 — round trip (stdio).** inspect + extract_images + embed/read on 3 real OMs (native/hybrid/scanned). Prove: non-destructive, idempotent re-embed w/ supersedes, survival through download/re-upload.
**M2 — schema + validate.** JSON Schema 0.1, two-tier validate, samples in /spec.
**M3 — remote transport.** Streamable HTTP, URL + presigned upload, R2, link outputs. (Free/paid decided by here.)
**M4 — process layer.** SKILL.md + generic instructions; end-to-end in Claude + one non-Claude client.
**M5a — extension consumer mode.** `/js` read/validate (+ cross-impl test vs pikepdf) → MV3 detection (re-fetch on viewed PDFs, toolbar badge) → payload card → named-webhook publish (envelope spec) + test-fire + copy/download. *No model anywhere.*
**M5b — extension author mode.** Download interception (Buildout + custom), side-panel review, local extraction via Prompt API, hosted path stubbed behind Q2, embed via `/js`.

**Suggested first Claude Code prompt (M1):** "Read /spec and this handoff doc. Scaffold /core with pikepdf-based embed/read (EmbeddedFiles + /AF AFRelationship=Data + XMP block w/ spec name/version/hash), PyMuPDF-based inspect (native/hybrid/scanned classification) and image extraction (SMask recombine, xref dedupe, CMYK→sRGB). Idempotent re-embed with supersedes hash. pytest round-trip against /fixtures. No LLM calls anywhere in /core."

**Standing rules for dev:** no inference in the open server or consumer mode, ever · tools return compact outputs · never modify visual content without an explicit flag · every payload change bumps assertedDate · no automation of third-party logged-in sessions · detection re-fetches bytes, never scrapes the viewer.
