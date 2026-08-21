# OM Structured Data Standard + Tooling - Handoff Document

**Version:** v6.1 (2026-08-16)
**Publisher:** Vervelio
**Audience:** Scott (business) + developer + Claude Code
**Status:** Scoping complete; ready to begin Milestone 1. Decisions log §16.
**Supersedes:** v0–v6.0. v6.0 took the document to standards-grade peak across a 28-appendix Part II. **v6.1 restores it to a *handoff*: the M1-essential normative core (§A–§E, §H–§J) stays inline; the ~60% institutional apparatus a standards body needs but an org of one does not yet - versioning, licensing/IP, privacy, governance, telemetry, diagrams, the worked example, the `@context` model, the ABNF grammar, conformance profiles, the reference harness, disclosure, and the §V–§AA conformance appendices - is parked intact in [`om-normative-spec-draft-v0.1.md`](om-normative-spec-draft-v0.1.md) until adoption. Shadow removed: the auto-generatable requirements index, glossary over-definitions, and thesis restatements. The four internal contradictions v6.0 briefly carried (OMW-W002, the tolerance table, the conformance schemes, disclosure/patent) are reconciled to one source of truth each.**



> **Document structure.** **Part I (§1–§16)** is the narrative handoff - the why, the strategy, the plan. **Part II** inlines only the **M1-essential normative core** (§A–§E, §H–§J; RFC 2119 keywords). The remaining normative appendices are drafted but **deferred until adoption** in [`om-normative-spec-draft-v0.1.md`](om-normative-spec-draft-v0.1.md) (see the scope note at the head of Part II). Where Part I and any normative section disagree, **the normative section wins.**


> **Name note:** "OpenOM" is a **working title, not locked.** The name sweep (§15 Q1) is P0 - it gates `@context`, PyPI/npm imports, and the org/domain reservation. Everything below uses "OpenOM"/`openom.app` as placeholders.

---

## TL;DR (for Scott)

- **What:** OpenOM is an open standard - MIT code, CC-BY spec (§G) - that embeds a small, broker-asserted data payload *inside* the OM PDF, using the same PDF/A-3 mechanism Factur-X uses for e-invoicing, and mirrors it as JSON-LD on the web. The broker asserts the deal's key facts once; every downstream party reads them instead of re-typing them out of a 40-page document.
- **Why it matters (per deal):** Today four or more parties - buyer, buyer's broker/analyst, lender, appraiser - each independently re-extract the same facts, each burning ~30–80k tokens of vision-model work on one 40-page OM, and each ending with a slightly different version of the numbers. OpenOM collapses that into one ~20–60k-token extraction at the source and ~2–5k-token reads downstream - **roughly 10–25× less per consuming party** - and produces one attributable, tamper-evident version of the deal's own figures. It also catches the OM's own math errors before anyone else sees them (§9). See §2 for the full cost model.
- **Why it lasts:** Token costs fall every year, so cheap extraction is the *hook, not the moat*. The durable value is **provenance** - a named party's dated, verifiable position on the deal (§10). That does not decay; if anything it compounds with adoption.
- **The ask:** ~15 real OMs across producers - the fixture *matrix*, not a count (§14) - to build and test against; the name decision (§15 Q1); and the free-vs-paid call before Milestone 3 (§15 Q2).
- **Status:** Nothing built yet; repo initialized. First code is the deterministic PDF round-trip (embed → read) on 3 real OMs, with the cross-implementation round-trip test wired in from day one (§8a, §B).


---

## Glossary

Terms of art used in this handoff, grouped for navigation.

### Commercial real estate

| Term | Meaning |
|---|---|
| **OM** | Offering Memorandum - the marketing/deal PDF a listing broker produces for a property. |
| **STNL** | Single-Tenant Net Lease - one tenant, net-lease structure. v0.1 scope. |
| **N / NN / NNN** | Net-lease grades by how many expenses the tenant covers (taxes, insurance, maintenance). NNN = tenant covers all three. |
| **absolute-net / gross / modified-gross** | Other `leaseTypeAsserted` values (§E). Absolute-net = tenant covers everything incl. roof/structure; gross = landlord covers operating expenses; modified-gross = split. |
| **NOI** | Net Operating Income - income after operating expenses; the numerator of the cap rate. |
| **noiType** | Whether NOI is **in-place** (actual, current leases) or **pro-forma** (projected). The disclosure most accuracy disputes hinge on. |
| **noiAsOfDate** | The date the asserted NOI is stated as of; required whenever `noi` is present (§E). |
| **Cap rate** | NOI ÷ price. The core valuation ratio. |
| **price/SF, rentPSF** | Price (or rent) per square foot - `askingPrice ÷ buildingSF`, `annualRent ÷ buildingSF`. Derivable; consistency-checked (§H). |
| **rentSchedule** | The modeled, per-period rent object (start/end, annual/monthly rent, escalation, abatement) - the standard's differentiator (§6d, §7d). |
| **escalation / escalationFromPrior** | The step-up in rent between consecutive periods, as a decimal fraction (0.10 = 10%). |
| **abatement** | A period of reduced or free rent within the schedule. |
| **options (ROFR / ROFO)** | Renewal options (count × length × escalation); Right Of First Refusal / Right Of First Offer to purchase. |
| **guarantor** | The entity backing the lease (corporate / personal / franchisee); distinct from the tenant entity. |
| **landlordResponsibilities** | The boolean set (roof, structure, parking, HVAC, taxes, insurance, CAM) that makes lease type *derivable and disputable* - kills "everything is NNN." |
| **buildingSF / lotAcres** | Gross building area (square feet) and land area (acres). |
| **OSCRE / RESO** | CRE / residential real-estate data-standards bodies; OpenOM *aligns with* their vocabularies for credibility, does not adopt wholesale (§3). |
| **Buildout / SharpLaunch / RCM / LightBox** | OM production & listing platforms - natural distribution partners (§5d), not competitors to the spec. |

### Format, JSON-LD & PDF mechanics

| Term | Meaning |
|---|---|
| **JSON-LD** | JSON for Linked Data - JSON with a shared vocabulary (`@context`) so machines agree on field meaning. |
| **`@context`** | The URL(s) defining the vocabulary a JSON-LD payload uses (schema.org + our custom namespace). Published `@context` URLs are immutable (§F). |
| **Factur-X / ZUGFeRD** | Franco-German e-invoicing standard: structured XML embedded in a PDF/A-3. The precedent we borrow the embedding mechanism from. |
| **/AF, AFRelationship** | PDF "Associated Files" mechanism - how an attachment is bound to a document with a declared relationship (`Data`). |
| **/Filespec, /EmbeddedFiles, /EF** | The PDF dictionaries that name and carry an embedded file: the file specification, the catalog name tree of embedded files, and the embedded-file stream reference (§D). |
| **XMP** | PDF metadata block; we store spec name, version, payload filename, and payload hash here (§D.2). |
| **/CheckSum** | The legacy PDF `/Params` field - an **MD5** digest of the uncompressed embedded bytes. **Not** the integrity mechanism; ignored for trust (§C, §D). |
| **SMask** | Soft mask - the alpha/transparency channel of a PDF image; must be recombined to recover RGBA. |
| **Image XObject** | The PDF object type that holds a raster image; extraction locates + decompresses these (§8b). |
| **CMYK / ICC / sRGB** | Print vs. profiled vs. standard-web color spaces; image extraction normalizes CMYK/ICC → sRGB (§8b). |
| **PDF/A-3** | Archival PDF profile that permits arbitrary embedded files. Our embedding is PDF/A-3-*style* (relaxed conformance in v1). |
| **application/ld+json** | The MIME type the embedded `om.json` stream declares (`/Subtype /application#2Fld+json`); consumers also accept `application/json` (§D.1). |

### Standard, canonicalization & provenance

| Term | Meaning |
|---|---|
| **JCS (RFC 8785)** | JSON Canonicalization Scheme - the exact byte form of a payload (UTF-8, sorted keys, no whitespace, canonical numbers) that makes cross-implementation hashing well-defined (§C). |
| **SHA-256 / integrity hash** | `sha256:<hex>` over the JCS bytes (signature key absent) - proves the payload is *unaltered since embed*; stored in XMP, not in the payload (§C). |
| **sourceDocHash** | A distinct SHA-256 over the *original source PDF bytes* - answers "which document does this payload describe," not "has the payload changed" (§C). |
| **payloadHash** | The XMP-stored integrity hash used for detection and tamper-evidence (§D.2). |
| **supersedes** | The prior `payloadHash` recorded on re-embed, so repricing *replaces* rather than stacks (§4, §D.3). |
| **assertedBy / assertedDate** | The named party (broker / brokerage / license #) making the assertion, and the date it is stated as of. Both required (§7a). |
| **source tag** | Per-field provenance: `asserted` (broker stated it) / `extracted` (pulled from doc, unreviewed) / `verified` (checked against an authoritative source) (§7a). |
| **four-layer provenance** | Hash + self-asserted identity + domain-origin verification + reserved signature field - the resolved trust model; each layer proves exactly one thing (§10). |
| **domain-origin verification** | Read-time proof that the OM and its JSON-LD mirror are served from a specific domain, via HTTPS/DNS - the web's own trust model. Free because consumer mode already has the URL (§10, layer 3). |
| **signature (reserved)** | The optional, empty-in-0.1 `meta.signature` field; cryptographic authorship is registry-era, required nowhere in 0.1 (§10, layer 4). |
| **idempotent (re-embed)** | Re-running embed replaces the payload in place (never a second `om.json`), bumps `assertedDate`, sets `supersedes` (§4, §D.3). |
| **specVersion / SemVer** | The payload's spec version, governed by Semantic Versioning: additive = minor, breaking = major + new `@context` URL (§F). |
| **RFC 2119 / RFC 8174** | The source of the normative keywords (MUST/SHOULD/MAY…) used throughout Part II; only uppercase forms are normative. |
| **Producer / Consumer / Validator** | The three conformance roles an implementation may claim; it is judged against each role it claims (§A, [OM-CONF-004]). |
| **conformance vectors** | The committed test payloads, expected JCS/hash/report outputs, and golden PDFs in `/spec/vectors/` that every implementation must reproduce (§B). |
| **error / warning taxonomy** | Stable, append-only codes: `OMV-E###` errors **block** embed; `OMW-W###` warnings **never** block (§H). |
| **cross-implementation round-trip** | The named test that a payload embedded by `/js` (pdf-lib) reads byte-for-byte identically under `/core` (pikepdf) and vice versa - the bug that silently kills a standard (§8a, §B). |
| **validator-as-trojan-horse** | Shipping the schema-independent consistency checker early, as standalone free value, to seed usage before embedding matters (§9). |

### Infrastructure, protocol & tooling

| Term | Meaning |
|---|---|
| **MCP** | Model Context Protocol - the agent tool-access standard the server exposes; one deterministic server reaches every major client (§6b). |
| **stdio / Streamable HTTP** | The two MCP transports: local pipe (stdio) and hosted remote (Streamable HTTP), needed for ChatGPT/web reach (§6b). |
| **FastMCP** | The Python library the thin MCP wrapper is built on. |
| **MV3** | Manifest V3 - the current Chrome extension platform. |
| **Prompt API / Gemini Nano** | Chrome's on-device model API used for free, private, local extraction - the document never leaves the machine (§5b path 1). |
| **Presigned upload** | A time-limited URL that lets a client upload a file directly to storage without server credentials. |
| **blob / blob id / R2** | An uploaded file object, its identifier, and the object store (Cloudflare R2) holding it, subject to a retention TTL (§6d, §K). |
| **HMAC** | Keyed hash used to sign the webhook body with a per-webhook shared secret so receivers can verify authenticity (§5b, §J). |
| **webhook envelope / envelopeVersion** | The versioned JSON wrapper POSTed to a receiver's URL (event, timestamp, verification, payload); versions independently of `specVersion` (§5b, §F). |
| **SSRF / DNS rebinding** | Server-Side Request Forgery and the rebinding variant - the re-fetch/webhook attack class the range rules and resolve-then-pin mitigate (§J). |
| **decompression bomb** | A small compressed payload/stream that expands enormously; capped by size + ratio limits before parsing (§J). |
| **pikepdf / PyMuPDF / jsonschema / typer** | Python core libraries: PDF read-write, render/inspect/image extraction, schema validation, CLI. |
| **pdf-lib / ajv / pdf.js** | JS subset libraries: PDF embed/read, JSON Schema validation, PDF text extraction. |
| **DoD (definition-of-done)** | Per-milestone exit criteria; two-tier - a technical DoD that *gates* the milestone and an adoption DoD that is *tracked* but does not gate (§14). |

### Project entities

| Term | Meaning |
|---|---|
| **Vervelio** | The neutral steward that publishes and governs the standard (§L). |
| **Fortis** | First adopter and seed-corpus source; not the publisher. |
| **Phil** | The reference consumer, wired in as an ordinary configured webhook - neutral in code, first-party in usage (§5b). |
| **OpenOM / omspec** | Working-title name (not locked) for the standard, and the RECOMMENDED XMP/vocabulary prefix. Name sweep is P0 (§15 Q1). |


---

## 1. What this is

An open standard + toolchain that embeds a machine-readable, broker-asserted data payload inside commercial real estate offering memorandum PDFs, and exposes the same payload as JSON-LD on the web. **The code (`/core`, `/cli`, `/mcp`, `/js`, `/extension`) is MIT; the specification text, JSON Schema, `@context`/vocabulary, and conformance vectors are CC-BY-4.0 attributed to Vervelio (§G)** - deliberately split so implementers can embed the schema and context without code-notice obligations while the standard's provenance stays clear. One assertion at the source, infinite cheap, consistent consumption downstream.

Deliverables from one codebase:
1. **Engine** - Python library + CLI (deterministic PDF/data verbs)
2. **MCP server** - dual transport (stdio + hosted Streamable HTTP), works in any MCP client
3. **Process layer** - Claude Skill + generic agent-instructions file (the extraction playbook)
4. **JS subset** - TypeScript package: embed/read/validate, powering the Chrome extension
5. **Chrome extension** - dual persona: author mode (broker embeds) + consumer mode (anyone detects, views, routes payloads)

---

## 2. Vision & strategic thesis (the "why" - do not lose this)

**The problem.** OMs are human-readable PDFs. Every consumer - buyer, buyer's broker, lender, analyst, LLM agents - re-extracts the same facts (price, cap rate, NOI, lease terms) from scratch. A 40-page OM through a vision model is ~30–80k tokens, slow, lossy. Multiply by every party on every deal. Worse, each re-extraction can read the document differently - there is no single, authoritative, attributable version of the deal's own numbers.

#### Problem quantification (the cost of re-extraction, per deal)

Model one STNL deal - a ~40-page OM - with four independent downstream readers (buyer, buyer's broker/analyst, lender, appraiser; a conservative count). The status-quo cost is *multiplicative in parties*; OpenOM makes it *constant in the deal*.

| Axis | Status quo (re-extract, every party, every read) | With OpenOM |
|---|---|---|
| **Tokens** | ~30–80k per party for a vision pass over 40 pages × ~4 parties ≈ **120–320k tokens/deal**, repeated on every re-read | **~20–60k once** at the source (embedder) + **~2–5k per downstream read** |
| **Per-party read** | a full ~50k-token vision pass, *every time* | a ~3k-token payload read - **roughly 10–25× less (≈16× at midpoint)** |
| **Latency** | a seconds-to-minutes vision pass blocks each agent before it can act | sub-second structured read |
| **Consistency** | up to 4 independently-extracted readings of the same numbers; none authoritative | one canonical, SHA-256-verified version (§C) every party reads |
| **Error surfacing** | the OM's own arithmetic faults (cap ≠ NOI÷price, rent-schedule sums, term math) surface late - in diligence, separately, per party | caught once at assertion by the consistency checker (§9, §H) before the OM ships |

The waste is that the *same document* is re-extracted by *every party* on *every deal*, forever - an O(parties × deals) cost. Embedding the payload once at the source collapses it to O(deals): one extraction, then near-free reads. As the deal is re-priced and re-circulated over its marketing life, the multiplier only grows - which is exactly the surface the idempotent re-embed (§4) and the ~2–5k `om_read` (§6c) are designed for.

**The move.** Embed a canonical, broker-asserted payload in the PDF itself, and mirror it as JSON-LD on the web. Precedent: Factur-X / ZUGFeRD - structured data embedded in PDF/A-3, which went from open spec to legal e-invoicing mandate. Same move for CRE OMs.

### The thesis, provenance-first

1. **Provenance is the durable value: broker-asserted, attributable, tamper-evident.** The payload is a named party's stated position on the deal, tied to a date, carried inside the document and verifiable at its source. "Attributable + tamper-evident" here means: you can tell *who published it*, *when*, and *that it hasn't been altered since* - **not** that anyone signs it cryptographically (see §10 for exactly what each layer proves, and what it doesn't). This value does not decay.

2. **Token asymmetry is the immediate hook.** The listing broker pays extraction once (~20–60k tokens in their existing AI client, or free on-device via the extension). Every downstream agent forever reads a ~2–5k broker-asserted payload. *"Make your deal legible to the buy-side's AI."* Token costs fall every year, so this is the reason they *try* it - provenance is the reason it *lasts*.

3. **The spec is the product; the tool is a commodity.** What compounds: versioned schema, JSON Schema validator, vocabulary namespace, governance, conformance tests. Ship `omspec 0.1` *with* the tool.

4. **Two-sided flywheel.** Author mode creates supply; consumer mode creates visible demand - buy-side tools lighting up on embedded OMs give listing brokers a reason to embed, and give buyers' brokers a reason to *ask* for embedded OMs.

**End state.** (a) Agents check for the payload first; vision fallback only on unembedded docs. (b) The standard becomes the substrate for a distributed, free-market MLS - JSON-LD listing pages + embedded payloads, crawlable by anyone, no central gatekeeper. Consumer-mode "submit to index" means the registry builds itself from the demand side (§11). Prerequisite for that stage: stronger provenance (§10) - an open MLS with no origin verification is a spam magnet.

**Why now.** The window is open because three things are newly true: buy-side brokers, lenders, and analysts now routinely run OMs through LLM agents, so the payload finally has a reader; the embed mechanism is de-risked (Factur-X took the same PDF/A-3 pattern from open spec to legal e-invoicing mandate, §3); and on-device models (Chrome Prompt API / Gemini Nano) plus MCP make free, private, client-side extraction reachable across every major agent client (§5b path 1, §6b) - answering the confidentiality objection that once blocked broker adoption.

**Neutrality.** Published under Vervelio, not Fortis. Fortis = first adopter, seed corpus, reference consumer (via Phil).

---

## 3. Landscape & positioning (who else, and why this is open)

The first question any stakeholder asks is "who else does this, and why hasn't it been done?" Short answer: adjacent players standardize *data* or *extract* it - none **embed an attributable payload at the source and verify it at the point of consumption.** That gap is the wedge.

| Player | Category | What they do | What they don't do (our wedge) |
|---|---|---|---|
| **OSCRE** | Data-model standards body | Publishes the OSCRE Industry Data Model - reference data definitions/dictionaries for CRE, member-governed. | Defines *terms*, never binds them to a document instance: no embed, no per-document provenance, no point-of-consumption verification; access is membership-gated. We align field *names* with the IDM for credibility (§7b); we do not adopt the model wholesale. |
| **RESO** | Data-model + API standards body | Data Dictionary + RESO Web API (OData) - the residential MLS interoperability layer. | Residential-first; models a listing as a *record in a queried database*, not an attributable artifact traveling inside the deal document. Nothing is embedded, nothing is provenance-verified at read time, CRE net-lease coverage is thin. We borrow names, not the transport. |
| **Buildout** | OM production + syndication | Generates the OM PDF and syndicates listings from a broker's CRM. | The structured data that *produced* the PDF stays in Buildout's database; the file that leaves carries none of it. No in-file payload, no portable assertion, no consumer-side verification. Natural embed-at-export partner (§5d), not a spec competitor. |
| **SharpLaunch** | Marketing platform | Listing microsites + OM/flyer generation + email campaigns. | Same structural gap as Buildout: the site and the PDF are outputs; no machine-readable, attributable payload survives the file leaving the platform. |
| **RCM (Real Capital Markets) / LightBox** | Investment-sales marketplace | Deal marketing, virtual deal rooms, and analytics for investment sales; now under LightBox. | A walled garden: deal data is portable only *within* RCM. Nothing is embedded in the OM for the open web; there is no neutral, cross-platform payload a non-RCM party can read. |
| **Crexi / CoStar** | Aggregating marketplaces / data platforms | Aggregate listings and market data behind login and platform terms. | They *host and consume* listing data; they do not emit a portable, self-describing artifact a broker owns and rehosts anywhere. This is precisely the incumbent-capture risk (§12) that an open MIT spec under a neutral steward answers. |
| **Dealpath** | Buy-side deal management | Ingests deal data into one firm's private pipeline/workspace. | Proprietary internal model; every firm re-ingests separately. Nothing is asserted *at the source* or shared across parties. A downstream **consumer** of our payload, not a producer of one. |
| **Primer / V7 / document-AI platforms** | Document extraction | Pull structured fields *out of* PDFs into the operator's own store (auto-labeling, doc pipelines). | Extraction happens N times - once per consumer - unattributed, into walled gardens; no source-of-truth assertion, no provenance, results not portable. We move that one extraction to the source and make it a *named assertion* (§7a). |
| **Ad-hoc vision-model pipelines** (GPT/Claude/Gemini over the raw OM) | Per-read extraction | Re-extract facts from the 40-page PDF on every read (~30–80k tokens). | Highest per-read cost, non-deterministic across runs *and* across models, no attribution, no integrity check. This is exactly the fallback the embedded payload eliminates (§2 end-state (a)). |
| **Factur-X / ZUGFeRD** | Embedded-data e-invoicing standard | Structured XML in PDF/A-3 for invoices; open spec that became an EU legal mandate. | Not real estate; an invoice is a settled fact, not a dated *opinion*, so there is no assertion/attribution semantics and no read-time origin-verification model. We borrow the embedding mechanism and the open-spec→mandate playbook (§2); we add opinion semantics (§7a) and domain-origin verification (§10). |

The wedge on four axes - the capabilities that jointly define OpenOM and that no adjacent player combines (✓ = yes; ◐ = partial / adjacent only; ✗ = no):

| | Embeds payload **in the document** | **Attributable** (named party + date) | Verifiable **at point of consumption** | **Open & portable** (no login/license to read) | Models CRE **net-lease rent schedule** |
|---|:--:|:--:|:--:|:--:|:--:|
| **OpenOM** | ✓ | ✓ | ✓ | ✓ | ✓ |
| OSCRE | ✗ | ✗ | ✗ | ◐ (terms, member-gated) | ◐ |
| RESO | ✗ | ✗ | ✗ | ◐ (API, licensed) | ✗ |
| Buildout / SharpLaunch | ✗ | ✗ | ✗ | ✗ | ✗ |
| RCM/LightBox · Crexi · CoStar | ✗ | ✗ | ✗ | ✗ | ✗ |
| Dealpath | ✗ | ✗ | ✗ | ✗ | ◐ (internal) |
| Primer / V7 / document-AI | ✗ | ✗ | ✗ | ✗ | ✗ |
| Factur-X / ZUGFeRD | ✓ | ◐ (issuer, not opinion) | ✗ | ✓ | ✗ (invoices) |

**Read the matrix as one sentence:** others standardize a vocabulary, *or* extract into a silo, *or* embed for a different domain - none **embed an attributable, opinion-typed payload at the source, verify it at the point of consumption, and leave it open and portable.** That intersection is the whole product.

**Positioning stance:** OpenOM is the *interoperability layer*, not another extractor or platform. We're OSCRE-aligned on vocabulary, Factur-X-derived on mechanism, and neutral on governance (Vervelio). The thing that is ours and defensible: **attributable provenance embedded in the document + verified at the point of consumption**, plus the first properly modeled **rent schedule** (§6d).

---

## 4. The canonical workflow loop (adoption motion)

> **Generate OM → run it through the tool → rehost the embedded OM.**

Design consequences:
1. **Near-zero friction.** One command / one click / one agent instruction; slots behind existing OM producers unchanged.
2. **Non-destructive embed.** Visually identical output; preserves quality, bookmarks, links; no content recompression.
3. **Idempotent update semantics.** Price reductions are the most common re-embed event. Re-embed *replaces* the payload (never stacks), bumps `assertedDate`, records `supersedes` = prior payload hash. Repricing is a first-class operation - and note it involves **no signing step** (§10), so it stays a one-click op.
4. **Survival rules.** The `/AF`+EmbeddedFiles attachment (§8a, §D) survives byte-preserving transport but is destroyed by any operation that re-writes the PDF's structure. Preserving vs destroying is not a judgment call - it is a property of whether the file's bytes (or at least its catalog, name tree, and streams) pass through intact. The matrix below is exhaustive for v0.1; **the single rule that follows from it is: rehost the embedded file itself; never re-export.** `om_inspect(url)` / `om_read(url)` re-verify survival at any point (normative: OM-FLOW-002).

   | Operation | Payload survives? | Why |
   |---|:--:|---|
   | HTTP host → download → re-upload (same bytes) | ✓ | Byte-preserving; the survival test case in §14 M1. |
   | Email as an attachment (ordinary MTA) | ✓ | Attachment bytes untouched. |
   | Cloud-storage sync (Drive / Dropbox / Box / OneDrive) | ✓ | Stored as an opaque blob. |
   | Slack / Teams file share, CDN passthrough | ✓ | Blob delivery, no re-encode. |
   | Rename / copy / move | ✓ | Filesystem metadata only. |
   | qpdf / linearization for Fast Web View | ✓ | Structure-preserving; attachments and name tree retained. |
   | **Re-export / "Save as PDF" / "Print to PDF"** (any app) | ✗ | Produces a *new* document; `/AF`, `/EmbeddedFiles`, and XMP are not carried. |
   | **Flatten / "reduce file size" / aggressive optimizer** | ✗ | Optimizers routinely drop embedded-file streams and the name tree. |
   | **PDF → image → PDF, or OCR re-write** | ✗ | Rebuilds the file from rendered pages; attachments gone. |
   | **Email/security-gateway CDR (content disarm & reconstruction)** | ✗ | Sanitizers strip embedded files *by design*; the most easily missed destroyer - treat any CDR'd channel as lossy and rehost from origin. |
   | "Save a copy" in some viewers (e.g. Preview re-save) | ⚠ verify | Viewer-dependent; MUST be verified with `om_inspect`, never assumed. |

   A Producer or Consumer MUST NOT assume survival across any ✗ or ⚠ row; the only guaranteed-durable action is rehosting the original embedded bytes.
5. **Rehosted URL = crawl surface.** `om_read(url)` works for any agent; same payload emitted as JSON-LD in listing-page markup. This rehosted URL is also what makes **domain-origin verification** free (§10).

### Future scope: the in-document badge (parked, captured)
Small visual mark on the OM (footer of page 2 or cover) - Factur-X logo convention. Opt-in flag only. Overlay stamp, spec name + version, possibly QR to public validator. Consumer-mode link badging (§5b) achieves much of this without modifying the document.

---

## 5. Integration surfaces (getting into their build process)

Four surfaces, lowest friction → deepest integration.

### 5a. CLI / watch folder (ships with engine, free)
`om embed` in a script/CI, or a watcher on an "OM outbox" folder - coordinator exports into the folder, embedded file appears in "ready." Zero UI. Also the server-side path for platforms.

### 5b. Chrome extension (the human-facing surface - two personas)

MV3. Shared foundation: `/js` subset (pdf-lib embed/read, ajv validate, pdf.js text), side panel UI, chrome.storage.sync settings.

#### Consumer mode (ships first - fully deterministic, no inference)
*Anyone browsing encounters an embedded OM; the extension detects, displays, verifies, routes.*

- **Detection mechanics:** content scripts cannot inspect Chrome's built-in PDF viewer internals. Instead the extension knows the URL of the viewed PDF, re-fetches the same bytes itself (typically from HTTP cache - no real second download), and parses with the JS subset (EmbeddedFiles + /AF + XMP marker). Same UX, different plumbing. **Detection re-fetches bytes; it never scrapes the viewer.**
- **Trigger:** tab URL is a PDF → auto-check (setting, with size cap) or check-on-panel-open. Toolbar badge: payload present / absent / hash-mismatch / **origin-verified** (§10).
- **Payload card (side panel):** instant deal screen - address, price, cap, NOI + noiType, tenant, guarantor, remaining term, options - plus assertedBy/assertedDate, hash + origin verification status, validation warnings. The "40 pages → 4 seconds" demo moment.
- **Publish (routing) - v1 is deliberately simple:**
  - **Generic webhook:** POST payload JSON to any URL + optional bearer token. Covers Zapier/Make/n8n → every CRM, Sheets, Slack, Airtable - zero connectors built.
  - **Copy JSON / download .json.**
  - **No presets, by design.** Every brokerage has a different database; the webhook is the universal adapter. Users configure multiple named webhooks with a test-fire button. Phil is simply a webhook URL Fortis brokers configure - neutral in code, first-party in usage.
  - **Webhook envelope + security contract** (receiving systems build against this; it versions independently of the spec via `envelopeVersion`, additive-only within a major, OM-VER-005). The **normative contract is §Y (OM-HOOK-###)**; the shape and the security summary here are its illustrative front door.
    ```json
    {
      "envelopeVersion": "1",
      "event": "om.payload.published",
      "id": "d1f9c0a2-8b3e-4a1d-9c77-2b6e5f0a4c11",
      "publishedAt": "2026-08-15T14:00:00Z",
      "sourceUrl": "https://example.com/listings/1000-example-rd.pdf",
      "specVersion": "0.1",
      "payloadHash": "sha256:9f2b…c4",
      "verification": { "hashValid": true, "originVerified": null, "signatureValid": null },
      "payload": { "@context": ["https://schema.org", "https://openom.app/ns/0.1"], "…the om.json…": "…" }
    }
    ```
    Security summary (exact rules in §Y):
    - **HMAC-SHA256 over the raw transmitted body**, prefixed by the timestamp: the sender signs `"<unix-ts>." + <raw JSON bytes>` and sends `OpenOM-Signature: t=<unix-ts>,v1=<hex>`. Receivers recompute over the *raw* bytes (before JSON parsing) and compare in constant time.
    - **Replay protection:** `OpenOM-Timestamp` (unix seconds) is inside the signature; receivers reject deliveries outside a **±300 s** default window and SHOULD dedupe on the event id.
    - **Idempotency:** `id` (== `OpenOM-Event-Id`, a UUIDv4) is stable across all retries of one event; delivery is **at-least-once**, so receivers MUST treat a repeated `id` as a no-op.
    - **Secrets are device-local:** per-webhook shared secrets live in `chrome.storage.local`, never `chrome.storage.sync` (OM-SEC-003).
    - **Versioning:** `envelopeVersion` bumps independently of `specVersion`; receivers MUST tolerate unknown additive fields.
  - **Future: "Submit to index"** - consumer extensions surface embedded OMs into the public registry (opt-in; hash- and origin-verified, later signature-verified). See §11.
- **Link-level detection (optional, per-domain opt-in):** content script badges PDF *links* on listing pages via an HTTP Range request on the file tail (cheap heuristic; confirmed on click). Opt-in, cache results.
- **Local files:** require the user's "Allow access to file URLs" toggle - onboarding step, documented.

#### Author mode (ships second - needs extraction assist)
*Listing broker captures, extracts, reviews, asserts, embeds.*

- **Capture:** download interception (buildout.com + user-added domains) → toast; context menu / toolbar on any PDF.
- **Flow:** extract → **review/edit fields** → validate (errors block, warnings inform) → **Assert & Embed** → save for rehosting.
- **Extraction paths (ship progressively; author mode / process layer ONLY - none of these run in `/core`, the open MCP server, or consumer mode, per §6a).** Every path drains into the *same* review panel, and the panel's output only becomes an assertion at Assert & Embed (§7a, OM-EXTP-003). The determinism boundary column states, unambiguously, where inference is permitted.

  | # | Path | Inference runs | Doc leaves device? | Network egress | Cost / tier | Accuracy | Precondition | Determinism boundary | Failure → fallback |
  |---|---|---|:--:|---|---|---|---|---|---|
  | **0** | **Manual / review-only** | none | No | none | free | human-limited | always available | Fully deterministic - the panel is `/js` only. The floor that guarantees author mode always works with zero inference. | n/a (is the fallback) |
  | **1** | **Local on-device** (Chrome Prompt API / Gemini Nano) | on device | **No** | **none** | free | good; weak on messy rent schedules (net = review panel + §9 warnings) | Prompt API present (verify at build, §15 Q6) | Inference is on-device, outside `/core`/server/consumer; answers the "won't upload my unreleased OM" objection (§12). | model unavailable / low-confidence → path 0 |
  | **2** | **Hosted extraction** (Vervelio endpoint) | Vervelio server | **Yes** (presigned upload) | presigned PUT → Vervelio | commercial-tier candidate (§15 Q2) | best | account + upload consent | Separate commercial service - **never the open server** (§6a). Subject to retention (OM-PRIV-002) and SSRF/blob rules (OM-SEC-001/006). | upload/extract error → path 1 or 0 |
  | **3** | **Chat handoff** (broker's own AI subscription via MCP connector) | broker's own AI provider | **Yes** (to their provider, under their ToS) | to broker's AI, never through Vervelio (OM-PRIV-001) | broker's existing subscription | provider-dependent | deep-link + logged-in client (§15 Q6) | Their assistant drives our MCP tools; **we never drive their assistant** (no chat-UI puppeteering, §7 hard rule). | connector/link failure → path 1 or 0 |

  *The assistant drives the tool; we never drive the assistant.* The extension MUST disclose which path an action uses, and whether the document leaves the device, **before** it leaves (OM-EXTP-002, OM-PRIV-001).
- **HARD RULE - no chat-UI puppeteering.** No injecting into / scraping logged-in ChatGPT/Claude sessions: ToS, fragility, account risk. Paths 1–3 achieve the outcome legitimately.
- **Review panel = the assertion gate.** Extraction output only *becomes* a broker assertion when a human reviews and clicks Assert & Embed.

**Architecture impact:** the TS subset (embed/read/validate) is required (`/js`); extraction stays wherever inference lives.

### 5c. Agentic browsers (Claude in Chrome, etc.)
In-browser agents run the loop as a shortcut/Skill against the MCP. Document in `/process`; no bespoke surface.

### 5d. Buildout partnership / API (endgame for this channel)
One native integration = thousands of brokerages embedding at export. Approach as Vervelio (neutral steward), not Fortis. Extends to SharpLaunch, RCM/LightBox, in-house shops via 5a. Timing: after 0.1 + tooling + traction.

---

## 6. Architecture

### 6a. Layers, one repo

| Layer | Form | Purpose | Distribution |
|---|---|---|---|
| Engine | Python lib + CLI, MIT | Deterministic verbs | GitHub (Vervelio org) + PyPI |
| MCP server | Thin wrapper, dual transport | Agent access, any client | stdio (pipx) + hosted Streamable HTTP (Vervelio) |
| Process layer | SKILL.md + agent instructions | Extraction/mapping playbook | Skill (Claude) + AGENTS-style doc |
| JS subset | TS: embed/read/validate | Extension + web/Node consumers | npm |
| Extension | MV3, consumer + author modes | Detect/view/publish + capture/review/embed | Chrome Web Store (Vervelio) |

**Cardinal rule: the open server, the core, and consumer-mode JS stay deterministic - zero inference, ever.** No keys, no per-call costs, trivial hosting, testable. LLM mapping runs client-side or on-device, guided by the process layer. Hosted inference-included extraction, if offered, is a separate commercial service - never the open server.

This rule is **normative and CI-enforced**, not aspirational: §V ([OM-ARCH-001..007]) fixes the exact deterministic layer set, forbids inference dependencies via a committed denylist scanned on every build, bounds network egress, and makes the edge→core dependency strictly one-directional. A build in which a deterministic package can reach an inference client through any path fails.

### 6b. Client compatibility target

| Client | Transport | Notes |
|---|---|---|
| Claude (web/desktop/mobile) | remote; desktop also stdio | + Skill |
| Claude Code / Cowork | stdio + remote | primary dev surface |
| ChatGPT | remote only | why remote ships at launch |
| Gemini (CLI) | stdio + remote | web-app connectors: verify |
| Copilot (VS Code agent mode) | stdio + remote | |
| Local LLMs (LM Studio, Continue, LibreChat…) | stdio | |
| Chrome (extension) | n/a - JS subset; Prompt API / hosted / chat-handoff | §5b |

### 6c. Token model
Server: zero inference, no keys. Client cost = context tokens on tool outputs; subscription users see normal usage limits, no API billing; extension local/consumer paths: zero tokens. Heavy op = one-time embedder extraction; consumers get ~2–5k `om_read`. Tools return compact outputs - text paginates, images return manifests + links.

### 6d. Remote file I/O
Remote can't reach client filesystems: tools accept HTTPS URL or presigned upload (→ blob id); outputs as download links, payload inline. stdio: plain paths. Path-or-URL polymorphic. Blobs: R2. Retention policy needed (§15 Q4).

---

## 7. The spec (design philosophy first)

### 7a. Assertions, not facts
An OM is an advocacy document: broker opinion of value + seller expectations. The payload encodes **assertions by an identified party as of a date**:
- `assertedBy` (broker, brokerage, license #) + `assertedDate` **required**.
- `noiType: "in-place" | "pro-forma"` **required** + `noiAsOfDate` - forces the disclosure most accuracy disputes are actually about.
- Labels derivable, not asserted: `landlordResponsibilities` boolean set (roof, structure, parking, HVAC, taxes, insurance, CAM) makes lease type *derivable and disputable* - kills "everything is NNN."
- **Per-field provenance tag.** Each substantive field carries a `source` of `asserted` (broker stated it), `extracted` (pulled from the doc, unreviewed), or `verified` (checked against an authoritative source). This operationalizes "assertions, not facts" at the field level and lets consumers weight fields. Default on embed is `asserted` (the review gate makes it so).
- Payloads SHOULD be human-reviewed before embed (extension review panel operationalizes).
- Tooling checks internal consistency, never market truth (§9).

### 7b. Format & governance
- **JSON-LD only** (XML dropped - no identified consumer).
- `@context`: schema.org (`RealEstateListing`, `Offer`, `Place`, `PostalAddress`, `Organization`) + custom vocab (capRate, noi, rentSchedule, guarantor, options…). Rent schedules unmodeled anywhere else = the opportunity.
- `"specVersion": "0.1"` + published JSON Schema.
- Borrow RESO/OSCRE names for credibility; don't adopt wholesale.
- Name TBD - reserve GitHub org + PyPI + npm + Chrome Web Store + domain as a set before code (§15 Q1, P0).

### 7c. v0.1 scope (confirmed)
STNL, N through NNN, retail/QSR/pharmacy. Multi-tenant/industrial/office later.

### 7d. Field sketch (moving toward the real schema)
- **Property:** address (parsed + geo), APN, building SF, lot, year built/renovated.
- **Deal:** asking price, cap rate, NOI + noiType + noiAsOfDate, price/SF, status.
- **Lease:** tenant entity, guarantor + type, `landlordResponsibilities` booleans, asserted lease type, commencement, expiration, remaining term, **`rentSchedule`** (modeled below), escalations, options, ROFR/ROFO.
- **Parties:** listing broker(s), brokerage, license #s, contact.
- **Meta:** specVersion, assertedBy, assertedDate, sourceDocHash, supersedes, **`signature` (optional, reserved - see §10)**, imageRights (optional).

**Modeled `rentSchedule`** (the differentiator - it must be a real object, not prose). Each period:
```json
{
  "periodStart": "2024-05-01",
  "periodEnd": "2029-04-30",
  "annualRent": 115625,
  "monthlyRent": 9635.42,
  "rentPSF": 12.70,
  "escalationFromPrior": 0.10,
  "abatement": null,
  "source": "asserted"
}
```
Rules: periods are contiguous and non-overlapping (a consistency warning fires otherwise, §9); `rentPSF` derivable from `annualRent ÷ buildingSF` (mismatch → warning); `escalationFromPrior` cross-checks against the prior period's `annualRent`.

### 7e. Sample payload (illustrative - fictional deal)
```json
{
  "@context": ["https://schema.org", "https://openom.app/ns/0.1"],
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
      { "periodStart": "2024-05-01", "periodEnd": "2029-04-30", "annualRent": 115625, "rentPSF": 12.70, "source": "asserted" },
      { "periodStart": "2029-05-01", "periodEnd": "2034-04-30", "annualRent": 127188, "rentPSF": 13.98, "escalationFromPrior": 0.10, "source": "asserted" }
    ],
    "options": [ { "count": 4, "lengthYears": 5, "escalation": "10% per option" } ]
  },
  "meta": { "sourceDocHash": "sha256:…", "supersedes": null, "signature": null }
}
```

### §7e.1 The sample as a conformance vector (worked validation)

The §7e payload is a **normative interop vector**, committed to `/spec/vectors/payloads/sample-stnl-nnn.json` with its JCS form and `sha256:` hash in `/spec/vectors/expected/` (§B, [OM-VEC-001]). With §E + §E.1 in force it uses **only defined fields** (`apn`, `yearBuilt`, `guarantor.{name,type}`, `tenantEntity`, `commencement`, `expiration`, `options[].{count,lengthYears,escalation}` are all now in the dictionary), and it MUST validate with **zero errors and zero warnings**:

| Check | Code | Result |
|---|---|---|
| Required fields present (`specVersion`, `assertedBy.*`, `assertedDate`, `noiType`+`noiAsOfDate`, `meta.supersedes`) | `OMV-E001`/`OMV-E002` | pass |
| `meta.signature` is `null` (reserved, not populated) | `OMV-E003` | pass (see below) |
| cap rate 0.0625 vs NOI ÷ price = 115625 ÷ 1850000 = 0.0625 | `OMW-W010` | exact, no warn |
| year-1 `annualRent` 115625 = stated NOI 115625 | `OMW-W020` | exact, no warn |
| periods contiguous (…2029-04-30 → 2029-05-01…), non-overlapping | `OMW-W021`/`W022` | pass |
| `escalationFromPrior` 0.10 vs 127188 ÷ 115625 − 1 ≈ 0.09999 | `OMW-W023` | within tolerance |
| `rentPSF` 12.70 vs 115625 ÷ 9100 ≈ 12.706; 13.98 vs 127188 ÷ 9100 ≈ 13.977 | `OMW-W024` | within tolerance |
| `leaseTypeAsserted` NNN with all `landlordResponsibilities` = false | `OMW-W040` | consistent, no warn |

**Signature clarification (removes a latent self-contradiction):** `meta.signature: null` is **not** "populated". Per [OM-ERR-003] (§X.2) `OMV-E003` fires only for a *non-null* `signature` object; `null` and an absent key are both conformant in 0.1 ([OM-DD-003]). For hashing, the `meta.signature` key is removed entirely from `payload_for_hash` regardless of whether it is `null` or absent ([OM-CANON-003]), so the presence of `"signature": null` in the stored payload does not affect `omspec:payloadHash`.

---

## 8. PDF mechanics

### 8a. Embedding
- `om.json` as PDF embedded file + /AF, `AFRelationship = Data` (Factur-X mechanism). XMP block: spec name, version, payload filename, payload hash.
- Pragmatic v1: PDF/A-3-*style*, strict conformance later.
- **Update semantics:** detect existing → replace attachment, update XMP, set `supersedes`. Never duplicate.
- Consumer path: /AF + XMP → attachment → schema validate. Fallback: full extraction.
- **Cross-implementation round-trip test:** pdf-lib output readable by pikepdf and vice versa, byte-for-byte payload fidelity. The kind of bug that silently kills a standard - named test from day one.

### 8b. Image extraction (settled: yes, no rendering)
Raster images = Image XObjects; extraction = locate + decompress (PyMuPDF primary; poppler `pdfimages -list` cross-check). Handle: SMasks (→RGBA), CMYK/ICC→sRGB, tiled/striped images (InDesign), dedupe by xref, vector content (paths → render fallback only), scanned/flattened (full-page image per page). `om_inspect` classifies native/hybrid/scanned up front. Third-party photo licenses → imageRights field.

### 8c. Libraries
Python: pikepdf, PyMuPDF, jsonschema, typer, FastMCP. JS: pdf-lib, ajv, pdf.js.

---

## 9. MCP tool surface + validation philosophy

| Tool | Signature | Notes |
|---|---|---|
| `om_inspect` | pdf(path\|url) → profile | class, pages, payload present + version?, image inventory, text coverage |
| `om_extract_text` | pdf, page_range → text + tables | paginated |
| `om_extract_images` | pdf → manifest + links/paths | SMask, dedupe, colorspace |
| `om_read` | pdf(path\|url) → payload \| null | hash + origin verify; the cheap consumer path |
| `om_validate` | payload → report | two-tier below |
| `om_embed` | pdf, payload → new pdf | invalid = refuse; warnings never block; §8a semantics |

### Validation: two tiers, hard boundary
1. **Errors (block):** JSON Schema violations. (Schema ships in M2.)
2. **Warnings (never block):** internal consistency - NOI ÷ price vs cap rate, rent-schedule sums and contiguity, date/term arithmetic, price/SF, continuity. Self-contradiction is data-quality regardless of opinion.
3. **Out of scope forever:** market truth (§10 Non-goals).

**Validator as trojan horse - split, not deferred.** The consistency-warning tier is schema-independent and independently valuable (OMs fail their own math constantly). Ship it as a **standalone free checker early**, before anyone cares about embedding - it's the cold-start lever. The schema-error tier lands with M2 when the schema exists. Do not force an artificial "M1.5"; the two tiers simply mature on different milestones.

Orchestration: inspect → extract → agent/on-device maps → human review → validate → embed → rehost → (consumer: detect → verify → publish).

---

## 10. Trust / provenance - the four-layer model (resolved)

Provenance is the thesis (§2), so this section is load-bearing. The design deliberately **requires no cryptographic signing at day one or at re-embed.** Each layer proves exactly one thing; be honest about what each does *not* prove.

| Layer | Ships | Proves | Does NOT prove |
|---|---|---|---|
| **1. Embedded hash** (in XMP) | Day one | The payload has not been altered since embed; travels inside the file everywhere. | Who created it; that it wasn't re-embedded by someone else. |
| **2. Self-asserted identity** (`assertedBy` + license + date) | Day one | The *claim of authorship* is on the record, tied to a named party and license #. | That the identity is real (nothing verifies the license by itself). Honestly labeled **unverified**. |
| **3. Domain-origin verification** (read-time) | With consumer mode (M5a) | That the OM is published at, and its JSON-LD mirror served from, a specific domain - "asserted by whoever controls this domain," via HTTPS/DNS, the web's own trust model. Free, because consumer mode already has the URL. | The legal identity behind the domain; survives poorly if the file is rehosted elsewhere (which is arguably correct - verification is meaningful at origin). |
| **4. Signature** (optional field, reserved) | Field reserved day one; verification is registry-era | Cryptographic authorship + integrity once a key infrastructure exists. | Nothing yet - reserved and empty in 0.1. |

**Why this design (the Scott-aligned reasoning):**
- A signature proves *who* and *unaltered-since*, not *true*. It does nothing against the broker who mislabels the deal (the "ice-cream stand posted as a Walgreens" problem) - that is content falsehood, and **market truth is out of scope forever** (§ Non-goals). So signing is not the tool for the problem brokers worry about.
- What actually deters the mislabeler is **attribution**: the claim is on the record under a named license (layer 2), and verifiable to a domain (layer 3). Accountability, not encryption.
- Signing would add real friction to the **most common operation** - repricing/re-embed - because a private key would have to be present at every export/CI/watch-folder run. Hash recompute is free and already happening.
- The one thing we do now for the future: **reserve the optional `signature` field in the 0.1 schema.** It costs nothing today and avoids a breaking `@context` change later. Require nothing; build no verification; ship it `null`.

**Roadmap.** Day one: layers 1–2, plus layer 3 as consumer mode ships. Registry era (§11): layer 4 graduates from reserved to verified, because an open index of valuable listings is where *impersonation* (dishonest identity) finally becomes a real threat that signatures actually solve.

### §10.1 Attacker models - exactly what the four layers stop, and what they don't

The four layers are only meaningful against named adversaries. Each row states a concrete capability, the layer(s) that defend, the **residual gap that remains in 0.1**, and when that gap closes. Layer numbers refer to the §10 table (1 = embedded hash, 2 = self-asserted identity, 3 = domain-origin verification, 4 = reserved signature).

| # | Adversary & capability | Their goal | Defended by | Residual gap in 0.1 (honest) | Closes when |
|---|---|---|---|---|---|
| A1 | **Bit-flipper** - edits `om.json` bytes at rest or in transit, leaving the XMP hash untouched. | Silently change a number (price, cap, NOI). | **L1** - recomputed SHA-256 (§C) ≠ `omspec:payloadHash` → `hash-mismatch`. | None. This is the one attack a lone hash fully stops. | Shipped day one. |
| A2 | **Re-embedder / hijacker** - takes a valid OM, strips the payload, embeds a *self-consistent* replacement with a matching fresh hash. | Substitute the whole assertion while passing L1. | **L2** records whatever identity they claim; **L3** flags it if the file is not served from the claimed origin. | Day one, nothing *cryptographic* stops a self-consistent re-embed; the deterrent is attribution + origin, not prevention. | L4 (signature) makes substitution detectable by key, registry era. |
| A3 | **Impersonator** - asserts under another broker's name and license number they do not hold. | Borrow a reputable identity. | **L3** (only if they also control a matching origin domain - usually they don't); **L4** cryptographically, later. | **L2 does not defend** - `assertedBy` is self-asserted and MUST be labeled *unverified* (§AA). License-registry lookup is out of scope in 0.1. | L4 graduates + registry cross-checks license → domain → key (§11). |
| A4 | **Content liar / mislabeler** - accurate attribution, false facts ("ice-cream stand posted as a Walgreens"; pro-forma dressed as in-place). | Misrepresent the deal itself. | **No layer.** Consistency warnings (§9, §H) catch only *self-contradiction* (cap ≠ NOI÷price, schedule sums). | **Permanent and intentional** - market truth is out of scope forever (Non-goals). Attribution (L2/L3) makes the lie *accountable*, not *impossible*. | Never (by design). Accountability, not prevention, is the answer. |
| A5 | **Origin spoofer / rogue rehoster** - hosts a genuine broker's OM on an attacker-controlled domain. | Appear endorsed by the broker's brand at a look-alike URL. | **L3** - origin verification fails (host domain ≠ the payload's mirror domain); badge degrades to *origin-unverified*. | Rehosting-away-from-origin is expected and MUST degrade gracefully, not error (§AA OM-TRUST-004). L1/L2 still hold; the file is unaltered, just not vouched-for at that URL. | Correct as-is; L4 adds portable authorship independent of URL. |
| A6 | **Downgrade / stripper** - removes the XMP marker (or the whole attachment) so consumers fall back to vision extraction. | Evade tamper detection by removing the thing that detects it. | **L1** cannot fire on an absent payload; detection reports *absent* (→ vision fallback), never *trusted*. | A stripped payload is indistinguishable from an OM that was never embedded; downgrade is not detectable in 0.1. | L4 + a signed, origin-served mirror lets a consumer notice "this domain published a payload for this deal, but this file has none." |
| A7 | **Stale/replay server** - serves an older, superseded payload (e.g. the pre-reduction price) from a valid origin. | Keep a stale number circulating. | **L1/L2/L3 all pass** - the old payload is genuine, just outdated. `supersedes` + `assertedDate` expose it *only if* the reader fetches the origin mirror to compare. | Freshness is not enforced at read in 0.1. | §AA OM-TRUST-008 stale check (compare to origin mirror) + registry "latest" pointer, registry era. |

**Precise definition of "origin-verified" (L3).** A payload is *origin-verified* for a given fetch **iff** all hold: (a) the PDF (or its JSON-LD mirror) was retrieved over **HTTPS with a valid certificate chain** for host `H`; (b) a JSON-LD mirror of the payload is served from the **same registrable domain** (eTLD+1) as `H`; and (c) the mirror's canonical payload hash (§C) **equals** the embedded `omspec:payloadHash`. L3 therefore proves "*the entity controlling this domain vouches for this exact payload*" - nothing about legal identity, and nothing that survives being copied to another domain (which is correct: the vouch is scoped to the origin). This is the web's own trust model (HTTPS/DNS), reused for free because consumer mode already holds the URL (§4, §5b).

**One-line contract for each layer (quotable in UI):** L1 = *"unchanged since embed."* L2 = *"claims to be - unverified."* L3 = *"this domain vouches for it."* L4 = *"cryptographically theirs"* (reserved, empty in 0.1). No layer says *"true."* The normative badge machine and UI honesty rules that enforce these one-liners are §AA.

---

## Non-goals (consolidated - do not re-litigate)

These are settled and permanent unless a decision-log entry reverses them:
- **Market truth.** Tooling never judges whether a deal's claims are accurate - only internal consistency. Consuming LLMs editorialize anyway; the spec takes no position.
- **No inference in the open server, the core, or consumer mode - ever.** No keys in those layers.
- **No chat-UI puppeteering.** Never inject into or scrape logged-in ChatGPT/Claude sessions. Use MCP connectors / on-device / hosted paths.
- **No viewer scraping.** Detection re-fetches PDF bytes; it never inspects the browser's PDF viewer internals.
- **No re-export.** Rehost the embedded file itself; re-export destroys the attachment.
- **No silent visual modification.** Output PDF is visually identical unless an explicit badge flag is set.
- **No required cryptographic signing in 0.1.** The field is reserved; signing is registry-era (§10).

**Normative restatement (append-only IDs).** The bullets above are binding; these IDs let conformance tests and reviewers cite them.

- **[OM-SCOPE-001]** Tooling MUST NOT assert or judge *market truth* - whether a deal's claims are accurate. `om_validate` and the standalone checker MUST restrict themselves to internal-consistency warnings (§9, §H); they MUST NOT emit a finding that asserts a value is wrong relative to the market.
- **[OM-SCOPE-002]** `/core`, `/cli`, `/mcp` (open server), and consumer-mode `/js` MUST NOT contain, import, or invoke an inference client, and MUST NOT require API keys ([OM-DoD-008] enforces this in CI).
- **[OM-SCOPE-003]** No implementation MAY inject into, script, or scrape a logged-in third-party chat session (ChatGPT/Claude/etc.). Extraction MUST use on-device, hosted, or MCP-connector paths only (§5b).
- **[OM-SCOPE-004]** Detection MUST re-fetch PDF bytes and parse them (§5b, [OM-XMP-003]); it MUST NOT read the browser's built-in PDF-viewer internals.
- **[OM-SCOPE-005]** The update/rehost path MUST rehost the embedded file itself; a Producer/Consumer workflow MUST NOT re-export or "print to PDF" as a distribution step, which destroys the attachment (§4).
- **[OM-SCOPE-006]** `om_embed` MUST produce a visually identical PDF ([OM-DoD-001] SSIM ≥ 0.9999) unless an explicit badge flag is set; it MUST NOT recompress or alter visual content by default.
- **[OM-SCOPE-007]** Cryptographic signing MUST NOT be required to embed or re-embed in 0.1; `meta.signature` is reserved and MUST NOT be populated (OMV-E003). Additionally, output from OCR/vision extraction MUST NOT be recorded with `source: "verified"` or presented as market-truth; unreviewed extraction is at most `source: "extracted"` (§7a), and the tooling MUST NOT offer valuation, investment, or legal advice.

---

## 11. Adoption strategy summary
1. **Provenance + embedder-pays-once** (§2) - durable value first, token asymmetry as the hook.
2. **Validator as trojan horse** (§9) - standalone consistency checker seeds usage before embedding matters.
3. **Consumer mode creates visible demand** (§5b) - buy-side lights up on embedded OMs; buyers' brokers start *asking*.
4. **Extension makes authoring one click; local path removes the confidentiality objection** (§5b).
5. **Publish/webhook makes payloads immediately useful** - into CRMs/Sheets/Phil day one.
6. **Fortis seeds supply; Phil is the reference consumer** - wired in as an ordinary webhook.
7. **Buildout + peer integrations** (§5d).
8. **Badges** - link-level (consumer mode, no doc changes) now-ish; in-document overlay later.
9. **Neutral governance under Vervelio**, OSCRE-aligned vocabulary (§3).

### Trust roadmap (see §10 for the model)
- Day one: hash + self-asserted identity; domain-origin verification with consumer mode.
- Registry era: signatures graduate; index = the free-market MLS, crowd-sourced from the demand side via consumer-mode "submit to index" (opt-in; hash + origin + signature verified → spam-resistant). Anyone can build an index; Vervelio/Phil builds the reference.

### §11.1 Trust-roadmap graduation gates

The layers and the registry graduate only when their preconditions are demonstrably met - otherwise the deferral decisions in §16 are being reversed by drift, not by decision.

| Capability | MUST NOT ship until | Rationale (ties to §10) |
|---|---|---|
| **Layer 3 - domain-origin verification** | Consumer mode ships (M5a) AND the §10.1 origin definition is implemented and covered by §AA conformance cases (OM-TRUST-008/010). | It is the day-one *verification* path; shipping the badge without the precise check invites A5/A7 confusion. |
| **Layer 4 - signature (reserved → verified)** | (a) A named key-infrastructure decision exists (who issues/rotates/revokes keys - brokerage? license authority? Vervelio CA?); (b) the `signature` field's canonical form is specified so signing does **not** change the integrity hash ([OM-CANON-003] already excludes `meta.signature`); (c) revocation + verification are defined; (d) a migration note ships (new context is *not* required - the field is additive within 0.1's context). | Signing solves impersonation (A3), which is only a *real* threat once an open index makes valuable listings worth impersonating; shipping it earlier adds friction to repricing for no threat reduction (§16). |
| **Registry / "submit to index"** | Layer 3 in production AND [OM-PRIV-003] consent model AND spam controls gated on hash + origin verification (later + signature). | "An open MLS with no origin verification is a spam magnet" (§2). Origin verification is the minimum bar; do not open the index below it. |

**Adoption funnel (tracked, not gated - depends on parties outside our control).** The two-sided flywheel (§2) is measured, telemetry-free, by counting observable artifacts, not by phoning home ([OM-TEL-001]): (1) OMs embedded (supply); (2) distinct domains serving origin-verifiable payloads; (3) external tools/users reading payloads via `om_read`/consumer mode (demand); (4) buyers' brokers *asking* for embedded OMs (qualitative, reported by Fortis). Progression 1→3 is the flywheel turning; stall at (1) means demand (consumer mode, §5b) is the lever to pull, not more supply.

---

## 12. Risks & mitigations

Each risk names a **testable gate** - a named test, CI check, or verifiable artifact - so "mitigated" is falsifiable, not asserted. Ordered highest-concern first; IDs are stable and append-only.

| ID | Risk | Mitigation | Testable gate | Owner |
|---|---|---|---|---|
| **OM-RISK-001** | **Cold-start - no supply, no demand** | Ship the standalone consistency validator first (value with zero embedding); consumer mode manufactures visible demand; Fortis seeds supply. | M1.x validator runs on any OM/payload in CI (§14 OM-DoD-002); adoption-DoD counter: ≥1 broker catches a real error pre-embed. | Scott + dev |
| **OM-RISK-002** | **Cross-impl round-trip bug** (pdf-lib ↔ pikepdf payload drift) | Named cross-implementation round-trip test from day one (§8a); byte-for-byte payload fidelity in CI. | [OM-VEC-002] green on every commit; divergence = red build (§14 OM-DoD-001). | Dev |
| **OM-RISK-003** | **Confidentiality objection** (won't upload unreleased OM) | On-device local extraction path (Prompt API); doc never leaves the machine. | M5b local path proven with a network-egress assertion = 0 bytes leave device during extraction (§14 OM-DoD-007); [OM-PRIV-001] path disclosure shown pre-send. | Dev |
| **OM-RISK-004** | **Fixture skew** (all one producer → messy cases untested) | Spec a fixture *matrix* (producers × pathologies), not a count; block M1 exit until the matrix is filled. | Matrix coverage report lists every (producer × pathology) cell as filled; M1 exit gate refuses on any empty cell (§14 OM-DoD-001, [OM-VEC-004]). | Scott (sources) + dev |
| **OM-RISK-005** | **Name squatting / unavailable across registries** | P0 name sweep across org+PyPI+npm+Web Store+domain *as a set* before any `@context` or import (§15 Q1). | Reservation receipts for all five namespaces recorded before first `@context` publish or first import lands. | Scott |
| **OM-RISK-006** | **Free/paid line drawn too late** | Decide before M3; ideally settle at M1 (§15 Q2). | §15 Q2 resolved with a written boundary before M3 opens; default-if-unresolved fallback applies (§15). | Scott |
| **OM-RISK-007** | **SSRF / abuse of hosted re-fetch** (om_read(url)/om_inspect(url), webhook POST) | Range-block private/loopback/link-local/metadata targets; no redirect into them; DNS-rebinding mitigation; HTTPS-only; size/time caps ([OM-SEC-001], [OM-SEC-003]). | Vector suite fires each blocked range (RFC1918, 127/8, ::1, 169.254/16, 100.64/10, fc00::/7) and asserts refusal; redirect-into-range test red. | Dev |
| **OM-RISK-008** | **Confidential-OM retention leak** (unreleased OM lingers on R2) | Default TTL ≤24h + delete-on-completion; single-use scoped presigned URLs ([OM-PRIV-002], [OM-SEC-006]); resolves §15 Q4. | Integration test: uploaded blob is unreachable after TTL and after job completion; presigned URL rejected on reuse. | Dev |
| **OM-RISK-009** | **Trust over-sold** (hash read as authenticity) | Four-layer model states what each proves and doesn't (§10, §10.1); UI shows distinct hash vs origin vs signature states; badge precedence + UI-honesty rules (§AA). | §AA conformance cases (OM-TRUST-001..005) pass; UI copy audit finds no forbidden word on an integrity-only pass. | Dev |
| **OM-RISK-010** | **Detection edge cases** (object streams hide EmbeddedFiles; viewer variance) | Re-fetch + full parse fallback; Range-request heuristic is best-effort, confirmed on open; cache. | Fixture cases with EmbeddedFiles inside object/xref streams parse correctly ([OM-VEC-004]); heuristic false-positive confirmed-on-open in extension test. | Dev |
| **OM-RISK-011** | **Prompt API insufficient/unavailable** (Gemini Nano weak on messy schedules, or absent on a target browser) | Review panel + consistency warnings as the net; hosted + chat-handoff fallbacks; build-time capability check (§15 Q6). | M5b degrades to hosted/chat-handoff when Prompt API absent (feature-detect test); schedule-heavy fixture surfaces the right OMW-W02x warnings for reviewer. | Dev |
| **OM-RISK-012** | **Spec fork / vendor divergence** (implementers drift the wire format) | Conformance vectors as the arbiter (§B); CC-BY spec + neutral governance RFC (§G, §L); cross-impl gate on every spec change. | Third-party implementations must reproduce §B vectors bit-for-bit; [OM-GOV-002] blocks merges without green cross-impl tests. | Scott |
| **OM-RISK-013** | **Incumbent capture** (Buildout/CoStar clones it closed) | Open MIT spec + neutral Vervelio governance + first-mover corpus; approach Buildout as partner, not competitor. | Published spec + vectors + governance doc are public and CC-BY before outreach; partnership approached per §5d timing. | Scott |
| **OM-RISK-014** | **Core dependency abandonment** (pikepdf / pdf-lib / PyMuPDF) | Cross-impl parity means either engine is independently replaceable; pin versions; the wire format (§C/§D) is library-agnostic. | [OM-VEC-002] proves the format survives swapping one implementation; dependency versions pinned in lockfiles. | Dev |


---

## 13. Future scope (parked, not forgotten)
In-document badge overlay (§4) · signature verification + key infra (§10) · registry + submit-to-index (§11) · named publish connectors (HubSpot/Salesforce/Sheets) · multi-tenant/industrial/office spec versions · strict PDF/A-3 · XMP mirror fields for dumb crawlers · hosted inference tier (§15 Q2) · sidecar convention (§15 Q5) · Buildout + peer native integrations · Firefox/Edge ports (check Prompt API availability).

### §13.1 Graduation triggers (what promotes a parked item to planned)

Each parked item stays parked until its trigger fires; the trigger is the falsifiable condition, not a calendar date.

| Parked item (from §13) | Graduation trigger |
|---|---|
| In-document badge overlay (§4) | A producer/partner requests the visible mark AND the opt-in flag + overlay leave rendered content otherwise byte-stable (no recompression). |
| Signature verification + key infra (§10 L4) | §11.1 Layer-4 gate satisfied (key infra decided, revocation defined). |
| Registry + submit-to-index (§11) | §11.1 registry gate satisfied (Layer 3 in production + consent + spam controls). |
| Named publish connectors (HubSpot/Salesforce/Sheets) | Recurring evidence the generic webhook (§5b) is insufficient for a specific high-volume receiver. |
| Multi-tenant / industrial / office spec versions | 0.1 STNL wire format is stable across ≥2 minor releases with no open structural defects. |
| Strict PDF/A-3 conformance | A consumer/regulatory requirement for strict archival conformance is identified (relaxed v1 otherwise suffices, §8a). |
| XMP mirror fields for dumb crawlers (§15 Q7) | A crawler that cannot open the attachment but reads XMP is a demonstrated consumer. |
| Per-field provenance side-map (scalar + `options[]` `source`, #44) | A consumer needs field-level provenance on non-schedule fields; ships as an additive minor (§F) defining a `source` side-map keyed by JSON pointer, without wrapping scalars. |
| Hosted inference tier (§15 Q2) | Boundary decided 2026-08-17 (§15.1) → **graduated: builds with M3** as a separate paid service. |
| Sidecar convention (§15 Q5) | A workflow needs `om.json` decoupled from the PDF that the embedded file + JSON-LD mirror cannot serve. |
| Buildout + peer native integrations (§5d) | 0.1 spec + tooling shipped AND initial adoption traction (funnel §11.1 stage 3). |
| Firefox/Edge ports | Prompt API (or an acceptable extraction fallback) confirmed available on the target browser (§15 Q6). |

---

## 14. Development plan (Claude Code handoff) - with definition-of-done

Each milestone has a **technical DoD (gates the milestone)** and an **adoption DoD (tracked, does not gate - it depends on parties we don't control).**

**Repo layout:** `/core` (Python) · `/cli` · `/mcp` · `/process` · `/spec` · `/js` (TS subset) · `/extension` (MV3, consumer + author) · `/fixtures`.

**Fixtures before extraction logic.** A *matrix*, not a count: producers (InDesign, Word-to-PDF, Buildout, scanned) × pathologies (messy rent schedule, CMYK/SMask images, flattened scan, empty payload, hash mismatch). 10–15 real OMs covering the matrix. (Scott sources.) M1 does not exit until the matrix is filled.

| Milestone | Technical DoD (gate) | Adoption DoD (tracked) |
|---|---|---|
| **M1 - round trip (stdio)** | inspect + extract_images + embed/read on 3 real OMs (native/hybrid/scanned); non-destructive, idempotent re-embed w/ `supersedes`, survival through download/re-upload; cross-impl round-trip test green. | 3 real Fortis OMs embedded and re-read successfully. |
| **M1.x - standalone validator** | Consistency-warning checker (schema-independent) runs on any payload/OM; catches NOI/cap, schedule sums+contiguity, date math. | ≥1 broker runs it to catch a real error before caring about embedding. |
| **M2 - schema + validate** | JSON Schema 0.1 published; two-tier validate (errors block / warnings inform); samples in `/spec`; per-field `source` tags; reserved `signature` field. | Schema referenced by an external reader. |
| **M3 - remote transport** ✅ *(gate met 2026-08-17, deterministic-only)* | Streamable HTTP; URL + presigned upload; R2; link outputs. Free/paid line decided by here. | ChatGPT/web client reads a payload via hosted MCP. |
| **M4 - process layer** ✅ *(gate met 2026-08-17; Claude half + client-agnostic instructions)* | SKILL.md + generic instructions; end-to-end in Claude + one non-Claude client. | A non-Claude client completes the full loop *(adoption-deferred)*. |
| **M5a - extension consumer mode** ✅ *(gate met 2026-08-17; A=`/js` trust core + B=MV3 extension)* | `/js` read/validate (+ cross-impl test vs pikepdf); MV3 detection (re-fetch on viewed PDFs, toolbar badge); payload card; domain-origin verification; named-webhook publish (envelope + HMAC) + test-fire + copy/download. No model anywhere. Read path worker-free (pdf-lib + zlib/DecompressionStream) and validator eval-free (ajv standalone) for the MV3 CSP. | 10 real OMs embedded and read by an external tool/user via the extension *(live-user adoption pending)*. |
| **M5b - extension author mode** ✅ *(gate met 2026-08-17; B1 deterministic + B2 on-device extraction)* | Side-panel review; local extraction via the on-device Prompt API (a browser global, isolated behind an Extractor seam); hosted path a throwing seam behind Q2; embed via `/js`. `chrome.downloads` interception deferred (capture is re-fetch + file picker). | A broker embeds an OM end-to-end without touching the CLI *(live-broker adoption pending)*. |

### §14.1 Measurable milestone exit criteria (gates)

Each gate below is the *machine-checkable* form of the corresponding Technical DoD in the table. A milestone MUST NOT be declared complete until its gate command exits green. Gate IDs are stable and append-only.

- **[OM-DoD-001] M1 round-trip gates.** (a) **Non-destructive:** for every fixture, output vs input has *identical* page count, an *identical* bookmark/outline tree, an *identical* count and destination set of link annotations, and per-page rendered rasters (300 DPI) with **SSIM ≥ 0.9999** (or zero perceptual diff); the file opens without repair in ≥2 independent viewers. (b) **Idempotent re-embed:** N≥3 successive embeds yield **exactly one** `om.json` in `/EmbeddedFiles`, a correct `supersedes` chain, and an Nth-output payload hash **equal** to a single direct embed's hash ([OM-XMP-004]). (c) **Survival:** payload `sha256:` is unchanged after **≥3** upload→download round-trips across **≥2** storage backends. (d) **Cross-impl:** [OM-VEC-002] green. (e) **Fixture matrix:** every (producer × pathology) cell filled ([OM-VEC-004]); exit refuses on any empty cell. *Verify:* `pytest core/tests -k "roundtrip or idempotent or survival or nondestructive" && python -m spec.matrix --assert-full`.
- **[OM-DoD-002] M1.x validator gate.** The standalone consistency checker runs on any payload *or* OM with no schema dependency and emits the correct §H codes for a labeled corpus: it MUST detect the seeded NOI/cap (OMW-W010), price/SF (OMW-W011), schedule sum/contiguity (OMW-W020/021/022), and date/term (OMW-W030/031) defects with **zero false negatives** on the seeded set. *Verify:* `pytest core/tests/test_consistency.py --corpus fixtures/seeded_defects`.
- **[OM-DoD-003] M2 schema gate.** `/spec/om-0.1.schema.json` (2020-12) published; `om_validate` returns errors that block and warnings that don't ([OM-ERR-001]); every §B vector reproduces its expected code set exactly ([OM-VEC-003]); per-field `source` tags and the reserved `signature` field (rejected via OMV-E003 if populated) are enforced; the JSON-LD `@context` vocabulary is published and drift-locked to the schema (§15.1 / #13). *Verify:* `pytest core/tests/test_samples.py core/tests/test_vectors.py spec/tests/test_context.py` (schema-tier code-set reproduction + canonical vectors + vocabulary completeness).
- **[OM-DoD-004] M3 remote gate.** Streamable HTTP transport serves the tool surface; PDF input accepted as path | HTTPS URL | blob-id; R2 wired with the [OM-PRIV-002] TTL + delete-on-completion proven; **all [OM-SEC-001] SSRF range cases refused** in an automated suite; the free/paid line (§15 Q2) is written down. *Verify:* `pytest mcp/tests/test_remote.py mcp/tests/test_ssrf.py`.
- **[OM-DoD-005] M4 process gate.** `/process` SKILL.md + generic agent-instructions drive the full loop end-to-end in Claude **and** one non-Claude MCP client, each producing a payload that passes `om_validate` with zero errors. *Verify:* recorded transcript + resulting payload passes `om_validate` in CI.
- **[OM-DoD-006] M5a consumer-mode gate.** ✅ *(met 2026-08-17.)* `/js` read/validate passes the cross-impl test against pikepdf ([OM-VEC-002]); MV3 detection re-fetches viewed PDFs (never scrapes the viewer) and drives the badge through all §AA states on labeled fixtures; the payload card renders; domain-origin verification meets the §10.1 definition; named-webhook publish sends an HMAC-signed, replay-protected envelope (§5b) with a working test-fire; **no inference dependency present in the consumer bundle** (import/graph assertion). The proof is the **live** real-browser Playwright gate (7/7 §AA states + publish HMAC over a self-signed HTTPS harness) - the mocked unit tests were green while two MV3-only defects (pdf.js worker, ajv `new Function`) still broke the product, so the live gate is the sole standard of proof (Rule 5). *Verify:* `npm --prefix js test && npm --prefix extension run test:consumer && node extension/scripts/assert-no-inference.mjs extension/dist`.
- **[OM-DoD-007] M5b author-mode gate.** ✅ *(met 2026-08-17.)* Capture (re-fetch/file) → review panel (`process/review-contract.md`) → validate → Assert & Embed via `/js`; on-device extraction via the Prompt API behind an Extractor seam with a **network-egress assertion of 0 bytes** during extraction ([OM-PRIV-001]); hosted path a throwing seam behind §15 Q2; a broker completes an embed without touching the CLI. The **egress-zero proof is architecture-level**: the live gate injects a fake `LanguageModel` to exercise the real on-device adapter (the real model can't run in CI Chromium) and asserts 0 off-device requests during `extract()` - stated, not faked. `chrome.downloads` interception deferred (not required for the gate). *Verify:* `npm --prefix js test && npm --prefix extension run test:consumer && node extension/scripts/assert-no-inference.mjs extension/dist` (the extension gate runs the author + egress-zero cases).
- **[OM-DoD-008] Standing gate (all milestones).** No inference dependency in `/core`, `/mcp`, or consumer-mode `/js`; tool outputs paginated/manifest-only; visual content unchanged absent an explicit badge flag. *Verify:* `node scripts/assert-no-inference.js core mcp extension/dist/consumer` runs in CI on every commit and is a required check.

**Suggested first Claude Code prompt (M1):** "Read `/spec` and this handoff doc. Scaffold `/core` with pikepdf-based embed/read (EmbeddedFiles + /AF AFRelationship=Data + XMP block w/ spec name/version/hash), PyMuPDF-based inspect (native/hybrid/scanned classification) and image extraction (SMask recombine, xref dedupe, CMYK→sRGB). Idempotent re-embed with `supersedes` hash. pytest round-trip against `/fixtures`. No LLM calls anywhere in `/core`."

**Standing rules for dev:** no inference in the open server, core, or consumer mode, ever · tools return compact outputs · never modify visual content without an explicit flag · every payload change bumps `assertedDate` · no automation of third-party logged-in sessions · detection re-fetches bytes, never scrapes the viewer · no signing required at embed/re-embed (§10).

---

## 15. Open questions (prioritized + assigned)

| # | Question | Priority | Blocks | Decide by | Default if unresolved by deadline | Owner |
|---|---|---|---|---|---|---|
| Q1 | **Name sweep** - GitHub org + PyPI + npm + Chrome Web Store + domain as a set. Candidates: OpenOM, omspec, ListingLD. | **P0** | `@context`, all imports, org reservation | **Before first `@context` publish or first import** (M1 scaffolding) | Keep working title "OpenOM" + `openom.app`; do **not** publish `@context` or reserve packages until locked (blocking is correct here - no risky default). | Scott |
| Q2 | **Free/paid boundary** - engine/MCP/extension local+consumer = free MIT; hosted inference extraction = commercial? | P0 | M3 (ideally settle at M1) | ~~Before M3 opens~~ | **RESOLVED 2026-08-17 (see §15.1).** Everything deterministic + self-hostable is free MIT; the sole paid product is **Vervelio-hosted inference extraction**, **built in M3** as a service separate from the open MCP server; Vervelio also runs a **free public deterministic MCP** instance alongside self-hosting. | Scott |
| Q3 | **Fixture matrix** - which producers × which pathologies, concretely. | P1 | M1 exit | **Before M1 exit gate** ([OM-DoD-001]) | Use the §14 baseline matrix (InDesign/Word/Buildout/scanned × messy-schedule/CMYK-SMask/flattened/empty/hash-mismatch); expand as real OMs arrive. | Scott + dev |
| Q4 | **Blob storage + retention** (R2) - expiry for unreleased OMs. | P1 | M3 | **With M3 remote gate** ([OM-DoD-004]) | Apply [OM-PRIV-002] conservative default: ≤24h TTL + delete-on-completion, single-use presigned URLs. | Dev |
| Q5 | **Sidecar convention** - `om.json` beside `om.pdf`? | P2 | M5a (nice-to-have) | Before M5a ships (non-blocking) | Do not ship a sidecar convention in 0.1; the embedded file + JSON-LD mirror are the two supported surfaces. | Dev |
| Q6 | **Build-time verifications** - Gemini web connectors · Prompt API limits + structured output · chat prefill deep-links per client · Web Store publishing under Vervelio · Prompt API on Edge. | P1 | M5a/M5b | **During M5a/M5b build** | Feature-detect at runtime and degrade to hosted/chat-handoff fallbacks (OM-RISK-011) where a capability is missing. | Dev |
| Q7 | **XMP mirror fields** for dumb crawlers. | P2 | future | Registry era (non-blocking) | Ship only the required §D.2 XMP marker in 0.1; add mirror fields additively (minor, §F) when a crawler need is demonstrated. | Dev |
| Q8 | **Consumer-mode defaults** - auto-check every viewed PDF (size cap) vs check-on-open? Link-badging per-domain opt-in? Cache TTL? | P2 | M5a | **With M5a consumer gate** | Default to check-on-panel-open (privacy-conservative), link-badging opt-in per domain, cache TTL 24h; revisit from telemetry-free user feedback. | Dev |
| Q9 | **Index submission consent model** (registry era) - what is shared, when. | P3 | registry | Before any registry code | Enforce [OM-PRIV-003]: opt-in per submission, share payload + source URL only (never the PDF), require hash + origin verification. | Scott + dev |

### §15.1 Free/paid boundary (Q2 resolution, 2026-08-17) - the written line for [OM-DoD-004]

This is the authoritative statement M3's gate requires in writing. It does not, and cannot, weaken the cardinal rule (§6a): the open server, `/core`, `/mcp`, and consumer-mode `/js` remain deterministic - zero inference, zero keys - forever.

**Free (MIT code / CC-BY-4.0 spec), self-hostable by anyone:**
- The entire deterministic toolchain: `/core`, `/cli`, `/mcp` (both stdio **and** Streamable HTTP transports), `/js`, and the `/extension` in **both** consumer and author modes.
- Author-mode extraction that runs **on-device** (Prompt API) or **client-side** - no Vervelio cost, so free.
- The spec text, JSON Schema, `@context`/vocabulary, and conformance vectors (CC-BY-4.0, attributed to Vervelio, §G).
- **A free, rate-limited, public Vervelio-hosted instance of the *deterministic* MCP server** - run for reach/adoption (ChatGPT/web clients), since it carries no per-call model cost. Anyone may also self-host the identical code.

**Paid (a separate commercial service - never the open server):**
- **Vervelio-hosted inference extraction** (extraction path 2, §5b): the endpoint that runs an LLM to turn a messy or scanned OM into a *reviewed-draft* payload. This is the only capability with genuine per-call cost and is the sole commercial product in 0.1's horizon.
- **Decision: it is BUILT in M3** (not stubbed), alongside - but architecturally separate from - the open deterministic remote transport. It holds its own model keys, lives outside `/mcp`, and is subject to single-use presigned uploads ([OM-SEC-006]) and retention ([OM-PRIV-002]). Path 0 (manual/review-only) and Path 1 (on-device) remain free and always available, so the paid path is never on the critical path to a valid embed.

**Consequence for M3 scope:** M3 now ships two things - (a) the free deterministic Streamable HTTP MCP (self-host + Vervelio public instance), and (b) the separate paid inference-extraction service. The `assert-no-inference` standing gate ([OM-DoD-008]) MUST continue to pass over `/core`, `/mcp`, and consumer `/js`; the paid service is explicitly out of that tree.

---

## 16. Decisions log
| Date | Decision | Rationale |
|---|---|---|
| 2026-08-15 | Layered architecture, one repo | Deterministic engine ≠ LLM process |
| 2026-08-15 | Python core (pikepdf + PyMuPDF) | PDF tooling maturity |
| 2026-08-15 | Factur-X-style PDF/A-3 embedding, relaxed v1 | Proven mechanism |
| 2026-08-15 | JSON-LD, schema.org + custom vocab, versioned + JSON Schema | Spec is the product |
| 2026-08-15 | XML dropped | No identified consumer |
| 2026-08-15 | v0.1 = STNL, N/NN/NNN | Most standardized; Fortis seeds |
| 2026-08-15 | Published under Vervelio | Neutral governance |
| 2026-08-15 | Dual transport; hosted Streamable HTTP | ChatGPT/web reach |
| 2026-08-15 | Zero inference server-side | No keys/costs |
| 2026-08-15 | Validator = errors + consistency warnings; never market truth | Assertions, not facts |
| 2026-08-15 | noiType + asOfDate required; assertedBy/Date framing | Opinion-not-fact in the spec |
| 2026-08-15 | landlordResponsibilities booleans | Kills "everything is NNN" |
| 2026-08-15 | Workflow = generate → embed → rehost; idempotent updates | Repricing is the common case |
| 2026-08-15 | In-document badge = future, opt-in | Never silently modify visuals |
| 2026-08-15 | Chrome extension = primary human-facing surface | One-click authoring + detection |
| 2026-08-15 | HARD RULE: no chat-UI puppeteering | ToS, fragility, account risk |
| 2026-08-15 | TS subset required | Extension needs in-browser engine |
| 2026-08-15 | Review-before-embed = spec SHOULD; review panel = assertion gate | Extraction → assertion via human |
| 2026-08-15 | Extension consumer mode ships before author mode | Fully deterministic; demo-able earlier |
| 2026-08-15 | Detection via re-fetch of the PDF URL, never viewer inspection | Viewer internals inaccessible |
| 2026-08-15 | Publish v1 = neutral named webhooks + copy/download; NO presets | Webhook is the universal adapter |
| 2026-08-15 | Webhook envelope mini-spec, versioned with the spec | Receiving systems need a stable contract |
| **2026-08-16** | **Thesis reframed provenance-first; token asymmetry is the hook, not the durable value** | Token costs decay; attributable provenance does not |
| **2026-08-16** | **Provenance = four layers: hash + self-asserted identity + domain-origin verification + reserved signature field** | Each proves one thing; be honest about limits |
| **2026-08-16** | **No cryptographic signing required in 0.1 or at re-embed; `signature` field reserved-not-required** | Signing doesn't solve content lies, adds friction to repricing; reserving the field avoids a breaking change |
| **2026-08-16** | **Domain-origin verification is the day-one verification path** (read-time, web-native) | Free - consumer mode already has the URL; no key management |
| **2026-08-16** | **Per-field `source` tag (asserted/extracted/verified)** | Operationalizes "assertions, not facts" at field level |
| **2026-08-16** | **`rentSchedule` fully modeled with consistency rules** | The acknowledged differentiator; must be a real object |
| **2026-08-16** | **Webhook envelope gains HMAC + replay protection + independent `envelopeVersion`** | Receiving systems need a security contract, not just a shape |
| **2026-08-16** | **Validator split: standalone consistency checker early, schema-error tier with M2** | Trojan-horse value needs no schema; avoids artificial milestone |
| **2026-08-16** | **Milestone DoD is two-tier: technical gates, adoption tracks** | A milestone can't be hostage to a third party's tool existing |
| **2026-08-16** | **Payload canonicalization = RFC 8785 (JCS); integrity hash = SHA-256 over JCS bytes, stored in XMP** (§C) | Cross-impl byte-for-byte fidelity is undefinable without a canonical form |
| **2026-08-16** | **Code = MIT; spec/schema/@context/vocabulary = CC-BY-4.0** (§G) | Spec licensing is separate from code licensing and gates adoption |
| **2026-08-16** | **Stable error/warning code taxonomy (`OMV-E###` / `OMW-W###`)** (§H) | Tools and receivers must program against codes, not prose |
| **2026-08-16** | **Spec follows SemVer; published `@context` URLs are immutable** (§F) | A shipped standard's contract cannot silently change meaning |
| **2026-08-16** | **PDF `/Params/CheckSum` (MD5) is NOT the integrity mechanism; the SHA-256 in XMP is** (§C, §D) | The PDF-level checksum is legacy MD5; provenance needs SHA-256 |
| **2026-08-16** | **Zero telemetry in core, open server, and consumer mode; extension analytics opt-in only** (§M) | Matches the deterministic-core rule; adopters demand it |
| **2026-08-16** | **Trust contract made normative: badge is a strict precedence state machine with UI-honesty constraints and a stale-assertion check** (§AA, [OM-TRUST-001..010]) | "Hash read as authenticity" (OM-RISK-009) is prevented by enforcing what each layer may *say*, not just what it proves |
| **2026-08-16** | **"Origin-verified" precisely defined = valid HTTPS host + same-eTLD+1 JSON-LD mirror + mirror hash == embedded hash; verification is non-transitive** (§10.1) | The named cross-impl and consumer gates need an unambiguous, testable definition of Layer 3 |
| **2026-08-16** | **Six explicit attacker models bound to the four layers, with honest residual gaps** (§10.1) | A trust contract is only load-bearing if it names whom it defends against and where it deliberately does not |
| **2026-08-17** | **M4 gate [OM-DoD-005] met: `/process` extraction playbook shipped - `mapping-guide.md` (shared substance) + `SKILL.md` (Claude) + `agent-instructions.md` (any MCP client), with a committed synthetic demo OM whose produced payload passes `om_validate` zero-error + warning-clean (`spec/tests/test_process_example.py`)** | Inference lives only in the agent's mapping step; every `om_*` tool stays deterministic. The live non-Claude MCP-client run is adoption-deferred (client-agnostic instructions authored, not faked) |
| **2026-08-17** | **M3 gate [OM-DoD-004] met (deterministic-only): hosted Streamable HTTP MCP - SSRF-hardened url fetch (resolve-then-pin), R2/local blob store (≤24h TTL + delete-on-completion + server-bound owner), per-principal rate limit, transport security (Host/Origin), untrusted-PDF parse isolation (subprocess timeout/memory), per-call page ceiling; paid extraction = seam only** | The free deterministic hosted server ships first; the paid inference-extraction service + distributed limiter/auth are hosted-deploy-gated (§15.1, issues #51/#52) |
| **2026-08-17** | **Per-field `source` scoped to `rentSchedule[]` period objects in 0.1 (#44); scalar + `options[]` provenance deferred to a future provenance-side-map minor** | A "sibling `source`" is only well-defined on object-valued fields; the schema already implements exactly this, so the prose is aligned to reality rather than wrapping scalars in 0.1 |
| **2026-08-17** | **Q2 free/paid boundary RESOLVED (§15.1): all deterministic + self-hostable surfaces free MIT; sole paid product = Vervelio-hosted inference extraction, BUILT in M3 as a service separate from the open server; Vervelio also runs a free public deterministic MCP** | Unblocks M3 ([OM-DoD-004] needs the line in writing); charges only for the one capability with real per-call cost, keeping the standard maximally adoptable |
| **2026-08-16** | **Risk register uses quantified L×I (1–5) scoring, banded, with a testable gate + stable [OM-RISK-###] ID per risk; five risks added (SSRF, retention leak, dependency abandonment, spec fork, Prompt-API insufficiency)** (§12) | Prose severities aren't comparable or falsifiable; "mitigated" must be provable |
| **2026-08-16** | **Milestone DoD gains machine-checkable exit gates [OM-DoD-###] with numeric thresholds + verification commands** (§14.1) | A gate that can't be run isn't a gate; "non-destructive/survival" needed numbers |
| **2026-08-16** | **Every open question gets a decide-by deadline and a default-if-unresolved fallback** (§15) | No pending decision - even a P0 - may silently deadlock the build |
| **2026-08-16** | **Trust roadmap + parked scope get explicit graduation gates/triggers** (§11.1, §13.1) | "Registry era"/"future" must be preconditioned, not calendar-guessed, to protect the 0.1 scope and deferral decisions |
| **2026-08-16** | **Non-goals restated as append-only normative requirements [OM-SCOPE-001..007]; OCR/vision output may never be `verified`/market-truth** (Non-goals) | Settled non-goals must be citable by conformance tests, and the two implied gaps closed |
| **2026-08-16** | **Webhook contract hardened to production grade (§Y, OM-HOOK): named RFC 6648-clean headers, `t=…,v1=…` HMAC-SHA256 over raw body, ±300 s replay window, stable event-id idempotency key, at-least-once delivery + key rotation. Workflow survival, idempotent re-embed, and extraction-path determinism made normative (§Z, OM-FLOW/OM-EXTP).** | Receiving systems and the extension need a testable wire contract and an unambiguous determinism boundary, not prose |


---


# PART II - Normative Specification & Technical Appendices

> **These sections are normative.** The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are to be interpreted as described in **RFC 2119** and **RFC 8174** (only uppercase forms are normative). Requirements carry stable IDs (`[OM-AREA-###]`) so conformance tests map 1:1 to requirements (§B, §12-traceability).

---

> **Scope of this Part II (M1-essential subset).** Only the normative core an M1 implementer opens is inlined here: **§A** conformance conventions, **§B** conformance suite & vectors, **§C** canonicalization & hashing, **§D** embedded-file & XMP wire format, **§E** data dictionary, **§H** error & warning taxonomy, **§I** MCP tool contracts, **§J** security considerations. The remaining normative appendices - versioning & compatibility, licensing/IP, privacy, governance, telemetry, diagrams, the worked end-to-end example, the `@context` model, the ABNF grammar, conformance profiles, the reference harness, vulnerability disclosure, and the §V–§AA conformance appendices - are drafted but **deferred until adoption** and live in [`om-normative-spec-draft-v0.1.md`](om-normative-spec-draft-v0.1.md). **Any §-reference in this document to an appendix not present here (§F, §G, §K, §L, §M, §N, §O–§AA) resolves in that file.** Requirement IDs are append-only and shared across both files.

---

## §A. Conformance conventions & requirement traceability

- **[OM-CONF-001]** An implementation claiming "OpenOM 0.1 conformant" MUST satisfy every `MUST`/`MUST NOT` in Part II that applies to the role it implements (Producer, Consumer, or Validator; §B).
- **[OM-CONF-002]** Requirement IDs are stable and append-only. A requirement MUST NOT be renumbered; if withdrawn it is marked *Deprecated* with the version that withdrew it, never deleted.
- **[OM-CONF-003]** Every normative requirement MUST have exactly one ID. Conformance-suite test cases (§B) MUST reference the ID(s) they exercise.
- **[OM-CONF-004]** Roles: **Producer** = writes payloads/embeds (CLI, `/js` author mode, `om_embed`). **Consumer** = reads/verifies (`om_read`, consumer mode). **Validator** = runs schema + consistency checks (`om_validate`, standalone checker). An implementation MAY fill multiple roles; it is judged against each role it claims.

### §A.1 Conformance targets, roles & levels

- **[OM-CONF-005]** A **conformance target** is a (role × level) pair. The roles are those of [OM-CONF-004] (Producer, Consumer, Validator). Each role defines two levels, **L1** (baseline) and **L2** (full). An implementation claims one target per role it implements; **L2 subsumes L1** - an implementation MUST NOT claim L2 for a role without satisfying every L1 requirement for that role. An implementation MAY claim different levels for different roles (e.g. Producer L2, Consumer L1).

- **[OM-CONF-006] Producer L1 (baseline embed).** A Producer L1 MUST, for a **native or hybrid** input PDF: (a) serialize the payload per canonicalization [OM-CANON-001]–[OM-CANON-007]; (b) embed it exactly per the wire format [OM-EMB-001]–[OM-EMB-005], [OM-EMB-010]–[OM-EMB-012] and write the XMP marker [OM-XMP-001]–[OM-XMP-003]; (c) perform idempotent re-embed [OM-XMP-004] with a correct `supersedes` value; (d) preserve visual content and document structure (§4.2 non-destructive; no re-export, no recompression of existing content); and (e) reproduce, for every applicable vector, the exact `sha256:` integrity hash required by [OM-VEC-003]. A Producer L1 that also runs consistency checks pre-embed MUST NOT let a warning block the embed ([OM-ERR-001]).

- **[OM-CONF-007] Producer L2 (full producer).** A Producer L2 MUST satisfy Producer L1 across the **entire pathology matrix** ([OM-VEC-013]–[OM-VEC-015]), including **scanned/flattened** and **image-bearing** PDFs, without corrupting image content or losing bookmarks/links; MUST maintain a correct `supersedes` chain across **at least two successive re-embeds** (each `omspec:supersedes` = the immediately-prior `omspec:payloadHash`); and MUST pass the **cross-implementation round-trip** [OM-VEC-002] in **both directions** for every applicable vector. A Producer L2 that additionally exposes image extraction (`om_extract_images`) MUST conform to §8b (SMask→RGBA recombination, CMYK/ICC→sRGB, tiled/striped assembly, xref dedupe).

- **[OM-CONF-008] Consumer L1 (read + integrity).** A Consumer L1 MUST implement the detection and integrity path: locate the payload in detection order [OM-XMP-003], decompress the `om.json` stream, recompute the §C integrity hash over the decompressed bytes, compare it to `omspec:payloadHash`, and return the payload or `null`. It MUST report `hash-mismatch` and MUST NOT treat a mismatched payload as trusted ([OM-XMP-003], [OM-SEC-005]). A Consumer L1 that re-fetches bytes from a URL MUST apply the SSRF range rules [OM-SEC-001] and the decompression-bomb caps [OM-SEC-002]. Consumer L1 is the minimum contract for `om_read` and for extension consumer-mode detection.

- **[OM-CONF-009] Consumer L2 (verify + validate).** A Consumer L2 MUST satisfy Consumer L1 and additionally: (a) perform **domain-origin verification** (§10 layer 3) and expose its distinct state (`originVerified: true|false|null`) without conflating it with `hashValid`; (b) **schema-validate** the read payload (Validator L2, [OM-CONF-011]) and surface the two-tier result; (c) accept unknown OPTIONAL fields ([OM-VER-003]) and degrade gracefully on an unknown **major** version ([OM-VER-004], emit `OMW-W001`, never silently misinterpret); and (d) never present `hashValid=true` as authorship or authenticity ([OM-SEC-005], §10). A Consumer L2 MUST NOT populate or trust the reserved `signature` field in 0.1 ([OM-DD]-`meta.signature`).

- **[OM-CONF-010] Validator L1 (consistency checker - schema-independent).** A Validator L1 MUST implement the **warning tier** in full: it MUST evaluate every consistency check whose inputs are present (`OMW-W010`–`OMW-W040`, §H), emit results in the `{code, severity, path, message, expected?, actual?}` shape ([OM-ERR-001]), apply the documented, configurable tolerances ([OM-ERR-002]), and MUST NOT block or mutate the payload. Validator L1 requires **no JSON Schema**; it is the standalone consistency checker of §9 / milestone M1.x and MAY run on any payload, embedded or loose.

- **[OM-CONF-011] Validator L2 (full validator).** A Validator L2 MUST satisfy Validator L1 and additionally implement the **error tier** (`OMV-E001`–`OMV-E004`, §H) against the normative JSON Schema [OM-DD-001], enforce the hard block/never-block boundary ([OM-ERR-001]: errors block `om_embed`, warnings never block), reject a 0.1 payload that populates `meta.signature` (`OMV-E003`), and reproduce the **exact code set** required by [OM-VEC-003] for every applicable vector. Validator L2 is the two-tier `om_validate` of milestone M2.

- **[OM-CONF-012]** A conformance target is meaningful only against a fixed spec version and a fixed conformance suite. A claim MUST bind both ([OM-CONF-013]). The set of vectors a target is judged against is exactly the manifest subset tagged for that role at that level or below ([OM-VEC-006], [OM-VEC-010]).

### §A.2 Conformance-claim format

- **[OM-CONF-013] Machine-readable claim.** An implementation that claims conformance MUST publish a claim document conforming to `/spec/conformance-claim-0.1.schema.json` (JSON Schema 2020-12), conventionally named `openom-conformance.json` and shipped alongside the implementation (repo root and/or release artifact). It MUST contain, at minimum:

```jsonc
{
  "$schema": "https://openom.app/schema/conformance-claim-0.1.schema.json",
  "claimVersion": "1",                       // this claim format's version (independent of specVersion)
  "implementation": {
    "name": "om-cli", "version": "0.4.2",
    "vendor": "Example Corp", "url": "https://github.com/example/om-cli"
  },
  "specVersion": "0.1",                       // the OpenOM spec version claimed
  "claims": [                                   // one entry per role; level 1 or 2
    { "role": "Producer", "level": 2 },
    { "role": "Consumer", "level": 1 }
  ],
  "suite": {                                    // the exact vectors judged against - immutable ref
    "ref": "openom-vectors@0.1.3",
    "commit": "git:9f1c…",
    "manifestHash": "sha256:…"                  // SHA-256 over JCS of manifest.json ([OM-VEC-008])
  },
  "result": {
    "runAt": "2026-09-01T12:00:00Z",
    "runner": "openom-conformance 0.3.1",
    "vectorsApplicable": 118, "vectorsPassed": 118, "vectorsFailed": 0
  },
  "certification": "self",                     // 0.1 has only self-certification ([OM-CONF-016])
  "attestation": "We attest this implementation passed the referenced suite. No third-party or Vervelio certification is implied."
}
```

  A claim is **valid** only if `vectorsFailed == 0` and `vectorsApplicable` equals the count the runner reports for the claimed targets against the referenced suite ([OM-VEC-010]).

- **[OM-CONF-014] Canonical claim string.** The human-readable form MUST be:
  `OpenOM <specVersion> - <Role Ln>[, <Role Ln>…] (self-certified <YYYY-MM-DD>, suite <suite.ref> <suite.manifestHash-short>)`
  e.g. `OpenOM 0.1 - Producer L2, Consumer L1 (self-certified 2026-09-01, suite openom-vectors@0.1.3 sha256:9f1c…)`. Roles MUST be listed in the order Producer, Consumer, Validator. The string MUST NOT omit the `self-certified` qualifier while 0.1 provides only self-certification ([OM-CONF-016]).

- **[OM-CONF-015] Anti-overclaim (falsifiability).** An implementation MUST NOT state or imply a role/level it has not passed the full applicable vector set for; MUST NOT claim endorsement, approval, or certification **by Vervelio or any body** (0.1 defines none); MUST NOT reference a mutable suite (the `suite` ref and `manifestHash` MUST pin an immutable, published suite release); and MUST NOT present a partial run (`vectorsFailed > 0`, or a filtered subset) as conformance. Because vectors are public and deterministic ([OM-VEC-009]–[OM-VEC-011]), any claim is refutable by re-running the pinned suite; a refuted claim SHOULD be corrected or withdrawn. The word "conformant" (unqualified) is reserved for a valid claim per [OM-CONF-013].

### §A.3 Self-certification procedure & governance of claims

- **[OM-CONF-016] Self-certification is the only path in 0.1.** There is **no central certification authority** in 0.1. An implementer self-certifies by executing the following, which MUST all hold for a valid claim:
  1. **Pin** an immutable, published conformance-suite release (`suite.ref` + `suite.commit` + `suite.manifestHash`, [OM-VEC-008]).
  2. **Run** a conformance runner ([OM-VEC-010]) over the manifest, restricted to the vectors applicable to each claimed target ([OM-VEC-006]).
  3. **Verify** every applicable vector passes (`vectorsFailed == 0`).
  4. **Emit** the machine-readable result into the claim document ([OM-CONF-013]).
  5. **Publish** `openom-conformance.json` with the implementation and, where displayed, the canonical string ([OM-CONF-014]).

- **[OM-CONF-017] Re-certification triggers.** A published claim is bound to `(specVersion, suite)`. An implementation MUST re-run and re-publish (or withdraw) its claim when **any** of the following occurs before continuing to assert the claim: (a) it targets a new `specVersion`; (b) a **new suite release adds or changes vectors** applicable to a claimed role/level (a minor suite bump that only adds vectors can only *narrow* an existing claim, so silence is not conformance); or (c) the implementation changes behavior in a claimed role. A claim whose `suite.ref` is older than the current published suite is **stale**, not invalid, and SHOULD state the suite it was certified against (it already does, per [OM-CONF-014]).

- **[OM-CONF-018] Voluntary claim registry (post-0.1).** Vervelio MAY host a **voluntary, opt-in** public registry of submitted claims (registry era, §11). Listing in it MUST NOT be construed as certification, endorsement, or verification by Vervelio beyond "a claim was submitted and its pinned suite re-ran green in a public runner." The registry MUST record the `suite.manifestHash` and the re-run result so any party can reproduce it. No feature or conformance status MAY be gated on registry listing.

- **[OM-CONF-019] Deprecated requirements & claims.** When a requirement is withdrawn per [OM-CONF-002] (marked *Deprecated*, never deleted), vectors that exercise only deprecated requirements MUST be retagged or retired in the next suite release, and the coverage gate ([OM-VEC-016]) recomputed. A claim against a suite predating the deprecation remains a valid historical claim for the `specVersion` it named.

### §A.4 Requirement traceability

- **[OM-CONF-020] Forward + reverse traceability.** Traceability MUST be bidirectional. Forward (test→requirement) is [OM-CONF-003]: every vector declares the requirement IDs it exercises (`requirements[]`, [OM-VEC-006]). Reverse (requirement→test) MUST be a **generated** artifact `/spec/vectors/traceability.json` mapping each `[OM-*]` ID to the set of vectors that exercise it, produced deterministically from the manifest and checked into the repo so a reader can audit coverage without running anything.

- **[OM-CONF-021] Coverage gate (CI).** Every normative **`MUST`/`MUST NOT`/`REQUIRED`/`SHALL`** requirement that is *testable and applicable to a role* MUST be exercised by at least one vector for that role. CI MUST fail if any such requirement has zero covering vectors in `traceability.json`. A requirement that is inherently non-vector-testable (e.g. governance/process requirements in §L, licensing §G, telemetry-absence §M beyond an observable-network assertion) MUST be explicitly enumerated in an `untestable[]` allowlist in the manifest with a one-line justification, so the gap is deliberate and reviewed, never accidental. `SHOULD`/`MAY` requirements SHOULD have vectors where practical but do not gate.

---

## §B. Conformance suite & interop test vectors

- **[OM-VEC-001]** `/spec/vectors/` MUST contain canonical test vectors committed to the repo: (a) `payloads/*.json` - valid and intentionally-invalid payloads; (b) `expected/*.json` - for each payload, its JCS form, its `sha256:` hash, and its expected `om_validate` report (error/warning codes); (c) `pdfs/*.pdf` - golden embedded OMs with a sidecar `*.expected.json` describing the payload, hash, and XMP fields.
- **[OM-VEC-002]** The **cross-implementation round-trip test** MUST assert: a payload embedded by `/js` (pdf-lib) and read by `/core` (pikepdf) yields byte-for-byte identical **decompressed payload bytes** and an identical `sha256:` hash, and vice versa. This test MUST run in CI on every commit.
- **[OM-VEC-003]** A Producer MUST reproduce, for every vector in `payloads/`, the exact `sha256:` hash in `expected/`. A Validator MUST reproduce the exact code set. Divergence is a conformance failure.
- **[OM-VEC-004]** Vectors MUST cover the fixture *pathology matrix* (§14): native/hybrid/scanned PDFs, CMYK/SMask images, empty payload, hash mismatch, non-contiguous rent schedule, `pro-forma` NOI, superseded re-embed.

### §B.1 Vector directory layout & manifest

- **[OM-VEC-005] Directory layout (normative).** `/spec/vectors/` MUST have the following shape; this supersedes the prose of [OM-VEC-001] by fixing exact locations while preserving its contents:

```
/spec/vectors/
  manifest.json            # machine-readable index of every vector ([OM-VEC-006])
  traceability.json        # generated requirement→vector map ([OM-CONF-020])
  payloads/*.json          # input payloads: valid and intentionally-invalid
  expected/*.jcs.json      # per payload: its exact JCS byte form ([OM-CANON-001])
  expected/*.report.json   # per payload: expected om_validate report ([OM-VEC-009])
  pdfs/*.pdf               # golden embedded OMs
  pdfs/*.expected.json     # per pdf: payload ref, hash, XMP fields, class
  contexts/                # pinned @context snapshots for offline, deterministic runs
```

- **[OM-VEC-006] Manifest schema.** `manifest.json` MUST conform to `/spec/vectors/manifest-0.1.schema.json` and list every vector as an object with these fields (`?` = OPTIONAL):

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Stable, unique, append-only vector id (e.g. `vec-embed-native-001`). MUST NOT be renumbered/reused ([OM-CONF-002] semantics). |
| `kind` | enum `payload`\|`pdf`\|`roundtrip` | What the runner does with it ([OM-VEC-010]). |
| `title` | string | Human label. |
| `roles` | array of `Producer`\|`Consumer`\|`Validator` | Which roles this vector exercises. |
| `levels` | object role→int | Minimum level per role at which the vector applies (e.g. `{"Producer":2}`). |
| `requirements` | array of `OM-*` ids | Requirements exercised - feeds traceability ([OM-CONF-020]). MUST be non-empty. |
| `dimensions` | object | `{ "producer": <enum §B.3>, "pathology": [<enum §B.3>…] }` for coverage ([OM-VEC-013]). |
| `input` | path | `payloads/…json` or `pdfs/…pdf`. |
| `expected` | object | Expected results ([OM-VEC-007], [OM-VEC-008]). |
| `tolerances?` | object | Per-vector overrides of the §H defaults ([OM-ERR-002]); absent = defaults. |
| `notes?` | string | Rationale / provenance pointer. |

```jsonc
// example manifest entry
{
  "id": "vec-rent-noncontiguous-001",
  "kind": "payload",
  "title": "NNN payload with a gap between rent periods",
  "roles": ["Validator"],
  "levels": { "Validator": 1 },
  "requirements": ["OM-DD-005", "OM-ERR-001"],
  "dimensions": { "producer": "n/a", "pathology": ["rent-gap"] },
  "input": "payloads/rent-noncontiguous-001.json",
  "expected": {
    "valid": true,                                  // schema-valid; consistency is a warning
    "jcs": "expected/rent-noncontiguous-001.jcs.json",
    "payloadHash": "sha256:2b1e…",
    "report": "expected/rent-noncontiguous-001.report.json"
  }
}
```

- **[OM-VEC-007] PDF-vector expected sidecar.** For a `kind:"pdf"` vector, `pdfs/<name>.expected.json` MUST declare: `embeddedFilename` (MUST be `om.json`), `class` (`native`\|`hybrid`\|`scanned`), `payloadHash` (§C integrity hash), the required XMP properties [OM-XMP-002] (`specName`, `specVersion`, `payloadFilename`, `payloadHash`, `assertedDate`, and `supersedes` when applicable), and a reference to the canonical payload JSON the embedded stream MUST decompress to. It MUST NOT assert whole-PDF byte equality ([OM-VEC-011]).

### §B.2 Expected results & runner semantics

- **[OM-VEC-008] Manifest pinning hash.** The `suite.manifestHash` referenced by a claim ([OM-CONF-013]) MUST be `"sha256:" + lowercase_hex(SHA-256(JCS(manifest.json)))`, computed with the §C canonicalization so it is implementation-independent. Two runners MUST derive the same `manifestHash` for the same manifest.

- **[OM-VEC-009] Expected validate-report matching.** An expected `report` declares `errors[]` and `warnings[]`, each a Finding subset `{code, path, expected?, actual?}` per §H. A run **matches** iff the **set of `(code, path)` pairs** produced equals the expected set - comparison is **order-independent** and **message-independent** (human-readable `message` text MUST NOT affect pass/fail; only stable codes and JSON-Pointer paths do). Numeric-consistency warnings MUST be evaluated using the vector's `tolerances` (or the §H defaults, [OM-ERR-002]); a vector that would be tolerance-sensitive MUST pin its `tolerances` so the outcome is deterministic.

- **[OM-VEC-010] Conformance runner (normative behavior).** A conformance runner MUST: (1) load and hash the manifest ([OM-VEC-008]); (2) select, per claimed target, exactly the vectors whose `roles`/`levels` include that target (level L2 selects L1+L2 vectors); (3) execute each vector by `kind` - `payload` → validate and compare report ([OM-VEC-009]) and, for producer targets, canonicalize+hash and compare to `payloadHash`; `pdf` → detect/read and compare hash, XMP, class ([OM-VEC-007]); `roundtrip` → the cross-impl assertion of [OM-VEC-002] in both directions; (4) report `vectorsApplicable`, `vectorsPassed`, `vectorsFailed`. A single mismatched hash or code-set is a **fail** for that vector; divergence is a conformance failure ([OM-VEC-003]).

- **[OM-VEC-011] Golden-PDF comparison scope.** For `pdf`/`roundtrip` vectors the runner MUST compare the **decompressed `om.json` payload bytes** and the §C integrity hash, and the required XMP properties - **not** the whole PDF byte stream. `/ModDate`, `/CreationDate`, object numbering, and stream-compression choices are cosmetic and MUST NOT affect pass/fail ([OM-EMB-011], [OM-CANON-005]). Whole-PDF byte equality MUST NOT be required by any vector.

- **[OM-VEC-012] Determinism & no live network.** A conformance run MUST be reproducible: identical (implementation, suite) MUST yield identical results. Runs MUST NOT depend on live internet. Vectors that exercise URL re-fetch, SSRF defenses ([OM-SEC-001]), or domain-origin verification (§10 layer 3) MUST target fixtures / loopback stubs / `contexts/` snapshots committed to the suite, and MUST assert the *decision* (e.g. "refused: private range", "originVerified:false") rather than fetching a real host. Negative security vectors (decompression bomb [OM-SEC-002], duplicate keys / over-deep nesting [OM-SEC-004]) MUST assert rejection with the documented code (`OM-IO-BOMB`, etc.).

### §B.3 Coverage matrix (producer × pathology)

- **[OM-VEC-013] Producer dimension (enumerated).** Every `pdf`/`roundtrip` vector's `dimensions.producer` MUST be one of: `InDesign`, `Word-to-PDF`, `Buildout`, `scanned-flattened`, `library-generated` (pikepdf/pdf-lib synthetic), `other`. `payload`-only vectors use `n/a`. The suite MUST include `pdf` vectors from **at least three distinct real-producer values** (i.e. excluding `library-generated`/`n/a`), because cross-producer variance - object streams, linearization, XMP placement - is where detection and embedding break (§12 fixture-skew risk).

- **[OM-VEC-014] Pathology dimension (enumerated).** `dimensions.pathology[]` values MUST be drawn from: `rent-messy`, `rent-gap`, `rent-overlap`, `cmyk-smask`, `icc-colorspace`, `tiled-striped`, `flattened-scan`, `empty-payload`, `hash-mismatch`, `pro-forma-noi`, `superseded-reembed`, `object-stream-hidden`, `oversized-payload`, `duplicate-keys`, `unknown-major`, `origin-unverified`. This set is append-only; adding a pathology is a minor suite release ([OM-CONF-017]).

- **[OM-VEC-015] Coverage floor (matrix).** The suite MUST satisfy, at minimum:

| Requirement | Floor |
|---|---|
| Each pathology in [OM-VEC-014] | ≥ 1 vector |
| Distinct real producers ([OM-VEC-013]) among `pdf` vectors | ≥ 3 |
| Document classes (`native`, `hybrid`, `scanned`) | ≥ 1 `pdf` vector each |
| Cross-impl round-trip ([OM-VEC-002]) | ≥ 1 vector, both directions |
| Idempotent multi-re-embed `supersedes` chain ([OM-CONF-007]) | ≥ 1 vector, ≥ 2 successive re-embeds |
| Image-bearing pathologies (`cmyk-smask`, `icc-colorspace`, `tiled-striped`) | ≥ 1 `pdf` vector each, on a real producer |
| Negative security vectors (`oversized-payload`, `duplicate-keys`) | ≥ 1 each ([OM-SEC-002], [OM-SEC-004]) |

- **[OM-VEC-016] Coverage gate (CI).** A `coverage.json` MUST be generated deterministically from the manifest and checked in. CI MUST fail if any floor in [OM-VEC-015] is unmet, if any pathology of [OM-VEC-014] has zero vectors, or if the requirement-coverage gate [OM-CONF-021] fails. Milestone **M1 MUST NOT exit** until the producer/class/cross-impl/image-bearing floors are green (§14 fixture-matrix), mirroring the fixture-matrix exit condition.

### §B.4 Vector provenance, redaction & licensing

- **[OM-VEC-017] Fixtures vs. vectors (distinct corpora).** The private **fixtures** of §14 (real, possibly unreleased OMs used for internal testing) are distinct from the committed, public **vectors** of §B. Real OMs MUST NOT be committed to `/spec/vectors/` unless they are either (a) synthetic, or (b) **redacted/anonymized**: fictional parties, no real broker PII, no real street address, geo, or APN, and no confidential pricing tied to an identifiable real deal. Each `pdf` vector's `.expected.json` MUST record `provenance` (`synthetic`\|`redacted-real`) and, for `redacted-real`, that redaction was reviewed. This preserves producer diversity ([OM-VEC-013]) while keeping the suite publishable.

- **[OM-VEC-018] Vector licensing.** All conformance vectors (payloads, expected files, golden PDFs, manifest) are part of the specification corpus and are licensed **CC-BY-4.0** to Vervelio ([OM-LIC-002]), so any implementation MAY redistribute them to substantiate its claim ([OM-CONF-013]). A contributor submitting a `redacted-real` vector MUST warrant they have the right to license it under CC-BY-4.0. The suite MUST NOT include any vector whose redistribution is restricted.

---

## §C. Canonicalization & hashing (the interop keystone)

- **[OM-CANON-001]** The canonical serialization of a payload MUST be **RFC 8785 JSON Canonicalization Scheme (JCS)**: UTF-8 encoding, **no BOM**, object keys sorted lexicographically by UTF-16 code unit, **no insignificant whitespace**, and numbers serialized per RFC 8785 §3.2.2.3 (ECMAScript `Number` shortest round-trip; no trailing zeros, no leading `+`, exponent form only per the algorithm).
- **[OM-CANON-002]** Array element order is significant and MUST be preserved (JCS sorts object keys only). `rentSchedule` order therefore carries meaning and MUST reflect chronological periods.
- **[OM-CANON-003]** The **integrity hash** is `"sha256:" + lowercase_hex( SHA-256( JCS(payload_for_hash) ) )`, where `payload_for_hash` is the full payload with `meta.signature` **removed** (not set to null - the key is absent) so that adding a signature later does not change the hash. The integrity hash MUST NOT be stored inside the payload; it lives in XMP (§D) to avoid self-reference.
- **[OM-CANON-004]** `meta.sourceDocHash` is a distinct value: `"sha256:" + lowercase_hex( SHA-256( original_source_PDF_bytes ) )` computed over the source document **before** embedding. It answers "which document does this payload describe," not "has the payload been altered." It is OPTIONAL and, when present, is part of `payload_for_hash`.
- **[OM-CANON-005]** The embedded-file stream (§D) MUST contain exactly the JCS bytes (a Producer MUST NOT pretty-print, re-key, or re-encode). Stream-level Flate compression is permitted; the hash is always computed over the **decompressed** bytes, so compression choice MUST NOT affect the hash.
- **[OM-CANON-006]** Monetary amounts are numbers in **major units** of the payload currency; whole-dollar values (e.g. `askingPrice`) SHOULD be integers; sub-unit values (e.g. per-month rent) MAY carry up to 2 decimals - but note JCS drops trailing zeros (`12.70`→`12.7`), so Producers MUST NOT rely on trailing-zero formatting for equality.
- **[OM-CANON-007]** Rates and percentages are decimal fractions: `capRate: 0.0625` means 6.25%. Producers MUST NOT encode `6.25`.

> **Why this is §C and not a footnote:** the named cross-impl round-trip test (§8a/§B) is *undefinable* without a canonical byte form. This section is the single technical dependency the whole "it's a standard, not a fork per vendor" claim rests on.

### §C.1 Preprocessing before canonicalization (mandatory)

RFC 8785 canonicalizes an *already-parsed* JSON value; it deliberately performs **no Unicode normalization** and **assumes unique member names** (RFC 8785 §3.1). OpenOM therefore mandates the preprocessing below *before* JCS is applied. Skipping any step lets two payloads that render identically to a human produce different bytes, a different hash, and a silent fork.

- **[OM-CANON-008] Unicode NFC.** Every JSON string value **and** every object member name MUST be normalized to **Unicode Normalization Form C (NFC)** before canonicalization. Producers MUST emit NFC. Consumers MUST verify integrity by hashing the payload **exactly as received** and MUST NOT silently re-normalize a received payload before hashing - re-normalizing would mask a genuine mismatch. *Worked:* the tenant value "café" as NFC (`é` = U+00E9, UTF-8 `63 61 66 c3 a9`) canonicalizes to `{"tenantEntity":"café"}` with SHA-256 `851b8c23eb02709cb52f013fff5215d8b1d836fa2283fbf8e7c35dbbc5a48ddf`; the NFD form (`e` + combining acute U+0301, UTF-8 `63 61 66 65 cc 81`) canonicalizes to `{"tenantEntity":"café"}` (byte-different) with SHA-256 `23174d586d5a3470ad9275df333f41c3b0e704b0d37447954a9efc74753f7a38`. Identical glyphs, different hash - NFC removes the ambiguity.

- **[OM-CANON-009] No duplicate member names.** Within any single object a member name MUST NOT appear more than once (compared after NFC). Producers MUST NOT emit duplicates; Consumers and Validators MUST **reject** a payload containing them (`OM-IO-DUPKEY`) rather than apply a last-wins/first-wins merge - the two merge strategies fork, and JCS output is undefined when keys repeat. This restates §J [OM-SEC-004] as a canonicalization invariant so it is enforced on the hashing path, not only the parsing path.

- **[OM-CANON-010] Structural preconditions.** The top-level payload MUST be a JSON **object** (never a bare array or scalar). Every string - value or member name - MUST be well-formed Unicode with **no unpaired surrogate** code unit; a payload containing an unpaired surrogate MUST be rejected (`OM-IO-BADUTF8`). Member names are always JSON strings. (The `OM-IO-*` rejection codes join the family already used by §I [OM-MCP-002] and §J's `OM-IO-BOMB`; they are transport/parse rejections, distinct from the §H `OMV-E###` schema codes.)

### §C.2 String & number serialization (pinned to the byte)

These clauses pin the two places real implementations diverge. They **refine, and do not relax,** [OM-CANON-001].

**Strings.**

- **[OM-CANON-011] Minimal escaping only.** String serialization MUST follow RFC 8785 §3.2.2.2: the seven two-character escapes `\"` `\\` `\b` `\t` `\n` `\f` `\r`, and `\u00XX` (lowercase hex) for the remaining C0 control characters U+0000–U+001F; **every other character, including all non-ASCII, MUST be emitted as literal UTF-8.** Producers MUST NOT ASCII-escape non-ASCII characters, and MUST NOT escape the forward slash `/`. *This is a top-tier fork source:* Python's `json.dumps` defaults to `ensure_ascii=True` (it would write `é` for `é`, forking the bytes), and several JavaScript serialization paths over-escape `/` or `<`. A conformant Producer emits, e.g., the euro sign `€` as its three literal UTF-8 bytes `e2 82 ac`, never as `€`.

**Numbers.**

- **[OM-CANON-012] One number model.** Every numeric value in a payload is an **IEEE 754 binary64** ("double"). Its canonical text is the ECMAScript `Number::toString` result as specified by RFC 8785 §3.2.2.3. There is no separate integer type in the JSON data model: `1850000` and `1850000.0` denote the same value and both canonicalize to `1850000`.
- **[OM-CANON-013] Reject non-representable numbers.** A Producer MUST reject any number that does not round-trip **exactly** through binary64 (`OM-IO-NUMRANGE`). In particular, integers whose magnitude exceeds the safe-integer limit **2^53 − 1 = 9007199254740991** are silently rounded by the number model - e.g. `9007199254740993` canonicalizes to `9007199254740992`. Silent rounding is a data corruption, so it MUST be a hard rejection, never a tolerated value. (No OpenOM 0.1 field legitimately requires a value outside the safe-integer range.)
- **[OM-CANON-014] Reject non-finite.** `NaN`, `Infinity`, and `-Infinity` are not JSON numbers and MUST be rejected (`OM-IO-NUMRANGE`).
- **[OM-CANON-015] Formatting invariants.** Negative zero MUST serialize as `0` (per ES `(-0).toString()`); Producers SHOULD NOT emit `-0`. Integral values in range serialize with **no** decimal point and **no** exponent (`1850000`, never `1850000.0` or `1.85e6`). Exponential form is used **only** at the ES thresholds - decimal exponent `< -6` or `≥ 21` (e.g. `1e-7`, `1e+21`) - with a lowercase `e` and a mandatory sign on the exponent; values between those thresholds use plain decimal notation. A formatter that switches to exponents at other thresholds (Python `repr` switches near 1e16 and 1e-5) is **non-conformant**. Trailing zeros are always dropped (`12.70` → `12.7`, `0.10` → `0.1`); Producers MUST NOT rely on trailing-zero or fixed-decimal formatting for equality (this reaffirms [OM-CANON-006]).

### §C.3 Integrity-hash preimage (exact construction)

- **[OM-CANON-016] Preimage algorithm.** The integrity hash of a payload P MUST be computed by exactly these steps, in this order:
  1. Verify structural preconditions ([OM-CANON-010]); reject on failure.
  2. Reject on duplicate member names ([OM-CANON-009]) or any non-representable / non-finite number ([OM-CANON-013], [OM-CANON-014]).
  3. NFC-normalize every member name and every string value ([OM-CANON-008]).
  4. Construct P′ by **removing the `signature` member from the `meta` object** if present - *removed entirely, not set to `null`.* No other member is removed or altered.
  5. Canonicalize P′ with RFC 8785 JCS → UTF-8 byte string B ([OM-CANON-001]–[OM-CANON-002], [OM-CANON-011]–[OM-CANON-015]).
  6. `integrityHash = "sha256:" + lowercase_hex( SHA-256( B ) )`.

  The result is stored as `omspec:payloadHash` in XMP (§D [OM-XMP-002]) and MUST NOT appear inside the payload ([OM-CANON-003]).

- **[OM-CANON-017] Field inclusion is exhaustive and closed.** `meta.signature` is the **only** field excluded from the preimage, and it is excluded for one reason: a signature - which, when it graduates from reserved (§10, layer 4) will sign the integrity hash - can then be added to `meta` **without** changing that hash. **Every other field is included in the preimage,** explicitly `meta.sourceDocHash` ([OM-CANON-004]) and `meta.supersedes`: both are part of the broker's assertion (which source document; which prior payload this one replaces), so altering either MUST change the hash. Implementations MUST NOT introduce any additional exclusion, allow-list, field-dropping, or field-reordering step beyond JCS member-name sorting.

### §C.4 `payloadHash` vs `sourceDocHash` - two hashes, never interchanged

Both are `sha256:<lowercase-hex>` strings and both use SHA-256 - which is exactly why the distinction MUST be stated rigorously. They answer different questions, cover different bytes, and live in different places.

| | `payloadHash` (integrity hash) | `meta.sourceDocHash` |
|---|---|---|
| **Covers** | JCS bytes of the payload, minus `meta.signature` ([OM-CANON-016]) | Raw bytes of the **original source PDF**, before embedding ([OM-CANON-004]) |
| **Answers** | "Has this payload been altered since it was asserted?" | "Which document does this payload describe?" |
| **Lives in** | XMP `omspec:payloadHash` (outside the payload) | Inside the payload, at `meta.sourceDocHash` |
| **In the preimage?** | n/a - it *is* the hash | Yes - included in `payloadHash` |
| **Required?** | Always present on an embedded OM | OPTIONAL |
| **On re-embed** | Recomputed; prior value copied to `omspec:supersedes` (§D [OM-XMP-004]) | Unchanged if the source PDF is unchanged |

- **[OM-CANON-018] No interchange.** A Consumer MUST use `omspec:payloadHash` - never `meta.sourceDocHash` - for the integrity / tamper check ([OM-XMP-003]). `meta.sourceDocHash` is a provenance pointer, not an integrity control, and MUST NOT be surfaced to a user as tamper-evidence. Neither of these is the PDF `/Params /CheckSum` (legacy MD5, §D [OM-EMB-005]), which MUST be ignored for every trust decision ([OM-SEC-005]).

### §C.5 Worked examples (conformance-grade)

Each example gives an input JSON (formatted for reading), the exact single-line JCS byte string a conformant Producer MUST emit, its UTF-8 byte length, and its SHA-256. These are normative anchors: the identical cases live in `/spec/vectors/` (§B [OM-VEC-001]) and every Producer MUST reproduce the exact hashes ([OM-VEC-003]).

**Example 1 - key sorting + whitespace removal.**

Input:
```json
{ "b": 2, "a": 1 }
```
JCS (13 bytes): `{"a":1,"b":2}`
SHA-256: `43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777`

**Example 2 - member-name ordering by UTF-16 code unit (the code-unit-vs-code-point trap).**

Input:
```json
{ "￿": "bmp-max", "😀": "grinning", "Z": 1, "a": 2 }
```
JCS (47 bytes): `{"Z":1,"a":2,"😀":"grinning","￿":"bmp-max"}`
SHA-256: `856d9d6d59d4a593c79e78e3609435b72487f44e70bf0ea03d16eb2bab0aba31`

Ordering is `Z` (U+005A) < `a` (U+0061) < `😀` (U+1F600 → UTF-16 units `D83D DE00`) < `￿` (U+FFFF). Note `😀` sorts **before** `￿`: its first UTF-16 code unit `0xD83D` is less than `0xFFFF`. Under *code-point* ordering U+1F600 would sort *after* U+FFFF - the opposite result. This one case is why [OM-CANON-001] mandates UTF-16 code-unit ordering; an implementation that sorts by code point forks here.

**Example 3 - number normalization.**

Input:
```json
{ "capRate": 0.0625, "askingPrice": 1850000, "noi": 115625, "rentPSF": 12.70, "escalationFromPrior": 0.10 }
```
JCS (94 bytes): `{"askingPrice":1850000,"capRate":0.0625,"escalationFromPrior":0.1,"noi":115625,"rentPSF":12.7}`
SHA-256: `3a47e6986d2df5054d4d833871b13781e9edf14ff15b1a3a31a4d2b6b5db6288`

`12.70` → `12.7` and `0.10` → `0.1` (trailing zeros dropped); integers are unchanged; `capRate` stays `0.0625` and is never `6.25` ([OM-CANON-007]).

**Example 4 - signature exclusion from the preimage.**

Input (a signed payload - `meta.signature` is populated here *only* to demonstrate exclusion; populating it in a real 0.1 payload is `OMV-E003`, §H):
```json
{
  "specVersion": "0.1",
  "assertedDate": "2026-08-15",
  "deal": { "askingPrice": 1850000, "capRate": 0.0625, "noi": 115625, "noiType": "in-place" },
  "meta": {
    "sourceDocHash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "supersedes": null,
    "signature": { "alg": "ed25519", "sig": "AAAA" }
  }
}
```
Preimage (after removing `meta.signature`, [OM-CANON-016] step 4), JCS (248 bytes):
`{"assertedDate":"2026-08-15","deal":{"askingPrice":1850000,"capRate":0.0625,"noi":115625,"noiType":"in-place"},"meta":{"sourceDocHash":"sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","supersedes":null},"specVersion":"0.1"}`
SHA-256 (this value becomes `omspec:payloadHash`): `aa631ed617b85ac226ef4f6ae97e5387a60fdc51c6e49f42c35034c113ca16f7`

The identical payload with `meta.signature` **absent** produces byte-identical JCS and the same hash - proving that adding a signature later does not disturb the integrity hash ([OM-CANON-017]). (`meta.sourceDocHash` here is the SHA-256 of an empty byte string, used only as a syntactically valid illustrative value.)

### §C.6 Normative note - numbers are the #1 cross-implementation hazard

> **This note is normative in intent and explains the strictness of §C.2.** More interop failures in JSON-canonicalization standards trace to number formatting than to everything else combined, because JSON has a single `number` type while every implementation language has several, and the mapping is lossy and non-obvious:
>
> - **integer vs float:** `1850000` vs `1850000.0` - JCS unifies both to `1850000`; a library that preserves the decimal forks;
> - **trailing zeros / fixed decimals:** `12.70` vs `12.7`; currency code that formats to two places forks;
> - **exponent thresholds:** ECMAScript switches to exponential at decimal exponent `< -6` / `≥ 21`; Python `repr` switches at different points; Java `BigDecimal`, Go, and .NET each differ again;
> - **precision beyond binary64:** big-integer or arbitrary-precision libraries preserve digits ECMAScript silently rounds (`9007199254740993` → `…992`);
> - **negative zero, locale decimal separators (`,`), and a leading `+`.**
>
> Because the integrity hash is over **bytes**, any one of these yields a *different hash for a payload that looks correct on screen* - a payload that verifies in its Producer and fails in every other Consumer. That is precisely the silent cross-implementation drift §8a names as *fatal to a standard*.
>
> **How the standard removes the freedom.** [OM-CANON-012]–[OM-CANON-015] eliminate every degree of freedom above; the reference behavior is the ECMAScript `Number::toString` algorithm (RFC 8785 §3.2.2.3), the same algorithm exercised by the RFC 8785 test suite.
>
> - **[OM-CANON-019]** `/spec/vectors/` MUST include a dedicated **number-serialization torture vector** exercising, at minimum: a whole-dollar integer, a decimal-fraction rate (`0.0625`), a trailing-zero input (`12.70` → `12.7`), both exponent-threshold boundaries (`1e-7`, `1e+21`), the max safe integer (`9007199254740991`, accepted), and a non-representable integer (`9007199254740993`, **rejected** with `OM-IO-NUMRANGE`). Every Producer MUST reproduce each accepted case's exact SHA-256 and MUST reject the non-representable case; the cross-implementation round-trip test (§B [OM-VEC-002]) MUST run this vector through both `/js` (pdf-lib) and `/core` (pikepdf) on every commit ([OM-VEC-003]). A Producer that cannot reproduce the vector hashes is non-conformant.

---

## §D. Embedded-file & XMP wire format (exact)

Grounded in the actual libraries: pikepdf `AttachedFileSpec`/`Pdf.attachments`, pdf-lib `PDFDocument.attach(..., { afRelationship: AFRelationship.Data })`.

### §D.1 Embedded file
- **[OM-EMB-001]** The payload MUST be embedded as a PDF embedded file named exactly `om.json`, referenced from the document catalog `/Names /EmbeddedFiles` name tree.
- **[OM-EMB-002]** The catalog MUST contain an `/AF` (Associated Files) array referencing the payload's `/Filespec` (Factur-X / PDF/A-3 mechanism). *Implementation note:* pdf-lib's `attach` adds `/AF` when `afRelationship` is set; pikepdf requires the `AttachedFileSpec` to carry `relationship = Name.Data` and the Producer MUST verify the `/AF` array is present on the catalog (assigning to `Pdf.attachments` alone populates `/EmbeddedFiles` but a conformant Producer MUST ensure `/AF` too).
- **[OM-EMB-003]** The `/Filespec` dictionary MUST set: `/Type /Filespec`, `/F (om.json)`, `/UF (om.json)` (both, for reader compatibility), `/AFRelationship /Data`, and `/EF << /F <stream> /UF <stream> >>`. `/Desc` is OPTIONAL.
- **[OM-EMB-004]** The embedded-file stream MUST set `/Type /EmbeddedFile` and `/Subtype` to the name-escaped MIME type `/application#2Fld+json` (i.e. `application/ld+json`). Consumers MUST also accept `/application#2Fjson` (`application/json`) for forward tolerance but Producers MUST write `application/ld+json`.
- **[OM-EMB-005]** `/Params` SHOULD include `/Size` (decompressed byte length) and `/ModDate`. The PDF `/Params /CheckSum` is defined by ISO 32000 as an **MD5** digest of the uncompressed bytes; it is legacy and **MUST NOT** be treated as the integrity mechanism. Integrity is the SHA-256 in XMP (§D.2, §C). Producers MAY write `/CheckSum` for reader compatibility; Consumers MUST ignore it for trust decisions.

### §D.2 XMP marker (detection + integrity)
- **[OM-XMP-001]** The document catalog `/Metadata` XMP stream MUST carry an OpenOM RDF description under namespace URI `https://openom.app/ns/0.1#` (placeholder until §15 Q1), RECOMMENDED prefix `omspec`.
- **[OM-XMP-002]** Required XMP properties: `omspec:specName` (string, `"OpenOM"`), `omspec:specVersion` (`"0.1"`), `omspec:payloadFilename` (`"om.json"`), `omspec:payloadHash` (the §C integrity hash), `omspec:assertedDate` (ISO 8601 date). OPTIONAL: `omspec:supersedes` (prior `payloadHash`).
- **[OM-XMP-003]** Detection order for a Consumer: (1) parse XMP for `omspec:payloadHash`; (2) locate `om.json` via `/AF`→`/Filespec`→`/EF`; (3) decompress, recompute the §C hash, compare to `omspec:payloadHash`; (4) schema-validate (§E). A Consumer MUST report `hash-mismatch` if step 3 disagrees and MUST NOT treat a mismatched payload as trusted.
- **[OM-XMP-004]** Re-embed (§4 idempotency): a Producer MUST replace the existing `om.json` stream and `/AF` entry in place, update all XMP properties, set `omspec:supersedes` to the prior `omspec:payloadHash`, and MUST NOT leave a second `om.json` in `/EmbeddedFiles`.

### §D.3 Cross-implementation gotchas (normative cautions)

- **[OM-EMB-010]** Producers MUST NOT let a library re-serialize the JSON; pass the JCS bytes directly (`Pdf.attachments['om.json'] = jcs_bytes` in pikepdf; `attach(jcs_bytes, 'om.json', …)` in pdf-lib).
- **[OM-EMB-011]** `/ModDate`/`/CreationDate` differences between implementations are cosmetic and MUST NOT affect the payload hash (which covers JSON only), nor conformance.
- **[OM-EMB-012]** Filename casing MUST be exactly `om.json` (lowercase) in both `/F` and `/UF`.
- **[OM-EMB-021]** *Object streams.* pikepdf/qpdf writes compressed object streams and cross-reference streams by default. This is conformant output, but a `/js` Consumer (pdf.js / pdf-lib) MUST parse compressed object streams to find `/EmbeddedFiles` (OM-XMP-006). A round-trip test MUST include a pikepdf-saved fixture read by `/js` to exercise this path.
- **[OM-EMB-022]** *Pass bytes, never objects (pdf-lib).* In `/js`, the payload MUST be handed to `attach()` as a `Uint8Array` of the JCS bytes. Building a JS object and letting `JSON.stringify` run reorders keys and inserts whitespace, breaking the §C hash. This is the JS-side corollary of OM-EMB-010.
- **[OM-EMB-023]** *Library XMP regeneration.* Some pipelines regenerate or overwrite `/Metadata` on save (e.g. setting document info via pdf-lib, or Adobe round-trips). A Producer MUST (re-)inject the `omspec:*` properties **after** any such step and MUST verify OM-XMP-013 (existing `dc:`/`pdf:`/`xmp:` preserved, omspec present) on the final saved bytes - not on the in-memory model.
- **[OM-EMB-024]** *pikepdf content normalization.* `Pdf.save(..., normalize_content=True)` and `linearize=True` may rewrite content-stream bytes; the former is forbidden for non-destructive embed (OM-EMB-020). Use object-stream generation and garbage collection (`object_stream_mode`, `qdf=False`) but leave content untouched.
- **[OM-EMB-025]** *Shared indirect objects across libraries.* When constructing the `/Filespec` manually (rather than via `Pdf.attachments[...] = AttachedFileSpec(...)` / pdf-lib `attach`), a Producer MUST ensure the name-tree ref and `/AF` ref are the same object (OM-EMB-006) and `/EF /F`/`/UF` are the same stream (OM-EMB-007). Manual construction that mints two objects is the classic duplicate-`om.json` bug.
- **[OM-EMB-026]** *`/UF` text-string encoding.* `/UF` is a PDF text string; for the pure-ASCII value `om.json` both PDFDocEncoding and UTF-16BE (leading `FEFF`) are valid. Producers SHOULD write the ASCII literal; Consumers MUST decode a UTF-16BE `/UF` (strip the BOM) before comparing to `om.json` (OM-EMB-014).
- **[OM-EMB-027]** *Compression is not part of the contract.* pikepdf and pdf-lib may choose different `/Filter` settings or none. Because the §C hash is over decompressed bytes (OM-CANON-005), the two outputs MUST yield identical decompressed payload bytes and an identical hash even when their on-wire `/Length` differs. The cross-impl test (OM-VEC-002) asserts decompressed-byte and hash equality, never PDF-byte equality.
- **[OM-EMB-028]** *MIME subtype survival.* Confirm on read that the decoded `/Subtype` is `application/ld+json` (or accepted `application/json`, OM-EMB-004); some libraries default an embedded file's `/Subtype` to `application#2Foctet-stream` when the MIME argument is omitted - a Producer MUST set the MIME type explicitly (pikepdf `AttachedFileSpec(..., mime_type='application/ld+json')`; pdf-lib `attach(..., { mimeType: 'application/ld+json' })`).

### §D.0 Object graph (the required topology)

A conformant OpenOM document links **exactly four** logical nodes off the catalog, with two of them shared by reference. The reference topology is:

```
                        +-------------------------------+
                        |  /Root  (Document Catalog)    |
                        +---------------+---------------+
           +----------------------------+----------------------------+
           |                            |                            |
   +-------v--------+          +---------v---------+        +---------v---------+
   | /Names (dict)  |          | /AF   (array)     |        | /Metadata (stream)|
   +-------+--------+          |  [ 12 0 R ]       |        |  XMP RDF/XML      |
           |                   +---------+---------+        |  omspec:payload   |
   +-------v-------------+               |                  |  Hash, specVer... |
   | /EmbeddedFiles      |               |                  +-------------------+
   |  (name tree)        |               |
   |  /Names [ (om.json) |               |
   |           12 0 R ]  |               |
   +-------+-------------+               |
           |                            |
           |   BOTH must reference the   |
           |   SAME /Filespec object     |
           +-------------+---------------+
                         |
              +----------v----------------------------------+
              | 12 0 obj   /Filespec                        |
              |   /Type /Filespec                           |
              |   /F  (om.json)   /UF (om.json)             |
              |   /AFRelationship /Data                     |
              |   /EF << /F 13 0 R   /UF 13 0 R >>          |
              +----------+----------------------------------+
                         |
              /F and /UF must reference the SAME stream
                         |
              +----------v----------------------------------+
              | 13 0 obj   /EmbeddedFile   (stream)         |
              |   /Type /EmbeddedFile                       |
              |   /Subtype /application#2Fld+json           |
              |   /Params << /Size N  /ModDate (D:...)      |
              |             /CheckSum <md5>  (LEGACY,       |
              |                        NOT trust, see D.4)>>|
              |   stream ...JCS bytes (optionally Flate)... |
              |   endstream                                 |
              +---------------------------------------------+
```

- **[OM-EMB-006]** The `/EmbeddedFiles` name tree entry for `(om.json)` and the `/AF` array entry MUST be the **same indirect `/Filespec` object** (one object, referenced twice). A Producer MUST NOT create two distinct `/Filespec` objects for the one payload. A Consumer that discovers the payload via the name tree and the payload via `/AF` and finds them pointing at different objects MUST treat the document as malformed and report ambiguity (OM-XMP-007).
- **[OM-EMB-007]** Within the `/Filespec`, `/EF /F` and `/EF /UF` MUST reference the **same** indirect `/EmbeddedFile` stream object. A Producer MUST NOT write two stream copies; a Consumer MUST read `/EF /F` first and fall back to `/EF /UF` only if `/F` is absent.
- **[OM-EMB-008]** The `/EmbeddedFile` stream, the `/Filespec`, and every intermediate name-tree node MUST be reachable from `/Root` after save (no dependence on the incremental-update trailer alone). A Producer MUST verify reachability after write; an object left only in a superseded revision does not conform.

#### §D.1.1 Dictionary key reference (normative)

- **[OM-EMB-009]** A conformant Producer MUST emit dictionaries whose keys, PDF object types, and cardinality match the tables below; a Consumer MUST tolerate additional (unknown) keys and MUST NOT reject a document solely for their presence. "Type" is the ISO 32000-1 object type. Names are shown in decoded (logical) form; on the wire they are subject to the escaping of §D.1.2.

**Catalog (`/Root`) keys used by OpenOM**

| Key | Type | Card. | Value | Conf. |
|---|---|---|---|---|
| `/Names` | dictionary | 1 | container for `/EmbeddedFiles` | MUST |
| `/Names /EmbeddedFiles` | name tree | 1 | maps `(om.json)` → `/Filespec` ref | MUST |
| `/AF` | array of indirect refs | 1 | contains the `/Filespec` ref (§D.1.3) | MUST |
| `/Metadata` | stream (`/Type /Metadata /Subtype /XML`) | 1 | XMP carrying `omspec:*` (§D.2) | MUST |

**`/Filespec` dictionary**

| Key | Type | Card. | Value | Conf. |
|---|---|---|---|---|
| `/Type` | name | 1 | `/Filespec` | MUST |
| `/F` | text string | 1 | `om.json` (lowercase, exact) | MUST |
| `/UF` | text string | 1 | `om.json` (PDFDocEncoded or UTF-16BE) | MUST |
| `/AFRelationship` | name | 1 | `/Data` | MUST |
| `/EF` | dictionary | 1 | `<< /F <stream> /UF <stream> >>` | MUST |
| `/Desc` | text string | 0..1 | human description | MAY |

**`/EF` sub-dictionary**

| Key | Type | Card. | Value | Conf. |
|---|---|---|---|---|
| `/F` | indirect ref → `/EmbeddedFile` | 1 | the payload stream | MUST |
| `/UF` | indirect ref → `/EmbeddedFile` | 1 | **same object** as `/EF /F` (OM-EMB-007) | MUST |

**`/EmbeddedFile` stream dictionary**

| Key | Type | Card. | Value | Conf. |
|---|---|---|---|---|
| `/Type` | name | 1 | `/EmbeddedFile` | MUST |
| `/Subtype` | name | 1 | `/application#2Fld+json` (§D.1.2) | MUST |
| `/Filter` | name / array | 0..1 | `/FlateDecode` (compression OPTIONAL; hash is over decompressed bytes, OM-CANON-005) | MAY |
| `/Length` | integer | 1 | on-wire (possibly compressed) byte length | MUST |
| `/Params` | dictionary | 0..1 | metadata (below) | SHOULD |
| stream body | bytes | 1 | exactly the JCS bytes (OM-CANON-005), optionally Flate-compressed | MUST |

**`/Params` dictionary**

| Key | Type | Card. | Value | Conf. |
|---|---|---|---|---|
| `/Size` | integer | 0..1 | **decompressed** byte length of `om.json` | SHOULD |
| `/ModDate` | date string | 0..1 | `D:YYYYMMDDHHmmSSOHH'mm'` | SHOULD |
| `/CreationDate` | date string | 0..1 | same format | MAY |
| `/CheckSum` | byte string (16 bytes) | 0..1 | **legacy MD5** of uncompressed bytes - NOT integrity (§D.4) | MAY |

#### §D.1.2 Name-object escaping (normative)

PDF name objects (`/Subtype`, `/AFRelationship`, `/Type`) are subject to ISO 32000-1 §7.3.5 escaping: any byte that is a delimiter, whitespace, the number sign `#` itself, or outside the range `0x21`–`0x7E` MUST be written as `#` followed by two uppercase-or-lowercase hexadecimal digits.

- **[OM-EMB-013]** In the MIME subtype `application/ld+json`, the solidus `/` (0x2F) is a delimiter and MUST be escaped as `#2F`, yielding the on-wire name `/application#2Fld+json`. The plus sign `+` (0x2B) is a regular character in a name object and MUST NOT be escaped by Producers (it is written literally); the letters and the period are written literally. Producers MUST NOT emit an unescaped `/` inside the subtype name, and MUST NOT escape `+` - writing `#2Fld+json` exactly.
- **[OM-EMB-014]** Consumers MUST **decode** name-object escaping to the logical byte string *before* comparing names. A Consumer MUST treat `/application#2Fld+json` and any equivalently-escaped encoding of the same bytes (e.g. `/application#2Fld#2Bjson`) as equal, and MUST match the payload filename `om.json` on its decoded value, not its raw on-wire bytes. Comparison of the MIME subtype MUST be over the decoded string; a Consumer MUST accept both `application/ld+json` and `application/json` per OM-EMB-004.

#### §D.1.3 `/AF` placement (normative)

- **[OM-EMB-015]** The OpenOM payload describes the whole document; its `/Filespec` reference MUST appear in the **document catalog** `/AF` array. Catalog-level placement is what makes it a document-scoped associated file and is the location a Consumer's fast path (OM-XMP-005) reads. Order within the `/AF` array is not significant; other unrelated associated files MAY coexist in the array.
- **[OM-EMB-016]** A Producer MUST NOT associate the OpenOM payload **only** at page level or at any other object's `/AF` (e.g. an annotation or `/StructElem`). A page-level `/AF` MAY additionally reference the payload, but MUST NOT be its sole association. A Consumer MUST NOT be required to scan page or annotation `/AF` arrays to find the payload.

#### §D.2.1 Serialized XMP template (normative)

- **[OM-XMP-010]** The `omspec` RDF description MUST be serialized as RDF/XML inside the catalog `/Metadata` XMP packet, using namespace URI `https://openom.app/ns/0.1#` (placeholder until §15 Q1) bound to the RECOMMENDED prefix `omspec`. All `omspec:*` values are **XMP simple (text) properties** - no arrays, no structs, no language alternatives. The canonical serialization is:

```xml
<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="OpenOM 0.1">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
      xmlns:omspec="https://openom.app/ns/0.1#">
   <omspec:specName>OpenOM</omspec:specName>
   <omspec:specVersion>0.1</omspec:specVersion>
   <omspec:payloadFilename>om.json</omspec:payloadFilename>
   <omspec:payloadHash>sha256:9f2c0a…e41b</omspec:payloadHash>
   <omspec:assertedDate>2026-08-15</omspec:assertedDate>
   <omspec:supersedes>sha256:1a0b…</omspec:supersedes>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
```

- **[OM-XMP-011]** Property value types and forms: `omspec:specName` and `omspec:specVersion` are literal text (`"OpenOM"`, `"0.1"`); `omspec:payloadFilename` is literal text (`"om.json"`); `omspec:payloadHash` is the §C integrity hash as `sha256:<lowercase-hex>`; `omspec:assertedDate` is an ISO 8601 date (`YYYY-MM-DD`); `omspec:supersedes` (OPTIONAL) is a prior `sha256:<hex>` value or is **omitted** when there is no predecessor (its absence, not an empty element, means "original"). A Producer MUST NOT emit `omspec:supersedes` as an empty element. Values MUST be XML-escaped (`&`, `<`, `>`); the hash and date values contain none of these but the rule is normative for robustness.
- **[OM-XMP-012]** The XMP packet MUST be UTF-8 encoded with the leading byte-order-mark inside `xpacket begin` (`﻿`) exactly as shown; the packet MUST be well-formed XML. `omspec:*` MAY be emitted as element form (shown) or attribute form on the `rdf:Description`; Consumers MUST accept both RDF/XML abbreviations.
- **[OM-XMP-013]** Writing the `omspec` description MUST be **non-destructive** to the producer's existing metadata: a Producer MUST preserve any pre-existing `dc:`, `pdf:`, `xmp:`, `pdfaid:` and other properties, adding `omspec:*` either to the existing `rdf:Description rdf:about=""` or as an additional `rdf:Description rdf:about=""` in the same `rdf:RDF`. A Producer MUST NOT replace the entire `/Metadata` stream with an omspec-only packet (a real hazard when a library regenerates XMP on save - see OM-EMB-023).

#### §D.2.2 Detection algorithm (normative - extends OM-XMP-003)

- **[OM-XMP-005]** A Consumer MUST detect and verify a payload in this exact order, producing exactly one of the states {`absent`, `present`, `hash-mismatch`, `ambiguous`}:
  1. Obtain the PDF bytes by re-fetching the source (never by scraping the viewer, §Non-goals), under the size/decompression bounds of OM-SEC-002.
  2. Parse the document, including **cross-reference streams and compressed object streams** (OM-XMP-006). Locate `/Root`.
  3. Read `/Root /Metadata`; parse the XMP for `omspec:specName` and `omspec:payloadHash`. Presence of `omspec:payloadHash` is the fast-path signal that a payload is claimed.
  4. Resolve the payload `/Filespec`: **prefer** the catalog `/AF` array - the first entry whose `/AFRelationship` is `/Data` and whose `/F` or `/UF` decodes to `om.json`. If `/AF` is absent, **fall back** to the `/Root /Names /EmbeddedFiles` name tree (OM-XMP-009).
  5. Dereference `/EF /F` (fallback `/EF /UF`); read the stream; apply `/Filter` decompression to obtain the decompressed bytes, bounded per OM-SEC-002.
  6. Recompute the §C hash over the decompressed bytes and compare to `omspec:payloadHash`. On mismatch, emit state `hash-mismatch` and MUST NOT treat the payload as trusted (OM-SEC-005). On match, emit `present`.
  7. Schema-validate (§E), then perform origin verification (§10 layer 3). Neither step changes the integrity state from step 6.
  If no `omspec:payloadHash` and no `om.json` file is found, emit `absent`.
- **[OM-XMP-006]** A Consumer MUST parse PDFs that use compressed cross-reference streams and object streams (ISO 32000-1 §7.5.7–§7.5.8). `/EmbeddedFiles` name-tree nodes and `/Filespec` objects are frequently stored in object streams (pikepdf/qpdf default output, OM-EMB-021); a Consumer that only scans the uncompressed body will falsely report `absent`.
- **[OM-XMP-007]** If more than one distinct `om.json` `/Filespec` is reachable (malformed producer): a Consumer MUST select the one referenced by catalog `/AF`; if two `/AF` entries or an `/AF` entry and a name-tree entry point at **different** objects, the Consumer MUST prefer the one whose recomputed hash equals `omspec:payloadHash`; if still ambiguous, emit state `ambiguous` and MUST NOT silently pick one.
- **[OM-XMP-008]** If `om.json` is present but the XMP carries no `omspec:payloadHash` (degraded producer): a Consumer MAY surface the payload but MUST mark it integrity-unverified and MUST NOT report `hashValid: true`. A self-hash of the bytes is informational only - with no stored reference hash there is nothing to verify against.
- **[OM-XMP-009]** Name-tree fallback: when traversing `/Root /Names /EmbeddedFiles`, a Consumer MUST recurse through intermediate `/Kids` nodes (a name tree may be nested, not a flat `/Names` array) and MUST match the key `om.json` on its decoded value.

### §D.4 Re-embed (replace-in-place) algorithm (normative)

Re-embed is the most common Producer operation (repricing, §4) and MUST replace, never stack. It requires no signing step (§10). A conformant Producer MUST implement this ordered algorithm:

- **[OM-EMB-017]** Re-embed procedure:
  1. Open the source PDF **without normalizing or recompressing content streams** (OM-EMB-020).
  2. Compute the new payload JCS bytes and the new §C integrity hash `H_new`.
  3. Read the existing XMP `omspec:payloadHash` as `H_prior` (may be absent → treat as no predecessor).
  4. Locate the existing payload `/Filespec` (via `/AF`, then name tree; OM-XMP-005 steps 4).
  5. Remove the existing `om.json` entry from the `/EmbeddedFiles` name tree **and** remove its `/Filespec` reference from the catalog `/AF` array.
  6. Create a new `/EmbeddedFile` stream (JCS bytes, OM-CANON-005) and a new `/Filespec` per §D.1, satisfying the shared-object invariants (OM-EMB-006/007).
  7. Add exactly one entry to the name tree and one reference to `/AF`, both pointing at the new `/Filespec`.
  8. Update the XMP: set `omspec:payloadHash = H_new`, `omspec:assertedDate` to the new assertion date, and `omspec:supersedes = H_prior` (omit `omspec:supersedes` if there was no predecessor). Also set `meta.supersedes` in the payload consistently (§E) before step 2 - the payload's `supersedes` and the XMP `supersedes` MUST agree.
  9. Save (OM-EMB-020), then verify reachability (OM-EMB-008) and single-instance (OM-EMB-018).
- **[OM-EMB-018]** After re-embed the document MUST contain **exactly one** reachable `om.json` `/Filespec` and one `/EmbeddedFile` payload stream. The superseded stream and `/Filespec` MUST be made unreferenced and MUST be removed by object garbage-collection on save; a Producer MUST NOT leave a second `om.json` in `/EmbeddedFiles` (restates OM-XMP-004) and MUST NOT let a superseded payload stream remain reachable from `/Root`.
- **[OM-EMB-019]** Idempotent no-op: if `H_new == H_prior` (the payload is byte-identical after JCS), a Producer SHOULD skip the write and leave the document unchanged (no `supersedes` self-reference, no `assertedDate` churn). A re-embed MUST NOT set `omspec:supersedes` equal to `omspec:payloadHash`.
- **[OM-EMB-020]** Non-destructive save: the output PDF MUST be visually identical to the source (§Non-goals). A Producer MUST NOT recompress, normalize, or re-encode page content streams, images, or fonts, MUST preserve bookmarks/outlines, links, and annotations, and MUST NOT set a content-normalization flag (pikepdf `normalize_content=True` MUST be off; OM-EMB-024). Structural rewriting limited to the objects in §D.0 (name tree, `/AF`, `/Filespec`, payload stream, `/Metadata`) is permitted; touching any other object's byte content is not.

### §D.5 The `/CheckSum` (MD5) trap (normative)

- **[OM-EMB-030]** The PDF `/Params /CheckSum` is, by ISO 32000-1, an **MD5** digest of the uncompressed embedded-file bytes. MD5 is not collision-resistant, so a matching `/CheckSum` proves nothing an attacker cannot also produce: a forged payload can be given a valid `/CheckSum`. Therefore:
  - A Consumer MUST NOT read, compare, or surface `/CheckSum` for **any** trust, integrity, or verification decision. The one and only integrity value is the SHA-256 in XMP `omspec:payloadHash` (§C, §D.2), recomputed over the decompressed JCS bytes at read time (OM-XMP-005 step 6).
  - A Producer MAY write `/CheckSum` for legacy-reader compatibility (restates OM-EMB-005) but MUST NOT present it, in tooling output or UI, as evidence of integrity or authenticity.
  - `hashValid: true` in tool output (§I) and the `origin-verified` badge (§10) MUST derive solely from the SHA-256 check and the domain-origin check - never from `/CheckSum`.
- This is the wire-format restatement of the §10 principle and OM-SEC-005: integrity is SHA-256; `/CheckSum` is a legacy artifact of the container format, not part of the OpenOM trust model. See also the decision-log entry (2026-08-16) fixing `/Params/CheckSum` as *not* the integrity mechanism.

---

## §E. Data dictionary, units & enumerations

- **[OM-DD-001]** The normative schema is `/spec/om-0.1.schema.json` (JSON Schema 2020-12). This table is the human-readable mirror; on conflict the schema wins.
- **[OM-DD-002]** Dates MUST be ISO 8601 (`YYYY-MM-DD` for dates, RFC 3339 UTC `Z` for timestamps). Currency MUST be ISO 4217; v0.1 assumes `USD` unless a top-level `currency` field states otherwise. Country/region codes MUST be ISO 3166.
- **[OM-DD-003]** **Absent vs null:** an omitted key means "not asserted"; an explicit `null` means "asserted to be not applicable / none" (e.g. `supersedes: null` = "this is an original, deliberately"). Consumers MUST distinguish the two.

### §E.2 Field-by-field dictionary

This is the complete human-readable mirror of `/spec/om-0.1.schema.json`; on conflict the schema wins ([OM-DD-001]). "Card." is cardinality (`1` = exactly one/required, `0..1` = optional single, `0..n` = optional array). "Req?" gives the RFC 2119 obligation and any condition. The `source` column marks whether the field MAY carry a sibling per-field provenance tag ([OM-DD-004]); `n/a` means the field is structural/meta and carries no `source`. Lexical grammars for identifier-shaped fields are in §E.3; controlled vocabularies are in §E.6.

**Top-level (JSON-LD envelope & required roots)**

| Field (path) | Type | Card. | Units/Format | Req? | `source` |
|---|---|---|---|---|---|
| `@context` | array<string> | 1 | JSON-LD contexts, [OM-DD-014] | MUST | n/a |
| `@type` | string const | 1 | `"RealEstateListing"` | MUST | n/a |
| `specVersion` | string enum `"0.1"` | 1 | - | MUST | n/a |
| `currency` | string | 0..1 | ISO 4217, default USD, [OM-DD-021] | SHOULD | n/a |
| `assertedDate` | date | 1 | ISO 8601 | MUST | n/a |
| `assertedBy` | object | 1 | see below | MUST | n/a |
| `property` | object | 1 | see below | MUST | n/a |
| `deal` | object | 0..1 | see below | SHOULD | n/a |
| `lease` | object | 0..1 | see below | SHOULD | n/a |
| `meta` | object | 1 | see below | MUST | n/a |

**`assertedBy` (asserting party / parties)**

| Field (path) | Type | Card. | Units/Format | Req? | `source` |
|---|---|---|---|---|---|
| `assertedBy.broker` | string | 1 | free text, non-empty | MUST | n/a |
| `assertedBy.brokerage` | string | 1 | free text, non-empty | MUST | n/a |
| `assertedBy.license` | string | 1 | license id, [OM-DD-016] | MUST | n/a |
| `assertedBy.phone` | string | 0..1 | E.164 RECOMMENDED | MAY | n/a |
| `assertedBy.email` | string | 0..1 | RFC 5322 addr-spec | MAY | n/a |

*A payload has exactly one asserting party in 0.1 (a single named broker/brokerage/license). Co-listing / multiple asserting parties are out of scope for 0.1.*

**`property`**

| Field (path) | Type | Card. | Units/Format | Req? | `source` |
|---|---|---|---|---|---|
| `property.address` | schema.org PostalAddress | 1 | see below | MUST | applies |
| `property.address.streetAddress` | string | 1 | free text | MUST | applies |
| `property.address.addressLocality` | string | 1 | city/locality | MUST | applies |
| `property.address.addressRegion` | string | 1 | ISO 3166-2 subdivision (US: 2-letter), [OM-DD-019] | MUST | applies |
| `property.address.postalCode` | string | 1 | US ZIP / ZIP+4, [OM-DD-018] | MUST | applies |
| `property.address.addressCountry` | string | 0..1 | ISO 3166-1 alpha-2, default `US`, [OM-DD-020] | SHOULD | applies |
| `property.geo.latitude` | number | 0..1 (both) | WGS84 deg, [OM-DD-013] | SHOULD | applies |
| `property.geo.longitude` | number | 0..1 (both) | WGS84 deg, [OM-DD-013] | SHOULD | applies |
| `property.apn` | string | 0..1 | APN, [OM-DD-017] | SHOULD | applies |
| `property.buildingSF` | number (int) | 0..1 | square feet | SHOULD | applies |
| `property.lotAcres` | number | 0..1 | acres, ≤ 2 dp | MAY | applies |
| `property.yearBuilt` | number (int) | 0..1 | `CCYY` | MAY | applies |
| `property.yearRenovated` | number (int) | 0..1 | `CCYY`, ≥ `yearBuilt` | MAY | applies |

**`deal`**

| Field (path) | Type | Card. | Units/Format | Req? | `source` |
|---|---|---|---|---|---|
| `deal.askingPrice` | number | 0..1 | major currency units (int) | SHOULD | applies |
| `deal.capRate` | number | 0..1 | decimal fraction (`0.0625`) | SHOULD | applies |
| `deal.noi` | number | 0..1 | major currency units | SHOULD | applies |
| `deal.noiType` | enum `in-place`\|`pro-forma` | 1 if `noi` present | - | MUST w/ `noi` (§H `OMV-E002`) | n/a |
| `deal.noiAsOfDate` | date | 1 if `noi` present | ISO 8601 | MUST w/ `noi` (§H `OMV-E002`) | n/a |
| `deal.pricePerSF` | number | 0..1 | major units ÷ SF, ≤ 2 dp; derivable | MAY | applies |
| `deal.status` | enum | 0..1 | `active`\|`under-contract`\|`sold`\|`withdrawn` | MAY | applies |

**`lease`**

| Field (path) | Type | Card. | Units/Format | Req? | `source` |
|---|---|---|---|---|---|
| `lease.tenantEntity` | string | 0..1 | legal entity name | SHOULD | applies |
| `lease.guarantor` | object \| null | 0..1 | see §E.4; `null` = no guaranty | MAY | applies |
| `lease.guarantor.name` | string | 1 if `guarantor` is an object | non-empty | MUST w/ guarantor obj | applies |
| `lease.guarantor.type` | enum | 0..1 | `corporate`\|`personal`\|`franchisee`\|`none` | MAY | applies |
| `lease.landlordResponsibilities` | object (7 booleans) | 0..1 | fixed key set, [OM-DD-028] | SHOULD | applies |
| `lease.leaseTypeAsserted` | enum | 0..1 | `N`\|`NN`\|`NNN`\|`absolute-net`\|`gross`\|`modified-gross` | MAY | asserted |
| `lease.commencement` | date | 0..1 | ISO 8601 | SHOULD | applies |
| `lease.expiration` | date | 0..1 | ISO 8601, > `commencement` | SHOULD | applies |
| `lease.remainingTermYears` | number | 0..1 | years, as of `assertedDate` | MAY | applies |
| `lease.rentSchedule` | array<RentPeriod> | 0..n | see §E.5 | SHOULD | per-item |
| `lease.options` | array<Option> | 0..n | see §E.4 [OM-DD-025] | MAY | per-item |
| `lease.rofr` | boolean | 0..1 | right of first refusal | MAY | applies |
| `lease.rofo` | boolean | 0..1 | right of first offer | MAY | applies |

**`meta`**

| Field (path) | Type | Card. | Units/Format | Req? | `source` |
|---|---|---|---|---|---|
| `meta.sourceDocHash` | string | 0..1 | `sha256:<hex>`, [OM-DD-015], §C [OM-CANON-004] | MAY | n/a |
| `meta.supersedes` | string \| null | 1 | prior payload hash \| `null`, [OM-DD-015] | MUST | n/a |
| `meta.signature` | object \| absent | 0..1 | reserved (§10) | MUST NOT populate in 0.1 (§H `OMV-E003`) | n/a |
| `meta.imageRights` | string | 0..1 | rights statement, [OM-DD-030] | MAY | n/a |

- **[OM-DD-023] `assertedBy` completeness.** `assertedBy` MUST include `broker`, `brokerage`, and `license`; `phone`/`email` are OPTIONAL professional contact for the assertion and are the only contact data a payload SHOULD carry (§K [OM-PRIV-004]).

- **[OM-DD-004]** A `source` tag is `asserted`\|`extracted`\|`verified`; when absent, Consumers MUST assume `asserted` for an embedded (review-gated) payload. **0.1 scope (resolved 2026-08-17, #44):** a `source` tag is structurally carried **only on object-valued containers that have room for a sibling key - normatively, `rentSchedule[]` period objects** (the extraction-risk hotspot, and the only place a "sibling `source`" is unambiguous). A bare scalar (`buildingSF`, `apn`, `askingPrice`, geo, …) has no sibling to attach to, so scalar-field and `options[]` provenance is **deferred to a future minor** that defines a provenance side-map (§13 parked item); the §E `source` column value **`applies`** marks the fields that side-map will cover, and until it ships those fields carry no per-field `source` and inherit the payload-level `asserted` assumption. This keeps 0.1 internally consistent with the published schema, which implements `source` on `rentPeriod` only.
- **[OM-DD-005] RentPeriod:** `periodStart` (date, MUST), `periodEnd` (date, MUST, > start), `annualRent` (number, MUST), `monthlyRent` (number, MAY), `rentPSF` (number, MAY; = annualRent÷buildingSF), `escalationFromPrior` (decimal fraction, MAY), `abatement` (number\|null, MAY), `source` (enum, MAY). Periods MUST be chronologically ordered; gaps/overlaps raise `OMW-W021`/`OMW-W022` (§H), never a schema error.

### §E.1 General encoding, units, precision & absence semantics

These rules apply to **every** field in the dictionary unless a field's row overrides them. They make the per-field table unambiguous and keep it consistent with the canonicalization keystone (§C).

- **[OM-DD-006] Document shape.** A payload MUST be a single JSON object serialized as JSON-LD and canonicalized/hashed per §C (RFC 8785 JCS). Object keys MUST be unique (duplicate keys are rejected, §J [OM-SEC-004]). Consumers MUST accept unknown OPTIONAL members without rejecting the payload (§F [OM-VER-003]). An empty object `{}` or empty array `[]` MUST NOT be used to signify "not asserted" - the key MUST be omitted instead (see [OM-DD-003]).
- **[OM-DD-007] Currency scope & default.** All monetary amounts in a payload are expressed in one currency, given by the top-level `currency` field (ISO 4217 alphabetic code, §E.3 [OM-DD-021]). When `currency` is absent the currency is **USD**. A single payload is single-currency in 0.1; mixed-currency deals are out of scope. Monetary fields are bare numbers in **major units** (dollars, not cents) and MUST NOT carry a currency symbol, thousands separators, or a suffix.
- **[OM-DD-008] Number precision & lexical form.** Numbers MUST be finite JSON numbers; `NaN`, `Infinity`, leading `+`, and leading zeros are prohibited (JCS, §C [OM-CANON-001]). Because JCS emits the shortest round-trip form and drops trailing zeros (`12.70`→`12.7`), Producers MUST NOT rely on trailing-zero formatting for equality or display fidelity ([OM-CANON-006]). Per-field precision:

  | Field class | Precision rule |
  |---|---|
  | Whole-currency (`deal.askingPrice`, `deal.noi`, `RentPeriod.annualRent`) | SHOULD be integer major units |
  | Sub-unit currency (`RentPeriod.monthlyRent`, `RentPeriod.rentPSF`, `deal.pricePerSF`) | MAY carry up to 2 decimals |
  | Rates / fractions (`deal.capRate`, `RentPeriod.escalationFromPrior`, `options[].escalationRate`) | decimal fraction; RECOMMENDED ≤ 4 decimals |
  | Area (`property.buildingSF`) | SHOULD be integer square feet |
  | Area (`property.lotAcres`) | MAY carry up to 2 decimals |
  | Coordinates (`property.geo.*`) | RECOMMENDED ≤ 6 decimals ([OM-DD-013]) |
  | Year (`property.yearBuilt`/`yearRenovated`) | 4-digit integer (`CCYY`) |
  | Counts / durations (`options[].count`, `options[].lengthYears`, `lease.remainingTermYears`) | non-negative; counts integer, durations MAY be fractional years |

- **[OM-DD-009] Rates & percentages.** Every rate or percentage MUST be a decimal fraction, never a percent value: `capRate: 0.0625` means 6.25%; `escalationFromPrior: 0.10` means 10% ([OM-CANON-007]). Producers MUST NOT encode `6.25` or `10`.
- **[OM-DD-010] Strings.** A string field, when present, MUST be non-empty, MUST be trimmed of leading/trailing whitespace, and MUST NOT contain unescaped control characters. Sentinel placeholders (`""`, `"N/A"`, `"TBD"`, `"-"`) MUST NOT be used as data - omit the key ([OM-DD-003]) or use `null` where a null is defined.
- **[OM-DD-011] Enumerations.** Enum values are matched **case-sensitively** against the registry in §E.6 ([OM-DD-040]); literals are lowercase and hyphenated except where the registry states otherwise (e.g. `N`/`NN`/`NNN`). A Consumer encountering an unknown enum member MUST treat the field as present-but-uninterpreted and MUST NOT reject the payload for it (§F [OM-VER-003]).
- **[OM-DD-012] Dates & term arithmetic.** All date-typed fields (`assertedDate`, `deal.noiAsOfDate`, `lease.commencement`, `lease.expiration`, `RentPeriod.periodStart`/`periodEnd`) MUST be ISO 8601 `YYYY-MM-DD` calendar dates with no time or zone component and MUST be valid on the proleptic Gregorian calendar. Timestamps (e.g. the webhook `publishedAt`, §5b) MUST be RFC 3339 UTC with a `Z` designator ([OM-DD-002]). A lease/rent interval `[start, end]` is **inclusive of both endpoints**; two intervals are **contiguous** iff the later interval's `periodStart` equals the earlier interval's `periodEnd` plus one calendar day. Unless a check names another reference, the "as-of" instant for term arithmetic (e.g. remaining term) is `assertedDate` (consistent with §H `OMW-W030`).
- **[OM-DD-013] Geospatial values.** `property.geo.latitude` and `property.geo.longitude` are WGS84 decimal degrees with `latitude ∈ [-90, 90]` and `longitude ∈ [-180, 180]`, RECOMMENDED to ≤ 6 decimal places. `latitude` and `longitude` MUST both be present or both absent.
- **[OM-DD-014] JSON-LD envelope.** `@context` MUST be a JSON array whose members include exactly `"https://schema.org"` and the versioned OpenOM namespace URL for this `specVersion` (`https://openom.app/ns/0.1` in 0.1; §D.2 [OM-XMP-001], §15 Q1). `@type` MUST be the string `"RealEstateListing"`. The namespace URL pinned in `@context` MUST correspond to `specVersion`; published context URLs are immutable (§F [OM-VER-002]).

### §E.3 Identifier-shaped field grammars

Identifier-shaped fields carry a machine-checkable lexical form so Producers and Validators agree byte-for-byte. Each grammar is given as ABNF (RFC 5234, with RFC 7405 case-sensitive `%s` string literals) and an equivalent PCRE-style regex anchored `^…$`. The JSON Schema (`format`/`pattern`) is authoritative on conflict ([OM-DD-001]). A field that is present but fails its grammar is a schema violation (§H `OMV-E001`).

- **[OM-DD-015] Payload-hash strings** (`meta.sourceDocHash`, `meta.supersedes` when non-null, and the XMP `omspec:payloadHash`, `omspec:supersedes`): the literal `sha256:` followed by exactly 64 **lowercase** hex characters (§C mandates lowercase; uppercase MUST be rejected).
  ```abnf
  lc-hexdig    = DIGIT / %x61-66            ; 0-9 / a-f
  sha256-hash  = %s"sha256:" 64lc-hexdig
  ```
  Regex: `^sha256:[0-9a-f]{64}$`

- **[OM-DD-016] `assertedBy.license`** (real-estate license number). License numbering is jurisdiction-specific and has no single national format; the grammar is therefore permissive but structured, and MUST NOT be empty or whitespace-only. **RECOMMENDED normalized form:** the ISO 3166-2 subdivision suffix (state), a single space, then the jurisdiction's local identifier - e.g. `MI 6501-000000`.
  ```abnf
  license-norm = region SP local-id
  region       = 2ALPHA                     ; ISO 3166-2:US subdivision suffix
  local-id     = 1*63( ALPHA / DIGIT / "-" / "." / "/" )
  ```
  Permissive regex (what the schema enforces): `^[A-Za-z0-9][A-Za-z0-9 .\-\/]{0,63}$`
  *No layer of OpenOM verifies a license against an authoritative registry; the value is a self-asserted identity claim (§10 layer 2), labeled unverified.*

- **[OM-DD-017] `property.apn`** (Assessor's Parcel Number). Formats vary by county (digits, hyphens, dots, occasional letters); Producers SHOULD store the APN exactly as printed on the assessor record. Same permissive shape as a license id:
  Regex: `^[A-Za-z0-9][A-Za-z0-9 .\-\/]{0,63}$`

- **[OM-DD-018] `property.address.postalCode`** (US default). US ZIP or ZIP+4:
  ```abnf
  us-zip = 5DIGIT [ "-" 4DIGIT ]
  ```
  Regex (US): `^\d{5}(-\d{4})?$`. When `addressCountry` is not `US`, `postalCode` MUST be a non-empty string valid for that country (not further constrained in 0.1).

- **[OM-DD-019] `property.address.addressRegion`.** For US addresses this MUST be the 2-letter ISO 3166-2:US / USPS subdivision code (uppercase, e.g. `MI`). Regex (US): `^[A-Z]{2}$`. For non-US addresses it MUST be the ISO 3166-2 subdivision *suffix* (the part after the country hyphen) or, where none applies, the locality-appropriate region name.

- **[OM-DD-020] `property.address.addressCountry`.** ISO 3166-1 **alpha-2**, uppercase; default `US` when absent. Regex: `^[A-Z]{2}$`.

- **[OM-DD-021] `currency`.** ISO 4217 **alphabetic** code, uppercase. Regex: `^[A-Z]{3}$`. Default `USD` ([OM-DD-007]).

- **[OM-DD-022] Date & timestamp lexical forms.** Dates: `^\d{4}-\d{2}-\d{2}$` and MUST be a valid calendar date. Timestamps (envelope only): RFC 3339 UTC, `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$`.

### §E.4 Object & sub-object models

- **[OM-DD-024] `lease.guarantor`.** Either an object or `null`. `null` asserts *no guaranty* (deliberate, per [OM-DD-003]); omitting the key means *not asserted*. When an object, `name` is REQUIRED; `type` is OPTIONAL and drawn from the guarantor enum ([OM-DD-040]). A `type` of `none` alongside a `name` is contradictory and Validators SHOULD flag it as a consistency warning (§H); prefer `guarantor: null` to assert no guaranty.
- **[OM-DD-025] `lease.options[]` (Option object).** Renewal/extension options. Each element:

  | Field | Type | Card. | Units/Format | Req? |
  |---|---|---|---|---|
  | `count` | number (int ≥ 1) | 1 | number of option periods | MUST |
  | `lengthYears` | number (> 0) | 1 | years per option period | MUST |
  | `escalation` | string | 0..1 | free-text descriptor (e.g. `"10% per option"`) | MAY |
  | `escalationRate` | number | 0..1 | decimal fraction per option ([OM-DD-009]) | MAY |
  | `noticeMonths` | number | 0..1 | months' notice to exercise | MAY |

  An Option element's `source` tag is **deferred to the provenance side-map minor** (#44, [OM-DD-004]); 0.1 does not carry `source` on `options[]`. When both `escalation` (prose) and `escalationRate` (machine) are present they SHOULD agree; disagreement is advisory only.
- **[OM-DD-026] `lease.rofr` / `lease.rofo`.** Booleans: `rofr` = a right of first refusal exists; `rofo` = a right of first offer exists. Absent = not asserted; there is no third value.
- **[OM-DD-027] `lease.remainingTermYears`.** The OM-asserted remaining primary-lease term (excluding options) measured in years as of `assertedDate`. It is derivable from `expiration − assertedDate`; when both are present and disagree beyond tolerance, §H `OMW-W030` fires. Remaining term MUST exclude unexercised options.
- **[OM-DD-028] `lease.landlordResponsibilities`.** A fixed-key object of exactly seven booleans: `roof`, `structure`, `parking`, `hvac`, `taxes`, `insurance`, `cam`. `true` means the **landlord** bears that cost/obligation; `false` means the **tenant** does. Additional keys MUST NOT be added in 0.1. This object, not `leaseTypeAsserted`, is the disputable ground truth for net-lease grade.
- **[OM-DD-029] `lease.leaseTypeAsserted` vs the derived grade.** `leaseTypeAsserted` is the broker's stated label (source tag fixed to `asserted`); it is advisory. The *derivable* net-lease grade is computed by Consumers from `landlordResponsibilities` and is **not** a stored field in 0.1. When `leaseTypeAsserted` = `NNN` but any of `taxes`/`insurance`/`cam` (or maintenance-bearing `roof`/`structure`/`parking`/`hvac`) is `true` for the landlord, §H `OMW-W040` fires - this is the mechanism that kills "everything is NNN" (§7a).
- **[OM-DD-030] `meta.imageRights`.** OPTIONAL free-text statement of third-party image licensing/redistribution constraints on the OM's photos (§8b), e.g. `"Third-party photography licensed to lister; do not redistribute."` It is descriptive only; tooling MUST NOT act on it.
- **[OM-DD-031] No separate `escalations` field.** Rent escalations are modeled structurally: within the primary term via `rentSchedule[].escalationFromPrior` (§E.5), and for renewal options via `options[].escalation`/`escalationRate`. 0.1 defines no free-standing `lease.escalations` field; Producers MUST NOT introduce one (it would duplicate, and risk contradicting, the schedule).

### §E.5 `rentSchedule` / RentPeriod (fully modeled)

`lease.rentSchedule` is an ordered array of RentPeriod objects - the differentiator (§6d), so it is specified exhaustively here. [OM-DD-005] gives the summary; this section is its normative expansion and governs on any apparent difference within §E.

**RentPeriod fields**

| Field | Type | Card. | Units/Format | Req? | `source` |
|---|---|---|---|---|---|
| `periodStart` | date | 1 | ISO 8601 | MUST | - |
| `periodEnd` | date | 1 | ISO 8601, > `periodStart` | MUST | - |
| `annualRent` | number | 1 | major currency units (face/contract rent) | MUST | - |
| `monthlyRent` | number | 0..1 | major units, ≤ 2 dp; ≈ `annualRent ÷ 12` | MAY | - |
| `rentPSF` | number | 0..1 | major units per SF/yr, ≤ 2 dp; ≈ `annualRent ÷ buildingSF` | MAY | - |
| `escalationFromPrior` | number | 0..1 | decimal fraction vs prior period's `annualRent` | MAY | - |
| `abatement` | number \| null | 0..1 | months of free rent within this period; `null` = none | MAY | - |
| `source` | enum | 0..1 | `asserted`\|`extracted`\|`verified` ([OM-DD-004]) | MAY | - |

**Structural & consistency invariants** (structural = schema error `OMV-E001`; consistency = warning, never blocks, §9/§H):

- **[OM-DD-032] Well-formed period (structural).** Each RentPeriod MUST have `periodStart` and `periodEnd` with `periodEnd > periodStart`, and a numeric `annualRent ≥ 0`. Violations are `OMV-E001`.
- **[OM-DD-033] Ordering & contiguity (consistency).** Array order MUST reflect chronology ([OM-CANON-002]): for every adjacent pair, `periodStart[i] > periodStart[i-1]`. A **gap** (period *i* `periodStart` later than `periodEnd[i-1]` + 1 day, per [OM-DD-012]) raises `OMW-W021`; an **overlap** (`periodStart[i] ≤ periodEnd[i-1]`) raises `OMW-W022`. A contiguous schedule has `periodStart[i] = periodEnd[i-1] + 1 day` for all *i*.
- **[OM-DD-034] `rentPSF` derivation (consistency).** When `rentPSF` and `property.buildingSF` are both present, `rentPSF` SHOULD equal `annualRent ÷ buildingSF`; a mismatch beyond the configured tolerance (§H default 0.5% relative) raises `OMW-W024`.
- **[OM-DD-035] `escalationFromPrior` semantics (consistency).** For period *i* > 0, `escalationFromPrior` = `(annualRent[i] − annualRent[i-1]) ÷ annualRent[i-1]`, a decimal fraction ([OM-DD-009]). On the **first** period there is no prior, so `escalationFromPrior` SHOULD be absent (or `null`); a non-null value on the first period, or a value inconsistent with adjacent `annualRent` beyond tolerance, raises `OMW-W023`.
- **[OM-DD-036] `monthlyRent` derivation (consistency).** When present, `monthlyRent` SHOULD equal `annualRent ÷ 12` within tolerance; a mismatch SHOULD raise a consistency warning (§H - code allocation belongs to §H). `monthlyRent` never overrides `annualRent`.
- **[OM-DD-037] `abatement` semantics (structural + consistency).** `abatement` is the number of months of free/abated rent *within* the period; `0 ≤ abatement ≤` the period's whole-month span (structural bound; out-of-range is `OMV-E001`). `abatement` MUST NOT modify `annualRent` (which is always face/contract rent); it is disclosed separately so Consumers can compute effective rent. `null` asserts explicitly no abatement; absent means not asserted.
- **[OM-DD-038] Year-one vs NOI (consistency).** When `deal.noi`, `deal.noiType = in-place`, and a rentSchedule are all present, the `annualRent` of the period covering `deal.noiAsOfDate` SHOULD equal `deal.noi` within tolerance; a mismatch raises `OMW-W020`. (Pro-forma NOI is exempt - it need not match current contract rent.)
- **[OM-DD-039] Schedule coverage vs lease term (consistency).** When `lease.commencement`/`lease.expiration` are present, the schedule SHOULD begin no earlier than `commencement` and its final `periodEnd` SHOULD equal `expiration`; deviations are surfaced via the gap/overlap and term-arithmetic warnings (`OMW-W021`/`OMW-W022`/`OMW-W031`). The schedule covers the **primary** term only; option-period rent is expressed via `options[]` ([OM-DD-025]), not appended to `rentSchedule`.

**Worked example** (the §7e sample, `buildingSF = 9100`, `noiAsOfDate = 2026-06-30`, `noi = 115625`, `noiType = in-place`):

| # | periodStart | periodEnd | annualRent | rentPSF (check) | escalationFromPrior (check) | contiguity |
|---|---|---|---|---|---|---|
| 1 | 2024-05-01 | 2029-04-30 | 115625 | 115625 ÷ 9100 = 12.706 ≈ 12.70 ✓ (`W024` clear) | - (first period) | - |
| 2 | 2029-05-01 | 2034-04-30 | 127188 | 127188 ÷ 9100 = 13.977 ≈ 13.98 ✓ | (127188−115625)÷115625 = 0.1000 ✓ (`W023` clear) | 2029-04-30 + 1d = 2029-05-01 ✓ (`W021`/`W022` clear) |

Period 1 covers `noiAsOfDate` and `annualRent[1] = 115625 = deal.noi` → `OMW-W020` clear. `monthlyRent` for period 1, if asserted, is `115625 ÷ 12 = 9635.42` ✓. All consistency checks pass; the schedule is contiguous, chronologically ordered, and internally consistent.

### §E.6 Enumeration registry

- **[OM-DD-040]** Every enumerated field draws its value from exactly this registry; literals are matched case-sensitively ([OM-DD-011]). Values are stable and append-only across minor versions.

| Field | Allowed values | Notes |
|---|---|---|
| `specVersion` | `0.1` | single value in this release |
| `@type` | `RealEstateListing` | schema.org type |
| `deal.noiType` | `in-place`, `pro-forma` | REQUIRED when `noi` present ([OM-DD-002] framing, §H `OMV-E002`) |
| `deal.status` | `active`, `under-contract`, `sold`, `withdrawn` | - |
| `lease.leaseTypeAsserted` | `N`, `NN`, `NNN`, `absolute-net`, `gross`, `modified-gross` | advisory label; grade derived from `landlordResponsibilities` ([OM-DD-029]) |
| `lease.guarantor.type` | `corporate`, `personal`, `franchisee`, `none` | prefer `guarantor: null` over `type: none` ([OM-DD-024]) |
| `source` (any field's provenance tag) | `asserted`, `extracted`, `verified` | default `asserted` for embedded payloads ([OM-DD-004]) |
| `currency` | any ISO 4217 alpha code | not a fixed list; format `^[A-Z]{3}$` ([OM-DD-021]); default `USD` |
| `addressCountry` | any ISO 3166-1 alpha-2 | format `^[A-Z]{2}$` ([OM-DD-020]); default `US` |

- **[OM-DD-041] Enum evolution.** New enum members are added only by a spec version bump; adding an OPTIONAL member is a **minor** change (§F [OM-VER-001]). Consumers MUST tolerate an unrecognized member per [OM-DD-011]/[OM-VER-003] rather than reject the payload. `currency`/`addressCountry` are open ISO-code sets, not closed lists, and are validated by format, not membership.

---

## §H. Error & warning taxonomy (stable codes)

- **[OM-ERR-001]** `om_validate` and the standalone checker MUST emit results as `{code, severity, path, message, expected?, actual?}`. Codes are stable and append-only. **Errors (`OMV-E###`) block `om_embed`; warnings (`OMW-W###`) never block.**

### §H.0 Severity model & block boundary

- **[OM-ERR-003]** There are exactly three severities: **`error`** (`OMV-E###`), **`warning`** (`OMW-W###`), and **`info`** (`OMI-I###`). Every emitted Finding MUST carry exactly one, and its severity MUST match its code's prefix. Severities and prefixes are closed for v0.1 (adding a fourth severity is a MAJOR change, §F).

- **[OM-ERR-004]** **The block boundary is binary and is a pure function of severity.** `om_embed` (and any Producer commit step) MUST refuse when the Finding set contains **≥ 1 `error`**, and MUST proceed when it contains **zero errors**, regardless of how many `warning` or `info` Findings are present. `warning` and `info` MUST NEVER block, MUST NEVER alter the payload, and are advisory only. No configuration, flag, or future code may make a `warning`/`info` block, nor make an `error` non-blocking.

- **[OM-ERR-005]** **Info severity.** `info` Findings are non-blocking observations that are neither schema violations nor data-quality contradictions - e.g. a defaulted field, an assumed `source` tag, a skipped cross-check because inputs were absent, or a deprecated-field notice (OM-VER-014). A Validator MAY suppress `info` by default and expose it under a verbose mode; it MUST NOT suppress `error` or `warning`.

- **[OM-ERR-006]** **Market truth stays out.** No code in any severity may encode a judgement about whether an assertion is *true in the market* (§10 Non-goals). Every `warning` is an **internal-consistency** or **plausibility** check computable from the payload alone (optionally plus the source document's own stated figures). This boundary is permanent and MUST NOT be crossed by any future code.

### §H.1 Finding & report object (exact)

- **[OM-ERR-007]** **Finding shape.** Every Finding is a JSON object with these members (extending the OM-ERR-001 sketch; older consumers MUST tolerate the added OPTIONAL members per OM-VER-003):

```jsonc
{
  "code":        "OMW-W010",        // REQUIRED, stable (§H tables)
  "severity":    "warning",          // REQUIRED, error|warning|info, matches prefix
  "path":        "/deal/capRate",   // REQUIRED, RFC 6901 JSON Pointer into the payload ("" = whole doc)
  "message":     "cap rate ...",    // REQUIRED, human-readable, NON-normative wording
  "requirement": "OM-DD-005",        // OPTIONAL, the [OM-*] id this enforces (traceability, §B)
  "expected":    0.0625,             // OPTIONAL, machine value for numeric checks
  "actual":      0.0710,             // OPTIONAL, machine value
  "tolerance":   0.005,              // OPTIONAL, the tolerance applied (§H.4)
  "unit":        "ratio"             // OPTIONAL, unit of expected/actual (ratio|usd|usd_per_sf|days|months|count)
}
```

- **[OM-ERR-008]** **`path` is RFC 6901.** `path` MUST be a JSON Pointer into the *payload* (not the PDF), with `""` denoting the whole document and array indices as their decimal position (e.g. `/lease/rentSchedule/1/annualRent`). Consumers MUST NOT parse `message` to locate a field - `path`, `code`, `expected`, and `actual` are the machine surface; `message` is display-only and its exact wording is non-normative and MAY change in a PATCH.

- **[OM-ERR-009]** **Deterministic ordering.** A Validator MUST emit Findings in a stable total order: primary key severity (`error` < `warning` < `info`), secondary key `code` ascending lexicographically, tertiary key `path` ascending as a byte string. Two conformant Validators MUST produce identical Finding sequences for the same payload - this is what makes the §B `expected/*.json` reports comparable.

- **[OM-ERR-010]** **Report envelope.** `om_validate` returns:

```jsonc
{
  "specVersion":      "0.1",
  "validatorVersion": "1.2.0",
  "errors":   [Finding, ...],
  "warnings": [Finding, ...],
  "info":     [Finding, ...],   // MAY be omitted when empty / suppressed
  "summary":  { "errorCount": 0, "warningCount": 2, "infoCount": 1 },
  "blocked":  false             // MUST equal (errorCount > 0)  - OM-ERR-004
}
```
`blocked` MUST equal `errorCount > 0`; a Producer MUST key its refuse/proceed decision on `blocked` alone.

### §H.2 Code stability & reserved ranges

- **[OM-ERR-011]** **Codes are permanent identifiers.** A code, once published, MUST NOT change meaning and MUST NOT be reused for a different check. Retiring a check follows the deprecation lifecycle (OM-VER-013): the row is retained and marked *Deprecated (withdrawn in vX.Y)*, never deleted. Receivers MUST tolerate an unknown code (forward compatibility) by treating it per its severity prefix and MUST NOT crash on it.

- **[OM-ERR-012]** **Reserved range map.** New codes MUST be allocated within the reserved band for their category; when a band fills, a new band is opened by CHANGELOG entry (§L). Bands:

| Prefix / band | Category | Status |
|---|---|---|
| `OMV-E001–E099` | Blocking: schema, structural, canonicalization, version-context | in use |
| `OMV-E100–E999` | Blocking, future categories | reserved |
| `OMW-W001–W009` | Version / compatibility (advisory) | in use |
| `OMW-W010–W019` | Deal-level math & plausibility | in use |
| `OMW-W020–W029` | Rent-schedule consistency | in use |
| `OMW-W030–W039` | Lease / date arithmetic | in use |
| `OMW-W040–W049` | Lease-type ↔ responsibilities | in use |
| `OMW-W050–W059` | Meta / supersede | in use |
| `OMW-W060–W069` | Provenance / `source`-tag consistency | in use |
| `OMW-W070–W999` | Future warning categories | reserved |
| `OMI-I001–I099` | Info / advisory notices | in use |
| `OMI-I100–I999` | Future info | reserved |
| `OM-IO-*` | Transport / I/O / parse failures (§I, §J) | in use (named, §H.5) |

Requirement-ID ranges are likewise reserved append-only: `OM-VER-001–050`, `OM-LIC-001–050`, `OM-ERR-001–050` for the framework of §F/§G/§H respectively; exceeding a band opens a new one by CHANGELOG entry.

| Code | Sev | Meaning |
|---|---|---|
| `OMV-E001` | error | JSON Schema violation (type/required/enum/format) |
| `OMV-E002` | error | `noiType`/`noiAsOfDate` missing while `noi` present |
| `OMV-E003` | error | `meta.signature` populated in a 0.1 payload (reserved) |
| `OMV-E004` | error | `specVersion` unsupported by this Validator's major |
| `OMW-W001` | warn | Unknown major spec version (Consumer) |
| `OMW-W010` | warn | cap rate ≠ NOI ÷ askingPrice beyond tolerance (default 0.5% abs) |
| `OMW-W011` | warn | price/SF ≠ askingPrice ÷ buildingSF beyond tolerance |
| `OMW-W012` | warn | NOI is `pro-forma` but presented without `noiAsOfDate` context |
| `OMW-W020` | warn | rentSchedule year-1 annualRent ≠ stated NOI (± tolerance) |
| `OMW-W021` | warn | rentSchedule gap between consecutive periods |
| `OMW-W022` | warn | rentSchedule overlapping periods |
| `OMW-W023` | warn | `escalationFromPrior` inconsistent with adjacent `annualRent` |
| `OMW-W024` | warn | `rentPSF` ≠ annualRent ÷ buildingSF beyond tolerance |
| `OMW-W030` | warn | remaining term (expiration − today) contradicts stated remaining term |
| `OMW-W031` | warn | commencement/expiration vs lease term arithmetic mismatch |
| `OMW-W040` | warn | `leaseTypeAsserted` = NNN but a `landlordResponsibilities` flag is true |

#### §H.3 Extended codes (append-only; the table above remains authoritative for existing rows)

- **[OM-ERR-013]** The following codes extend the §H taxonomy. They are stable and append-only; none renumber or redefine an existing code.

**Additional blocking errors (`OMV-E###`)**

| Code | Sev | Meaning |
|---|---|---|
| `OMV-E005` | error | Duplicate object key in payload (JCS requires unique keys - §C, OM-SEC-004) |
| `OMV-E006` | error | Max nesting depth exceeded (OM-SEC-004) |
| `OMV-E007` | error | Payload not valid UTF-8, or a BOM is present (violates OM-CANON-001) |
| `OMV-E008` | error | Payload exceeds the documented size cap before parse (OM-SEC-002; transport-side surfaces as `OM-IO-BOMB`) |
| `OMV-E009` | error | `specVersion` disagrees with the `@context` version segment (OM-VER-020) |
| `OMV-E010` | error | `meta.supersedes` present and malformed (not a `sha256:<64-hex>` string or `null`) |

**Additional warnings (`OMW-W###`)**

| Code | Sev | Meaning |
|---|---|---|
| `OMW-W002` | warn | Newer MINOR within a known MAJOR (Consumer; OM-VER-016) |
| `OMW-W003` | warn | Unknown member of an extensible enum (OM-VER-009) |
| `OMW-W013` | warn | `capRate` outside the plausibility band (default 0.02–0.20) |
| `OMW-W014` | warn | `askingPrice`, `noi`, or `buildingSF` is non-positive |
| `OMW-W025` | warn | `monthlyRent` ≠ `annualRent` ÷ 12 beyond tolerance |
| `OMW-W026` | warn | `rentSchedule` does not span the lease (starts after `commencement` or ends before `expiration`) |
| `OMW-W032` | warn | `assertedDate` is in the future relative to processing date |
| `OMW-W033` | warn | `noiAsOfDate` is after `assertedDate` |
| `OMW-W034` | warn | `expiration` ≤ `commencement` (lease-level date sanity) |
| `OMW-W041` | warn | `leaseTypeAsserted` contradicts the `landlordResponsibilities` set generally (e.g. `gross` but all flags false, or `absolute-net` but a flag true) |
| `OMW-W050` | warn | `meta.supersedes` equals the current payload's own hash (self-supersede) |
| `OMW-W051` | warn | Embedded `omspec:payloadHash` differs from the origin mirror's current payload hash (superseded/stale served file; §AA OM-TRUST-009) |
| `OMW-W060` | warn | A field's `source` is `verified` but no corroborating verification metadata is present |

**Info notices (`OMI-I###`)**

| Code | Sev | Meaning |
|---|---|---|
| `OMI-I001` | info | A field was defaulted (e.g. `currency` assumed `USD` - OM-DD-002) |
| `OMI-I002` | info | A `source` tag was absent and assumed `asserted` (OM-DD-004) |
| `OMI-I003` | info | A cross-check was skipped because required inputs were absent (e.g. no `buildingSF` for W024) |
| `OMI-I010` | info | Payload uses a field deprecated as of this Validator's version (OM-VER-014) |

#### §H.4 Default tolerances

- **[OM-ERR-014]** Each tolerance-bearing check uses the default below unless overridden via the named config key. Defaults are normative for conformance-vector reproduction (§B); an implementation MUST use these defaults when no override is supplied, and a Finding's `tolerance` member (OM-ERR-007) MUST report the value actually applied. Overriding a tolerance is a MINOR change if it ships as a new default (OM-VER-007); per-invocation overrides are not version-bearing.

| Code | Quantity checked | Default | Unit | Config key |
|---|---|---|---|---|
| `OMW-W010` | `capRate` vs `noi ÷ askingPrice` | 0.005 (absolute, = 50 bps) | ratio | `tol.capRateAbs` |
| `OMW-W011` | price/SF vs `askingPrice ÷ buildingSF` | 0.01 (relative) | ratio | `tol.pricePerSfRel` |
| `OMW-W013` | `capRate` plausibility band | [0.02, 0.20] | ratio | `tol.capRateBand` |
| `OMW-W020` | year-1 `annualRent` vs stated `noi` | 0.01 (relative) | ratio | `tol.noiVsRentRel` |
| `OMW-W023` | `escalationFromPrior` vs adjacent `annualRent` | 0.005 (relative) | ratio | `tol.escalationRel` |
| `OMW-W024` | `rentPSF` vs `annualRent ÷ buildingSF` | 0.01 (relative) | ratio | `tol.rentPsfRel` |
| `OMW-W025` | `monthlyRent` vs `annualRent ÷ 12` | 1.00 (absolute) | usd | `tol.monthlyRentAbs` |
| `OMW-W030` | remaining term vs (`expiration` − today) | 31 | days | `tol.remainingTermDays` |
| `OMW-W031` | stated lease term vs (`expiration` − `commencement`) | 31 | days | `tol.leaseTermDays` |

Relative tolerance means `|actual − expected| ÷ |expected| ≤ tol`; absolute means `|actual − expected| ≤ tol`. Date comparisons treat both endpoints as whole calendar days. Checks whose inputs are absent are not run and MAY emit `OMI-I003` (§H.3), never a warning.

- **[OM-ERR-002]** Numeric-consistency tolerances MUST be documented and configurable; defaults above. Warnings are advisory and MUST NOT alter the payload.

---

## §I. MCP tool contracts (I/O)

- **[OM-MCP-001]** Every tool accepts a path (stdio) or HTTPS URL or blob-id (remote) for its PDF input, and returns compact output: text paginated, images as a manifest + links, never raw bytes in context.
- **[OM-MCP-002]** Errors return `{ "error": { "code": "<OMV-E###|OM-IO-###>", "message": str, "retryable": bool } }`.

### §I.1 Common tool conventions (all tools)

- **[OM-MCP-003] PDF input polymorphism.** Every tool's `pdf` parameter is a `PdfRef`: **exactly one** of `path` (stdio only; local filesystem), `url` (HTTPS only), or `blobId` (a handle returned by a prior presigned upload; remote only). Rules:
  - A `path` MUST be rejected by the hosted (Streamable HTTP) transport - remote servers have no access to client filesystems (§6d) - returning `OM-IO-008`.
  - A `url` MUST be `https:` (never `http:`, `file:`, `ftp:`, `data:`, `gopher:`, `blob:`) or the tool returns `OM-IO-008`; it is subject to the full SSRF ruleset (§J OM-SEC-001, OM-SEC-011, OM-SEC-014).
  - A `blobId` MUST resolve to a live, authorized blob for the calling principal (§J OM-SEC-013) or return `OM-IO-006` / `OM-IO-007`.
  - Canonical schema:
    ```jsonc
    // PdfRef
    { "type": "object",
      "oneOf": [ {"required":["path"]}, {"required":["url"]}, {"required":["blobId"]} ],
      "properties": {
        "path":   {"type":"string"},
        "url":    {"type":"string","format":"uri","pattern":"^https://"},
        "blobId": {"type":"string","pattern":"^blob_[A-Za-z0-9]{16,}$"} },
      "additionalProperties": false }
    ```
- **[OM-MCP-004] Error envelope (canonical) + stable I/O codes.** On failure a tool MUST return the OM-MCP-002 envelope, extended with an OPTIONAL `details` object. A tool MUST NOT return partial success as an error, nor an error condition as success:
  ```jsonc
  { "error": { "code": "OM-IO-002", "message": "URL resolves to a private address",
               "retryable": false, "details": { "resolvedIp": "10.0.0.5" } } }
  ```
  `code` MUST be drawn from the table below or from the §H validation codes. `retryable` MUST be `true` only for transient conditions and `false` for deterministic rejections. I/O codes are stable and append-only:

  | Code | Retryable | Meaning |
  |---|---|---|
  | `OM-IO-001` | true | Upstream fetch failed (DNS / connect / TLS / 5xx) |
  | `OM-IO-002` | false | URL resolved to a blocked address range (§J OM-SEC-001) |
  | `OM-IO-003` | true | Connect / read timeout exceeded |
  | `OM-IO-004` | false | Response exceeded the max byte cap before completion |
  | `OM-IO-005` | false | Fetched bytes are not a PDF (`%PDF-` magic / content-type check failed, §J OM-SEC-014) |
  | `OM-IO-006` | false | `blobId` not found or expired |
  | `OM-IO-007` | false | `blobId` not authorized for this principal (§J OM-SEC-013) |
  | `OM-IO-008` | false | Unsupported input scheme/transport (`path` on remote; non-HTTPS URL) |
  | `OM-IO-009` | false | Redirect limit exceeded or cross-range redirect (§J OM-SEC-011) |
  | `OM-IO-010` | false | Malformed / unparseable PDF (§J OM-SEC-010) |
  | `OM-IO-BOMB` | false | Decompressed size or compression-ratio cap exceeded (§J OM-SEC-002) |
  | `OM-IO-012` | false | Invalid `pageRange` |
  | `OM-IO-013` | false | Invalid or expired pagination `cursor` |
  | `OM-IO-014` | true | Rate-limited by the hosted server; honor `Retry-After` (§J OM-SEC-012) |
  | `OM-IO-TRAVERSAL` | false | Embedded `/F`/`/UF` filename is not exactly `om.json`, or a path-traversal attempt on read (§J OM-SEC-007) |
  | `OM-IO-ENCRYPTED` | false | A non-empty user password is required to open the PDF (§W OM-PDF-001) |
  | `OM-IO-SIGNED` | false | A certification (DocMDP) signature disallows added content; embedding refused (§W OM-PDF-002) |
  | `OM-IO-DUPKEY` | false | Duplicate object member name on the parse path (§C OM-CANON-009; validator-tier counterpart is `OMV-E005`) |
  | `OM-IO-BADUTF8` | false | Payload not well-formed UTF-8, has a BOM, or contains an unpaired surrogate (§C OM-CANON-010; validator-tier counterpart is `OMV-E007`) |
  | `OM-IO-NUMRANGE` | false | Number not exactly representable in binary64, or non-finite (§C OM-CANON-013/014) |

  These `OM-IO-*` codes are **transport/parse-layer** rejections raised before or during parsing; their `OMV-E###` counterparts (`OMV-E005`, `OMV-E007`, `OMV-E008`) are the **validator-tier** equivalents raised when the same fault is caught inside `om_validate` (§H). A given fault surfaces as exactly one of the two, depending on which layer catches it first.

- **[OM-MCP-005] Pagination.** Text output is paginated by an **opaque** `cursor`. A tool that truncates MUST set `truncated: true` and return `nextCursor` (a base64url-encoded, server-owned token); the caller passes it back verbatim to continue. Cursors MUST be opaque (callers MUST NOT parse or construct them), stable for a bounded TTL (RECOMMENDED ≥ 5 min), and scoped to the same `pdf` input; a cursor presented for a different input MUST return `OM-IO-013`. A tool MUST NOT stream unbounded text into context (§6c, OM-MCP-001).
- **[OM-MCP-006] Image manifest & links.** `om_extract_images` MUST NOT return image bytes inline. Each manifest entry is a descriptor plus a retrieval handle: on remote transport a short-TTL HTTPS download URL (RECOMMENDED ≤ 15 min, single-object scope); on stdio a local `path`. Handles are for out-of-band retrieval and MUST NOT be inlined as `data:` URIs. Deduplication is by PDF `xref`; the count of collapsed duplicates is reported in `deduped`.
- **[OM-MCP-007] Determinism.** `/core`, `/mcp`, and the tools they expose MUST be free of inference and free of network side effects beyond the explicit fetch a tool performs (§6a; §M OM-TEL-001). Given identical input bytes and options, `om_inspect`, `om_read`, `om_validate`, and the JCS/hash portion of `om_embed` MUST produce identical results across runs and across implementations (the interop guarantee of §C). Non-deterministic PDF metadata (e.g. `/ModDate`) MUST NOT affect any hash or verdict (§D OM-EMB-011).
- **[OM-MCP-008] Limits & timeouts.** Each tool MUST enforce, and the hosted server MUST document, per-call limits: max fetched PDF size (RECOMMENDED 200 MB), max PDF-stream decompression budget (RECOMMENDED 500 MB + ratio cap, §J OM-SEC-002), max decompressed payload 5 MB (§J OM-SEC-002), connect+read timeouts (RECOMMENDED 10 s connect / 30 s read), and max pages processed per call. Exceeding a limit returns the mapped `OM-IO-###` - never a crash, a hang, or a truncated-but-successful result.
- **[OM-MCP-009] Read-only vs mutating.** `om_inspect`, `om_read`, `om_extract_text`, `om_extract_images`, and `om_validate` are read-only and MUST NOT modify the input. `om_embed` is the only mutating tool; it MUST write a new document, MUST NOT modify the input in place, and MUST honor §D idempotency (replace, never stack).

### §I.2 Per-tool I/O contracts

Each contract gives the input schema, the success-output schema, and a worked example. All tools share the `PdfRef` input (OM-MCP-003), the error envelope (OM-MCP-004), and the limits (OM-MCP-008). `Finding` is the §H shape `{code, severity, path, message, expected?, actual?}`. `null` in `verification`/`payload` fields is significant per §E OM-DD-003 (absent/`null` are distinct).

#### om_inspect - **[OM-MCP-010]**
*Read-only. Classifies the document and reports the payload / image / text profile.*
```jsonc
// input
{ "pdf": PdfRef, "verifyOrigin": false }   // verifyOrigin default false; true triggers the §10 layer-3 check
// output (success)
{ "class": "native|hybrid|scanned",
  "pages": 42,
  "payload": { "present": true, "specVersion": "0.1",
               "hashValid": true, "originVerified": null },   // null = not checked / not verifiable
  "images": { "count": 18, "hasSMask": true,
              "colorspaces": ["DeviceCMYK","ICCBased"] },
  "textCoverage": 0.94 }                                       // 0..1 fraction of pages with extractable text
```
- **[OM-MCP-010]** When `payload.present=false`, `hashValid` and `originVerified` MUST be `null`, not `false`. `hashValid=false` means a payload was found but failed the §D.2 hash check (`hash-mismatch`); `class` MUST reflect the fixture matrix classes (§14): `native` (extractable text), `hybrid` (mixed), `scanned` (page images only).

#### om_read - **[OM-MCP-011]**
*Read-only. The cheap consumer path (§2). Returns the verified payload or null.*
```jsonc
// input
{ "pdf": PdfRef, "verifyOrigin": true }    // consumer mode defaults verifyOrigin=true when a URL is known
// output (success)
{ "payload": { /* the om.json, decompressed, as parsed */ },   // or null if no payload present
  "payloadHash": "sha256:…",                                    // recomputed per §C; null if payload null
  "specVersion": "0.1",
  "verification": { "hashValid": true, "originVerified": null, "signatureValid": null } }
```
- **[OM-MCP-011]** A Consumer MUST NOT return a non-null `payload` together with `verification.hashValid:false`. A hash-mismatched payload MUST be surfaced as `payload:null` with `verification.hashValid:false` - never as a trusted payload (§D OM-XMP-003; §J OM-SEC-005). `signatureValid` is `null` in 0.1 (reserved, §10). Cross-transport parity: the same `pdf` bytes MUST yield the same `payloadHash` on stdio and remote (OM-MCP-007).

#### om_extract_text - **[OM-MCP-012]**
*Read-only, paginated (OM-MCP-005).*
```jsonc
// input
{ "pdf": PdfRef, "pageRange": "1-5", "cursor": null, "maxChars": 100000 }
// output (success)
{ "text": "…",
  "tables": [ { "page": 3, "rows": [["cell","…"]] } ],
  "pageRange": "1-5", "truncated": false, "nextCursor": null }
```
- **[OM-MCP-012]** `pageRange` is 1-indexed inclusive (`"3"`, `"1-5"`, `"2,4,7"`); an out-of-bounds or malformed range returns `OM-IO-012`. When output exceeds `maxChars` or the server cap, the tool MUST set `truncated:true` and return a `nextCursor` (OM-MCP-005). `text` MUST NOT include image bytes; tables are best-effort structural extraction, not rendering.

#### om_extract_images - **[OM-MCP-013]**
*Read-only. Manifest + links, never bytes (OM-MCP-006; §8b).*
```jsonc
// input
{ "pdf": PdfRef, "pageRange": null, "includeVector": false }
// output (success)
{ "manifest": [ { "xref": 12, "pages": [4],
                  "width": 2400, "height": 1600,
                  "colorspace": "DeviceCMYK", "hasSMask": true,
                  "mime": "image/png", "bytes": 240233,
                  "link": "https://…/img_12.png" } ],   // or { "path": "…img_12.png" } on stdio
  "deduped": 3 }
```
- **[OM-MCP-013]** Extraction is locate + decompress only; the tool MUST NOT render/rasterize page content except the documented full-page-image fallback for scanned or vector-only pages (§8b). It MUST recombine SMasks to RGBA and convert CMYK/ICC to sRGB before emitting (§8b), and MUST dedupe by `xref` (reported in `deduped`). `includeVector` defaults false; when true, rendered fallbacks MUST be flagged (`"rendered": true`). All output paths/links are subject to §J OM-SEC-007 (no traversal outside the designated output scope).

#### om_validate - **[OM-MCP-014]**
*Validator role (§A). Two-tier (§9, §H).*
```jsonc
// input
{ "payload": { /* om.json */ },
  "tolerances": { "capRateAbs": 0.005, "psfRel": 0.02 } }   // optional; defaults per §H OM-ERR-002
// output (success - a report is success even when it contains errors)
{ "ok": false,
  "errors":   [ { "code": "OMV-E002", "severity": "error", "path": "deal.noiType",
                  "message": "noiType required when noi present" } ],
  "warnings": [ { "code": "OMW-W010", "severity": "warn", "path": "deal.capRate",
                  "message": "cap rate != NOI/price", "expected": 0.0625, "actual": 0.061 } ],
  "canonical": { "hash": "sha256:…" } }   // JCS hash of payload_for_hash (§C)
```
- **[OM-MCP-014]** `om_validate` MUST NOT mutate the payload and MUST return a report (tool success) even when `errors` is non-empty - a schema error is *data in the report*, not a tool-level error. `ok` is `true` iff `errors` is empty. `canonical.hash` MUST equal the hash a Producer would embed (§C OM-CANON-003), so callers can pre-check exactly what `om_embed` will write.

#### om_embed - **[OM-MCP-015]**
*The only mutating tool (OM-MCP-009). Producer role.*
```jsonc
// input
{ "pdf": PdfRef, "payload": { /* om.json */ },
  "badge": false,          // §4; MUST NOT modify visuals unless true (Non-goals; Rule 6)
  "sourceDocHash": true }   // compute & store meta.sourceDocHash over pre-embed bytes (§C OM-CANON-004)
// output (success)
{ "pdf": "https://…/embedded.pdf",   // or { "path": "…" } on stdio; a NEW document, input untouched
  "payloadHash": "sha256:…",
  "supersedes": "sha256:…|null",
  "xmp": { "specName": "OpenOM", "specVersion": "0.1",
           "payloadFilename": "om.json", "payloadHash": "sha256:…" } }
```
- **[OM-MCP-015]** `om_embed` MUST run `om_validate` internally and MUST refuse when schema errors are present - returning an error envelope whose `details.errors` carries the §H `OMV-E###` findings; warnings MUST pass through and MUST NOT block (§9). It MUST write the JCS bytes verbatim (§C OM-CANON-005; §D OM-EMB-010), perform the in-place replace / `supersedes` idempotency of §D OM-XMP-004 (never stacking a second `om.json`), and MUST NOT alter visual content unless `badge:true`.

---

## §J. Security considerations

### §J.0 Threat model (STRIDE)

The table enumerates the threats OpenOM tooling faces, classified by STRIDE (Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege), each bound to a **normative** mitigation requirement below. Threats are analysed against the three deployment surfaces: the hosted MCP server (network-facing), `/core` + `/js` (parsers run on untrusted input), and the extension (runs in the user's browser). Each mitigation is REQUIRED unless its requirement text says otherwise.

| # | Threat | STRIDE | Surface | Attack scenario | Normative mitigation |
|---|---|---|---|---|---|
| T1 | SSRF via `url` fetch | I, E | Hosted server (`om_read`/`om_inspect`) | Caller submits `url` pointing at `169.254.169.254` (cloud metadata) or an internal service to read credentials/data | OM-SEC-001, OM-SEC-011 |
| T2 | DNS rebinding (TOCTOU) | I | Hosted fetch | Hostname resolves public at check time, private at connect time | OM-SEC-001, OM-SEC-011 (resolve-then-pin) |
| T3 | Redirect into a blocked range | I | Hosted fetch | Public URL 302-redirects to `http://127.0.0.1` | OM-SEC-011 |
| T4 | Content-type / polyglot confusion | T | Hosted fetch | Non-PDF (or PDF-polyglot) served as `application/pdf` to smuggle a parser exploit | OM-SEC-014 |
| T5 | Decompression bomb (`om.json` Flate) | D | `/core`, `/js` | 5 MB stream inflates to gigabytes; OOM | OM-SEC-002 |
| T6 | PDF nested-stream / object bomb | D | PDF parser | Deeply nested or high-ratio streams exhaust memory before parse | OM-SEC-002 |
| T7 | XMP RDF/XML XXE & entity expansion | I, D | XMP `/Metadata` parser | External entity reads local files, or `billion-laughs` expansion; XMP is RDF/**XML**, not JSON | OM-SEC-009 |
| T8 | JSON deep nesting / duplicate keys | D, T | `om_validate`/`om_read` | Pathological nesting exhausts the parser; duplicate keys make the JCS hash ambiguous | OM-SEC-004 |
| T9 | Malformed PDF (crash / hang / OOM) | D | pikepdf / PyMuPDF / pdf.js | Corrupt xref or infinite loop crashes the worker | OM-SEC-010 |
| T10 | Path traversal in embedded filename / image output | T, E | `om_embed`, `om_extract_images` | `/F (../../etc/cron.d/x)` on read, or a traversal path on image write | OM-SEC-007 |
| T11 | Webhook SSRF | I | Extension publish | User-configured webhook URL points at an internal host on the receiver's network | OM-SEC-003 |
| T12 | HMAC secret leakage | I, S | Extension storage | Secret in `chrome.storage.sync` syncs unencrypted across devices | OM-SEC-003 |
| T13 | Webhook replay | S, T | Webhook receiver | Captured envelope re-POSTed to trigger duplicate actions | §5b (timestamp + nonce window), OM-SEC-003 |
| T14 | Hash-collision / MD5 misuse | T, S | Trust decision | Trusting the legacy MD5 `/CheckSum` as integrity | OM-SEC-005 |
| T15 | Payload spoofing (valid hash, false claim) | S, R | Consumer | Broker mislabels the deal; hash still valid | OM-SEC-005 + §10 (attribution, not crypto - market truth out of scope) |
| T16 | Blob IDOR | I | Hosted blob store | Attacker guesses/enumerates a `blobId` to fetch another tenant's OM | OM-SEC-013 |
| T17 | Supply-chain compromise | T, E | Build/CI | Compromised or typosquatted dep (pikepdf, pdf-lib, ajv) ships malicious code | OM-SEC-008 |
| T18 | Resource exhaustion / no rate limit | D | Hosted MCP | Flood of large-PDF fetches exhausts CPU/bandwidth | OM-SEC-012 |
| T19 | Extension over-permission | E | MV3 | Broad host permissions or an injected content script widen the attack surface | OM-SEC-015 |
| T20 | Covert phone-home / telemetry exfiltration | I | `/core`, consumer mode | A dependency or build silently beacons document/payload data | §M OM-TEL-001 |
| T21 | Presigned-URL abuse | I | Upload path | A leaked presigned URL is reused or over-scoped | OM-SEC-006 |
| T22 | Repudiation of an assertion | R | Payload | Publisher denies having asserted the numbers | §10 (assertedBy + hash + `supersedes` chain), §7a |


- **[OM-SEC-001] SSRF (server-side re-fetch).** `om_read(url)`/`om_inspect(url)` and the hosted server MUST refuse URLs resolving to private/loopback/link-local/metadata ranges (RFC 1918, 127.0.0.0/8, ::1, 169.254.0.0/16, 100.64.0.0/10, fc00::/7), MUST NOT follow redirects into those ranges, and SHOULD mitigate DNS-rebinding (resolve-then-pin, re-check post-resolution). HTTPS only; enforce a connect/read timeout and a max response size.
- **[OM-SEC-002] Decompression bombs.** Producers/Consumers MUST cap the decompressed payload (`om.json`) at a documented limit (RECOMMENDED 5 MB) and reject payloads exceeding it (`OM-IO-BOMB`). PDF stream expansion MUST be bounded (max total decompressed size + max compression ratio) before parsing.
- **[OM-SEC-003] Webhook SSRF & secrets.** The user-configured webhook URL is attacker-influenced relative to the receiver: the extension MUST apply the OM-SEC-001 range rules before POSTing, and MUST HMAC-sign the body (§5b). HMAC secrets MUST NOT be stored in `chrome.storage.sync` (it syncs unencrypted across devices); use `chrome.storage.local` and document that secrets are device-local.
- **[OM-SEC-004] Payload/JSON hardening.** Parsers MUST enforce a max nesting depth and reject duplicate object keys (JCS assumes unique keys). Consumers MUST treat all payload strings as untrusted data and MUST NOT execute or interpolate them (no `@context` fetch that executes code; contexts are fetched as inert JSON with the range rules of OM-SEC-001, and SHOULD be cached/pinned).
- **[OM-SEC-005] Hash assumptions.** Integrity relies on SHA-256 collision resistance; the legacy MD5 `/CheckSum` (§D) MUST NOT be used for any trust decision. `hashValid=true` proves *unaltered since embed*, not *authentic* (§10) - Consumers MUST NOT present it as authorship proof.
- **[OM-SEC-006] Blob storage.** Presigned upload URLs MUST be single-use, short-TTL, and scoped to one object; uploaded blobs are subject to the retention policy (§K).

- **[OM-SEC-007] Path traversal in file/image handling.** On read, a Consumer MUST treat the embedded `/F`/`/UF` filename as untrusted: it MUST require exactly `om.json` (§D OM-EMB-012) and MUST NOT use any embedded filename to derive a filesystem write path. When `om_extract_images` (or any tool) writes outputs, generated filenames MUST be derived from safe tokens (e.g. `img_<xref>.<ext>`), MUST be confined to a designated output directory, and MUST reject any path component that is `.`/`..`, absolute, a symlink, a Windows device name (`CON`, `NUL`, `AUX`, `COM1`…), or contains a path separator or NUL byte. A traversal attempt MUST be refused (`OM-IO-TRAVERSAL` on read, or a tool error on write), never silently written outside the output scope.
- **[OM-SEC-008] Supply-chain integrity.** Builds MUST use a committed, hash-pinned lockfile for every dependency (`uv.lock`/`poetry.lock` for Python; `package-lock.json` for `/js`), and CI MUST verify integrity hashes on install and fail on mismatch. Releases MUST be built in CI from a tagged commit (not a developer machine), SHOULD publish provenance/attestation (e.g. npm/PyPI trusted publishing with build provenance), and SHOULD be reproducible. Direct dependencies MUST be limited to the vetted set (pikepdf, PyMuPDF, jsonschema, typer, FastMCP; pdf-lib, ajv, pdf.js) plus their transitive closure; adding a new direct dependency to `/core`, `/mcp`, or consumer-mode `/js` requires the §L RFC. A CVE scan MUST run in CI and block release on a known-exploitable high-severity finding.
- **[OM-SEC-009] XMP parsing (RDF/XML) hardening.** The XMP `/Metadata` stream (§D.2) is RDF/**XML** and is parsed with an XML parser; that parser MUST disable external entity resolution (no XXE - no external DTD, no `SYSTEM`/`PUBLIC` entities, no network or file fetches) and MUST bound internal-entity expansion to defeat `billion-laughs`/quadratic-blowup (`OM-IO-BOMB`). XMP parsing MUST NOT execute or fetch anything referenced within the metadata. A malformed or over-sized XMP block MUST degrade to "payload absent / detection failed," never crash the Consumer.
- **[OM-SEC-010] PDF parser hardening.** Untrusted PDF bytes MUST be parsed with resource ceilings enforced *before and during* parse: max input size and max stream-decompression budget (OM-SEC-002, OM-MCP-008), a wall-clock timeout per operation, and a bounded object/xref-recursion depth. Parsing SHOULD run in an isolated, memory-limited worker/process so a crash or OOM in pikepdf/PyMuPDF/pdf.js cannot take down the host; the hosted server MUST convert a parser crash/timeout into `OM-IO-010`/`OM-IO-003`. Consumers MUST NOT enable any PDF-parser feature that executes embedded JavaScript or launches external actions.
- **[OM-SEC-011] Redirect & DNS-rebinding controls.** Server-side fetches (OM-SEC-001) MUST cap redirects (RECOMMENDED ≤ 5) and MUST re-apply the OM-SEC-001 address-range check to **every** hop, including the final resolved IP. Implementations MUST mitigate DNS rebinding by resolving the hostname, validating the resolved address(es) against the block list, and **connecting to the pinned validated address** (resolve-then-pin), not re-resolving between check and connect. A hop or resolution that lands in a blocked range MUST fail with `OM-IO-009`/`OM-IO-002` and MUST NOT be followed.
- **[OM-SEC-012] Rate limiting & quotas (hosted).** The hosted MCP server and upload endpoint MUST enforce per-principal rate limits and concurrency/size quotas, and MUST return `OM-IO-014` with a `Retry-After` when exceeded. Limits MUST be documented. Rate limiting MUST NOT weaken any correctness or verification guarantee - it only bounds resource use.
- **[OM-SEC-013] Blob authorization (anti-IDOR).** `blobId` values MUST be unguessable (≥ 128 bits of entropy) and MUST be authorization-checked against the calling principal on every access; a `blobId` belonging to another principal MUST return `OM-IO-007` (not `OM-IO-006`, to avoid leaking existence only where policy permits). Blobs are single-tenant, subject to OM-SEC-006 and the §K retention policy.
- **[OM-SEC-014] Fetched-content verification.** Before parsing, a fetched resource MUST be confirmed to be a PDF by inspecting the leading bytes (`%PDF-`), independent of the `Content-Type` header, and MUST be rejected with `OM-IO-005` otherwise. The declared `Content-Type` MUST NOT be trusted for security decisions. Response size MUST be enforced incrementally during download (OM-SEC-002, OM-MCP-008), not only after completion.
- **[OM-SEC-015] Extension least-privilege (MV3).** The extension MUST request the minimum host permissions necessary and SHOULD prefer `activeTab` / user-gesture-scoped access over broad `<all_urls>` host grants; link-level detection host access is per-domain opt-in (§5b). Content scripts MUST NOT inject into or read logged-in third-party app surfaces (Non-goals; no chat-UI puppeteering). Secrets and device-local settings live in `chrome.storage.local`, never `chrome.storage.sync` (OM-SEC-003). The extension MUST NOT weaken page security (no disabling CSP, no `eval` of remote code); the `/js` subset it ships MUST remain inference-free in consumer mode (§6a).
