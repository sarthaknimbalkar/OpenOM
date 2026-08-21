# openOM — Recon: Feature Map, Gaps, Market & Opportunities

> **Purpose.** A thorough, honest reconnaissance of what openOM is today, where it can still
> improve technically, what problems the commercial-real-estate (CRE) data industry actually has,
> and how openOM can win — beyond everything already built.
>
> **Author's note.** openOM = an open (MIT) **standard + toolchain** that embeds a machine-readable,
> broker-asserted data payload inside CRE offering-memorandum (OM) PDFs (Factur-X / PDF-A-3
> mechanism) and mirrors the same payload as JSON-LD on the web. *Extract once at the source; consume
> infinitely, cheaply, downstream.* Published under **Vervelio Labs** (neutral steward).
>
> The one rule that governs everything: **deterministic core, inference at the edges.** The engine,
> MCP server, and consumer tooling contain zero LLM/inference calls, ever. Assertions, not facts:
> every payload is an identified party's opinion as of a date.

_Compiled 2026-08-19. Sections are dated where they reflect a point-in-time market read._

> **Decision overlay (2026-08-21).** The strategic questions in §7.7 have been answered in
> [`openOM-decision-memo.md`](openOM-decision-memo.md). This recon's *analysis* stands; several
> *recommendations* were overridden. Read the memo as authoritative where they differ. Quick map:
> - **O1 (deep schema — rent roll/T-12/multifamily): DROPPED.** Underwriting happens at the deal
>   desk off broker-of-record files, never pre-LOI off OM data. Schema stays **thin, common-
>   denominator, investment-property-first**; uneven data is a *feature* (better-documented listings
>   rise to the top).
> - **O9 (embed partner): REDIRECTED** away from a Buildout/Crexi BD deal → **DealGround** ingestion
>   + a **NEW first-class path: a Buildout MCP OAuth connector** that pulls structured data at the
>   source (property/deal/lease/rent schedule) *before* the PDF is flattened. It's a data-fetch, not
>   inference (cardinal rule holds); on-device Gemini-Nano extraction becomes the *fallback*. No BD
>   dependency — user-authorized OAuth. This is now the **#1 sequence item** and a second cold-start
>   lever alongside M1.
> - **O5/O6 (signatures / DNS origin): PARKED.** Casual L2 integrity-only for now.
> - **O2 (RESO alignment): HELD.** Independent unless RESO initiates.
> - **O14 (anti-hallucination AI-grounding): CONFIRMED as the lead** — grounded in the sharpened
>   posture below.
> - **Philosophy sharpened:** an OM is *an advertisement — a broker's **opinion of value** the
>   seller agreed to before creation._ "Verified" means *asserted-by-whom, unaltered, as-of-when* —
>   never "true."

---

## Table of contents

1. [Feature inventory — what openOM ships today](#part-1--feature-inventory)
2. [Internal technical gaps — beyond the open issues](#part-2--internal-technical-gaps)
3. [Market research — the industry & the OM workflow](#part-3--market-research-the-industry--the-om-workflow)
4. [Competitive & adjacent landscape](#part-4--competitive--adjacent-landscape)
5. [Pain points by persona → openOM's answer](#part-5--pain-points-by-persona--openoms-answer)
6. [Strategic improvement opportunities](#part-6--strategic-improvement-opportunities)
7. [Adoption barriers, risks & open questions](#part-7--adoption-barriers-risks--open-questions)
8. [Prioritized recommendation matrix](#part-8--prioritized-recommendation-matrix)

---

## Part 1 — Feature inventory

_What is actually built and shipping today. Grouped by layer; each item is real, tested code on
`main` unless marked otherwise._

### 1.1 The specification (the product)

- **Payload JSON Schema 0.1** (`spec/om-0.1.schema.json`, JSON Schema 2020-12) — property, deal,
  lease, rent schedule, assertedBy identity (broker, brokerage, license, website,
  licenseJurisdiction/Authority), `meta` (supersedes, sourceDocHash, signature), `ext` extension
  object, `propertyType`, `noiType` (in-place|pro-forma) + `noiAsOfDate`.
- **JSON-LD `@context` / vocabulary** (`spec/context/openom-0.1.jsonld`) — schema.org reuse where a
  term exists, `om:` namespace otherwise, xsd datatype coercions ([OM-LD-004]).
- **Canonical finding-code registry** (`spec/codes.json`) — 29 codes (error/warning/info) → the
  requirement clause each enforces; both cores drift-lock to it.
- **Webhook envelope schema** (`spec/webhook-envelope-0.1.schema.json`) — the §Y change-notification
  contract, with a MUST payloadHash↔payload binding.
- **Conformance vectors** (`spec/vectors/`) — the anti-fork oracle: JCS expected canonical bytes +
  SHA-256 hashes, golden embedded PDFs, negative/tampered cases, and a 600-case differential-fuzz
  corpus. Both implementations reproduce them byte-for-byte.
- **Hosted namespace tree** (`site/`, generated) — the pinned `$id`/`@context` URLs actually
  resolve (ns/0.1 as `application/ld+json`, schemas as `application/schema+json`, open CORS via
  Cloudflare `_headers`); drift-locked in CI.
- **Per-persona docs site** (`site/openom/docs/`, generated) — broker / portal / developer
  quick-starts + a field reference and validation-code catalog **generated from** the schema and
  codes registry (cannot drift), + a hosted client-side "verify a PDF" tool.
- **Governance / stewardship** — published under Vervelio Labs (neutral), MIT toolchain +
  CC-BY-4.0 spec; namespace `https://verveliolabs.com/openom/...`.

### 1.2 The trust model (§AA — the reason anyone believes a payload)

Four provenance layers, strict precedence, **honest by construction** (never overclaims):

- **L1 present** — is there an embedded payload at all?
- **L2 integrity** (`hashValid`) — payload unaltered since embed (SHA-256 over the exact stored
  bytes vs the XMP marker). Terminal on mismatch. Copy: *"Unaltered since embed"* — never
  "verified/authentic/signed/official/genuine" (a FORBIDDEN word list enforces this).
- **L3 origin-verified** — the hosting domain vouches for this exact payload (HTTPS + a same-
  registrable-domain mirror whose hash matches). PSL-aware so a shared host can't cross-vouch.
- **L4 signature-verified** — reserved for 0.1 (never returned yet).
- **Assertions, not facts** — `assertedBy` + `assertedDate` + `noiType` + `noiAsOfDate` are
  required; tooling checks internal consistency, never market truth.

### 1.3 Deterministic core — Python (`/core`, `openom-core`)

- **embed / read** — Factur-X attach of `om.json`, XMP `omspec:` marker (payloadHash, assertedDate,
  supersedes, sourceDocHash), idempotent re-embed (replace-not-stack), non-destructive (visually
  identical), `meta.supersedes` on reprice, sourceDocHash stable across reprices.
- **inspect / classify** — native / hybrid / scanned + **OCR'd-scan detection** (invisible text
  layer over a full-page image via render-mode analysis), classification confidence, text coverage,
  ocrOverlay fraction.
- **extract text** — deterministic page text with pagination.
- **extract images** — locate + decompress + recombine SMask→RGBA, CMYK/ICC/Indexed→sRGB, dedupe by
  xref + content hash, decompression-bomb guard, **CCITT G4 / JPEG 2000** codec coverage,
  **vector-only page render fallback**, inline-image capture via the fallback, and a **pdfium
  differential decode cross-check**.
- **validate** — two-tier: schema errors **block**, consistency warnings **never block** (NOI÷price
  vs cap rate, rent-schedule sums, date/term math, currency defaults); market truth out of scope.
- **canonicalize** — RFC 8785 (JCS); SHA-256 over canonical bytes = the integrity hash and the
  anti-fork keystone.
- Deterministic, pure, `mypy`/`ruff`-clean, **zero inference deps** (CI-enforced boundary).

### 1.4 CLI (`/cli`, `om`)

`om embed · read · inspect · validate · check · extract · conformance · version · watch`.
Watch-folder server-side automation (drop `<name>.pdf` + `<name>.json` → embedded OM out,
`--once`/polling, schema-gated skip). `--format pretty|compact`, `--quiet`, stdin/stdout piping,
UTF-8-forced output, §I exit-code contract. Zero UI, zero inference.

### 1.5 MCP server (`/mcp`)

- **Six deterministic tools**: `om_inspect · om_extract_text · om_extract_images · om_read ·
  om_validate · om_embed` (+ `om_request_upload`). Compact outputs (paginated text, image manifests
  + links — never raw bytes into context).
- **Dual transport** — stdio (local) + hosted Streamable HTTP (`build_http_app`/`main_http`).
- **Hosted hardening** — SSRF-hardened `url` fetch (resolve-then-pin), R2/local blob store
  (≤24h TTL, delete-on-completion, server-bound owner, anti-IDOR), per-principal rate limit
  (in-memory **and** distributed via a Redis-backed CounterStore seam), **API-key lifecycle**
  (issue/verify/rotate/revoke + per-key quota, hash-only storage), untrusted-PDF parse isolation
  (killable subprocess, timeout/crash → mapped error), per-call page ceiling, structured stderr
  logging, HTTP Host/Origin security.
- **Cardinal boundary** — the paid inference-extraction service is a **seam only** (402); zero
  inference in `/mcp` (CI-enforced import-graph + dependency checks).

### 1.6 TypeScript reference (`/js`, `openom-js`)

Byte-parity with the Python core: canonicalize, hash, embed, reembed (+ sourceDocHash carry),
verify, parse, crypto, **verifyOrigin** (§10 domain-origin + PSL), **badge** (§AA state machine +
honest labels + FORBIDDEN list), consistency, text extraction, **in-browser decryption** of
empty-user-password AES OMs (V4/R4 + V5/R6, object-stream handling), webhook envelope build/verify
(two-sided HMAC + SSRF host-guard), marker-property read. Worker-free read path (pdf-lib + zlib /
DecompressionStream; pdf.js only as an encrypted fallback), eval-free validator (ajv standalone).

### 1.7 Embeddable widget (`/js/widget`, `<openom-badge>`)

Drop-in web component for portals: re-fetch bytes → read → integrity → optional origin → §AA badge,
reusing the exact openom-js path (so a portal badge can never disagree with the extension). Static
copy only (no payload text → no XSS), absent → renders nothing, fails closed on error. Single
minified IIFE, asserted inference-free.

### 1.8 Browser extension (`/extension`, MV3 Chrome)

- **Consumer mode** — detect (re-fetch bytes, never scrape the viewer) → read → validate →
  verifyOrigin → stale → per-tab badge; popup card with source tags + residual warnings + stale
  notice; named-webhook publish (test-fire/copy/download); options page + opt-in proactive
  detection + per-domain link-badging content script.
- **Author mode** — side-panel capture → schema-driven review form (per-field value + evidence,
  omissions, residual warnings, reprice diff) → **explicit human assert** (stamps assertedBy/
  assertedDate, promotes rent `extracted→asserted`, `meta.supersedes` on reprice) → embed via
  `/js` → blob download. **On-device extraction** via the browser Prompt API (Gemini Nano) —
  evidence-cited draft, human-only-field guard, prompt-injection fence, egress-zero
  ([OM-PRIV-001]); **in-browser encrypted-OM decrypt** before authoring.
- **Quality** — worker-free + eval-free under MV3 CSP, full design system + WCAG-AA a11y (axe-gated),
  inference-free bundle (asserted), pdf.js lazy-loaded as an on-demand chunk.

### 1.9 Process / playbook (`/process`, no code)

`SKILL.md` (Claude-invocable `openom-author`) + `agent-instructions.md` (any MCP client) +
`mapping-guide.md` (field map / vocabulary / consistency, drift-locked to the schema) +
`review-contract.md` (the human assertion gate) + a worked `example/` (OM → payload → transcript,
CI-gated) + a **Prompt-API manual-verification kit**. Inference lives ONLY in the agent's mapping
step; every `om_*` tool stays deterministic.

### 1.10 Distribution & ops

GitHub Action (`openom-embed`, CI embed/validate), hosted client-side verify tool, examples gallery
+ reference webhook receiver, Cloudflare Pages site deploy, PyPI Trusted-Publishing + npm
`--provenance` release workflows, Chrome Web Store packaging. Edge supported (same MV3 build);
Firefox roadmapped.

### 1.11 Quality, security & anti-fork machinery

- **Cross-implementation anti-fork oracle** (Python ⇄ JS read each other's output; byte-identical
  canonical JSON + hash), **JCS differential fuzz** (600 cases), **RFC 8785 vectors**, **boundary**
  (no-inference) enforcement, SBOM, vuln-scan, seeded-defect gate, headed real-browser Playwright
  gate (local), mutation testing (local).
- **Security posture** — SSRF resolve-then-pin, blob owner-binding, subprocess isolation, bomb
  guards, empty-password decrypt validation (never emits a corrupt OM), two-sided HMAC webhooks,
  constant-time compare, AES-GCM secret storage, SW message-origin gate.
- **Real-OM evidence** — non-destructive embed proven across ~60 producers on a 1330-OM corpus;
  125/125 in-scope encrypted OMs decrypt render-identical (pikepdf oracle).

---

## Part 2 — Internal technical gaps

_Where the current architecture can still improve, **beyond** the open GitHub issues. Ranked
roughly by leverage. These are engineering/product observations, not GTM (see Part 6)._

### 2.1 Schema breadth — the biggest technical gap

> **⚑ Decision (2026-08-21): deprioritized — not a build target.** Per the
> [decision memo](openOM-decision-memo.md) §1–2, deep underwriting schema is out of scope:
> underwriting happens at the deal desk off broker-of-record files, never pre-LOI off OM data.
> Schema stays thin / common-denominator / investment-property-first; uneven data is a *feature*.
> The analysis below is retained as an accurate description of the data *shape*, **not** a
> recommendation to build it.

The schema is **heavily single-tenant net-lease (STNL)-shaped** (`lease.tenantEntity`,
`rentSchedule`, `leaseTypeAsserted: NNN`, single `noi`). Real CRE spans asset classes with very
different data shapes, and the current model can't represent most of them well:

- **Multifamily** — unit mix, unit-level rent roll, occupancy/vacancy, T-12 operating statement,
  expense ratios, in-place vs market rent, loss-to-lease, RUBS, concessions.
- **Multi-tenant office / retail / industrial** — a rent roll with *many* tenants, suite/unit
  granularity, lease abstracts (options, renewals, percentage rent, CAM/expense reimbursements,
  escalations, TI/LC), WALT, occupancy, anchor vs inline.
- **Hospitality** — ADR, RevPAR, occupancy, flag/brand, PIP.
- **Land / development** — entitlements, zoning, density, FAR, pro-forma development budget.
- **Debt / financing assumptions** — existing loan, assumable debt, DSCR, LTV, going-in vs
  stabilized, sources & uses.
- **Operating statement (T-12 / pro-forma)** — line-item income and expenses, not just a single
  NOI number. This is where most underwriting actually happens.

**Implication:** openOM today captures the *headline* deal facts well but not the *underwriting*
detail. A buyer's analyst still re-keys the rent roll and T-12 from the PDF. That's the 80% of the
re-keying pain the standard exists to kill. → A modular, asset-class-aware schema (a shared core +
per-asset-class modules) is the highest-leverage technical investment.

### 2.2 Scanned OMs can't be extracted deterministically at all

The core is deterministic and inference-free, so a **scanned OM with no text layer** (~10%+ of the
corpus, and higher among older/owner-brokered deals) yields *nothing* from `extract_text`. Options,
none clean under the cardinal rule:

- OCR is inference-adjacent; it belongs at the edge (author-mode / process layer), not `/core`.
- Today the story is "author mode + on-device extraction can read a scan visually" — but the
  deterministic pipeline everyone else relies on is blind to scans.
- **Gap:** a clear, first-class "scanned → author-assisted → asserted payload" path, and guidance
  that scanned OMs are an *author-time* problem, not a consumer-time one. The OCR-scan *detection*
  (#6) is done; the OCR *extraction* handoff is not productized.

### 2.3 Origin verification depends on a same-domain mirror few brokers will host

> **⚑ Decision (2026-08-21): parked (O6).** Casual L2-integrity-only for now; DNS/`.well-known`
> origin anchoring is not being pursued. Analysis retained for when the trust layer is revisited.


L3 (origin-verified) requires the broker to host `deal.json` on the same registrable domain as the
PDF. Most brokers publish via Buildout/Crexi/email/Dropbox — they don't control a matching HTTPS
origin. So in practice most payloads top out at **L2 (integrity-only)**. Alternatives worth designing:

- **DNS-anchored proof** — a `TXT`/`.well-known/openom` record binding a brokerage domain to a
  signing key, so origin can be proven without a per-deal mirror.
- **Cryptographic signature (L4)** — a detached signature (JWS/COSE, or PAdES on the PDF) by a
  brokerage key, verifiable offline with no mirror at all. This is the *reserved* layer; making it
  real is the durable answer to "who says so."
- **Marketplace-hosted vouching** — if Crexi/Buildout served the mirror, origin would light up for
  everyone on that platform (a partnership play, Part 6).

### 2.4 Verifiable identity — `assertedBy` is self-asserted

Anyone can put any brokerage name + license number in `assertedBy`. There is no binding between the
claim and a real, verifiable identity. Ladder of increasing trust:

- License-number *format* validation per state (cheap, deterministic) — not done.
- License-number *liveness* check against state DRE registries (a service, not core).
- Verifiable Credentials / DID for brokerages (an org signs; consumers verify the org, then the
  org's signature over the payload). Aligns with L4.

### 2.5 Signature layer (L4) is reserved, not real

> **⚑ Decision (2026-08-21): parked (O5).** Casual L2-integrity-only signing stands; no cryptographic
> L4 investment now. Revisit only if the space develops to make it worth it.


No cryptographic signing exists yet. Without it, "origin-verified" is the ceiling and it's fragile
(mirror-dependent, revocable by moving a file). Real signing (per §2.3) is the single biggest
*trust* upgrade and unblocks offline verification, mirror-free origin, and identity binding.

### 2.6 Revocation / correction discovery

`meta.supersedes` records that a payload replaced a prior one **inside a PDF**, but a consumer who
already downloaded v1 has no way to learn v2 exists, or that a deal was withdrawn/repriced/pulled.
There's no web-discoverable "latest state for this asset" or revocation feed. → A lightweight
`.well-known` "latest/withdrawn" lookup, or the webhook envelope extended to a public update feed.

### 2.7 Language/runtime reach — only Python + JS

Enterprise consumers (underwriting models in **Excel/VBA**, CRMs in **Java/.NET**, data pipelines in
**Go/Rust**, analytics in **R**) can't natively read/verify a payload. The JSON-LD is portable, but
the *canonicalization + hash verification* (the thing that makes it trustworthy) needs a conformant
implementation. → At minimum: a tiny **verification-only** library port (read + JCS + hash + badge
state) in Go, Java, and C#; and an **Excel/Google-Sheets** function that pulls a payload into cells.

### 2.8 Consumption ergonomics — nobody lives in JSON-LD

Brokers and analysts live in **Excel, email, and their CRM**. openOM emits JSON-LD. Missing
last-mile:

- **CSV/XLSX export** of a payload (and of a rent roll / T-12 once §2.1 lands).
- **Email/inbox ingestion** — OMs arrive as email attachments; there's no "forward it and get a
  payload" path.
- **CRM/marketplace connectors** — no native Buildout/Crexi/CoStar/Salesforce/HubSpot integration.

### 2.9 Testing & evidence depth

- **No real embedded-OM corpus in CI** (#22/#9) — proofs are synthetic; the private 1330-OM corpus
  is local-only. A committable, redistributable "golden real-ish OM" set (synthetic but
  producer-diverse and asset-class-diverse) would raise confidence.
- **Cross-impl parity does not yet cover marker provenance** (supersedes/sourceDocHash derivation
  differs subtly between Python and JS) — a latent fork risk if the two diverge further.
- **Mutation testing is Python-only + local**; JS mutation (Stryker) abandoned.
- **No fuzzing of the PDF parse path** against malformed/hostile PDFs beyond the guard tests.

### 2.10 Performance & scale

- No streaming for very large (100+ page, image-heavy) OMs — read/inspect load the whole doc.
- Image extraction materializes full rasters; a batch/server path over thousands of OMs (the
  "process a brokerage's back-catalog" use case) has no throughput story.
- The extension bundle is large (pd-lib + ajv duplicated across contexts); fine for load-once, but
  a lighter verify-only path would help embeds.

### 2.11 Spec formalism & conformance program

- No RFC-style normative spec document, no versioned governance process, no **conformance
  certification** (a badge/test-suite third parties run to claim "openOM-conformant"). For a
  *standard*, this is how you get independent implementations without forks.
- The codes registry + vectors are excellent raw material for a public conformance suite — it isn't
  packaged as one yet.

### 2.12 Observability for consumers

- No way for a portal/consumer to report "I saw a hash mismatch on this URL" back to anyone; no
  abuse/tamper telemetry loop. The badge is honest but silent.

---

## Part 3 — Market research: the industry & the OM workflow

_Grounded in 2025–2026 sources (linked at the end of Part 4). Numbers are industry-reported, treat
as directional._

### 3.1 What an OM is and why it's a data-quality black hole

A CRE **offering memorandum** is the marketing + financial-disclosure PDF a broker produces to sell
a property. It carries the facts a buyer needs to screen and underwrite: price, cap rate, NOI, the
rent roll, the T-12 operating statement, lease abstracts, property description, photos, maps. It is
almost always a **designed PDF** (InDesign / Buildout / Word) — human-readable, machine-opaque.

The economic problem: **the same facts are re-extracted by every downstream party, by hand, over and
over.** The broker's tool *generated* the OM from a structured property record — then flattened it to
a PDF — and every recipient re-keys it back into a model.

### 3.2 The cost of manual re-keying (the core pain, quantified)

- **CBRE (2025): 62% of institutional acquisitions analysts spend most of their time on data
  entry.** This is the headline stat for the whole thesis.
- A senior analyst spends **20–30 minutes of pure data entry per OM just to reach a kill/pursue
  decision**; at 10–15 OMs/week that's **4–6 hours/week of high-cost analyst time** producing zero
  insight.
- Full transcription (rent roll + T-12 + lease abstracts into Excel/Argus) runs **2–4 hours per
  deal**, sometimes cited as **4–8 hours**.
- Re-keying is also an **error** source — a mis-typed NOI or rent figure propagates into the model
  and the decision.

### 3.3 How OMs flow today (the value chain)

1. **Authoring / marketing** — the broker builds the OM in **Buildout** (private marketing + CRM
   engine, OM/flyer generation is its reason to exist) or **Crexi Create** (generates OM drafts from
   financials/leases/rent rolls or an address), or InDesign/Word. *The structured data exists here.*
2. **Distribution** — the OM is published to a **marketplace** (**Crexi** — public deal flow;
   **CoStar/LoopNet** — largest, ~13M monthly visitors, data + comps breadth) and/or emailed
   directly to buyer lists and posted to deal rooms.
3. **Consumption** — buyers/analysts, lenders/underwriters, and increasingly **LLM agents**
   re-extract the OM to screen, underwrite, and comp. *The structured data is reconstructed here, per
   firm, per deal, badly.*

openOM inserts a machine-readable, verifiable payload at step 1 (or 2) so step 3 is free.

### 3.4 The precedent that proves the mechanism: Factur-X / ZUGFeRD

The exact mechanism openOM uses (a hybrid PDF: human-visual + embedded structured data in PDF/A-3)
is already a **production, ISO-standard, cross-industry success** in e-invoicing:

- ZUGFeRD (Germany) + Factur-X (France), harmonized, embedded UN/CEFACT XML in a PDF/A-3, meeting
  EU standard EN 16931. AP teams post incoming hybrid invoices **automatically — cutting re-keying,
  OCR cost, and disputes.** This is openOM's value prop, already validated in an adjacent trillion-
  dollar workflow.
- **The adoption lesson (and caution):** Factur-X's uptake is driven by **government mandate**
  (France mandatory 2026; Germany phased 2025→2028; Belgium 2026) and a **central platform**
  (Chorus Pro). **CRE has no mandate and no central platform.** So openOM cannot ride regulation —
  it must win on **network value and marketplace distribution** (Part 6). The mechanism is proven;
  the go-to-market must be earned.

### 3.5 The AI wave is making the problem *worse*, not better — openOM's wedge

Every acquisitions/lending shop is now bolting **general-purpose AI** onto OM extraction (Docsumo,
RealQuant, Blooma, Crexi Vault, Cashflow Portal, and a long tail of GPT wrappers). This creates a
**new** problem the industry is actively afraid of:

- **AI hallucination in CRE is a named, feared failure mode** — models "confidently generate false
  figures" (fabricated NOI, population/income growth, lease terms) that "appear accurate on the
  surface." Practitioners warn that handing AI-generated pro-formas to a client "can set you up for
  disaster."
- CRE workflows "depend on **explainability, provenance, and defensible outputs**." Even
  **hallucinated *metadata*** is flagged as dangerous because it looks authentic and is unchecked.
- The industry's own recommended mitigation is **RAG over verified sources** — i.e., ground the
  model in real, structured facts.

**This is openOM's wedge.** Every AI tool re-extracts and can hallucinate; openOM provides the
**at-source, broker-asserted, evidence-cited, hash-verified fact** that (a) removes the need to
re-extract and (b) is the ideal RAG/grounding source that *can't* silently drift — you can prove the
NOI is what the broker asserted, unaltered, by whom, as of when. openOM turns "AI guessed" into
"the broker asserted, and here's the cryptographic proof."

---

## Part 4 — Competitive & adjacent landscape

_openOM is **not an extraction app** — it's an open standard + at-source embed. The "competitors"
mostly validate the pain; several are better understood as **future consumers or embed partners**._

### 4.1 Downstream AI extraction tools (buyer/lender side) — the pain-validators

**Docsumo, RealQuant, Blooma, Crexi Vault, Cashflow Portal AI, AcquiOS, PropRise, v7 Labs, Kolena.**
They extract rent rolls / T-12s / OMs into models — each firm, each deal, repeatedly. RealQuant
(Excel add-in, cell-level source citations, built by REPE principals), Docsumo (auto-spread T-12/rent
roll/OM), Blooma (lending workflow + audit trails), Crexi Vault (24+ data points, ~2 min vs 30 min).

- **How openOM relates:** for an openOM-enabled OM, their expensive+hallucination-prone extraction
  becomes a **free, verified read**. The smart ones should *consume* openOM (read the payload, skip
  extraction, keep their model/UX) — openOM is upstream infrastructure, not a rival model.
- **openOM's edge:** they produce *unverified, per-firm, possibly-hallucinated* data; openOM
  produces *one at-source, asserted, hash-verified* fact with a named asserter and date.

### 4.2 Authoring / marketing tools (broker side) — the ideal embed partners

**Buildout** (private OM/marketing/CRM engine — OM generation is its core) and **Crexi Create**
(generates OM drafts from financials/leases/an address). **These tools already hold the structured
property record they flatten into the PDF.** Embedding an openOM payload at generation time is nearly
free for them and is the purest form of "extract once at the source."

- **This is the single highest-value partnership vector.** If Buildout/Crexi Create emit openOM by
  default, the standard is populated at the source overnight.

### 4.3 Marketplaces / distribution — origin-vouching + reach

**Crexi** (public deal flow), **CoStar / LoopNet** (largest, data + comps). If a marketplace hosts
the mirror / serves the payload, **origin-verification (L3) lights up for every listing on the
platform** — solving §2.3 at scale. They're also the discovery layer where a "verified openOM" badge
would be seen.

### 4.4 Data standards — align, don't reinvent

- **RESO (Real Estate Standards Organization)** — the residential standard (Data Dictionary + Web
  API, replaced RETS). CRE is explicitly "**stagnant on standards**"; RESO has a **nascent CRE
  working group** building Data-Dictionary extensions. **openOM should align its vocabulary with the
  RESO CRE Data Dictionary** (map `om:` terms to RESO fields) — riding the emerging authority
  instead of competing with it, and positioning openOM as *the transport/provenance layer* over
  RESO's *vocabulary layer*.
- **schema.org** `RealEstateListing` — already reused in the `@context`; keep extending the JSON-LD
  alignment for web/SEO discoverability.

### 4.5 Data aggregators / comps / deal management — adjacent consumers

**CoStar, Reonomy, Cherre, MSCI/Real Capital Analytics** (property + market + comp data);
**Dealpath, Juniper Square** (deal/investment management). Different layer (they aggregate *market*
data), but they all ingest *deal* facts and would benefit from a verified at-source feed. Comps
databases in particular are built from exactly the facts openOM carries.

### 4.6 Where openOM uniquely sits (the moat)

| Axis | Everyone else | openOM |
|------|---------------|--------|
| **Where extraction happens** | Downstream, N times, per firm | Once, at the source |
| **Trust model** | AI-extracted, unverified, hallucination-prone | Broker-asserted, evidence-cited, hash-verified |
| **Ownership** | Proprietary, siloed per vendor/platform | Open (MIT) standard, neutral steward |
| **Where the data lives** | Locked in a vendor DB / platform | **In the artifact** — travels with the PDF, offline, survives email/re-host |
| **Provenance** | None (who said this? when? altered?) | `assertedBy` + `assertedDate` + integrity hash + supersedes lineage |
| **Cost to consume** | Per-extraction compute + risk | ~Free deterministic read |

**Positioning in one line:** *openOM is not another AI extractor — it's the open provenance + data
layer that makes extraction unnecessary and AI grounding trustworthy.*

### Sources (Parts 3–4)

- Kolena — [OM guide](https://www.kolena.com/blog/offering-memorandum-in-real-estate-investing-a-complete-guide/)
- RealQuant — [AI underwriting in Excel](https://www.realquant.ai/), [document intelligence](https://www.realquant.ai/solutions/document-intelligence/), [best AI tools 2026](https://www.realquant.ai/resources/blog/best-ai-tools-cre-underwriting-2026/)
- Docsumo — [CRE underwriting extraction](https://www.docsumo.com/solutions/use-cases/cre-underwriting)
- Blooma — [AI CRE lending](https://www.blooma.ai/)
- AcquiOS — [software that reads OMs](https://acquios.ai/blog-software-reads-offering-memorandums)
- The Fractional Analyst — [AI in CRE finance](https://thefractionalanalyst.com/tfa-blog/ai-in-commercial-real-estate-finance)
- Blooma — [underwriting time](https://www.blooma.ai/blog/how-long-does-underwriting-take)
- RESO — [expanding commercial data](https://www.reso.org/blog/expanding-commercial-data/); Constellation Data Labs — [what is RESO](https://cdatalabs.com/what-is-reso-and-why-does-it-matter-for-real-estate-data-products/)
- theBrokerList — [AI hallucination speed trap in CRE](https://blog.thebrokerlist.com/the-ai-hallucination-speed-trap-in-commercial-real-estate/)
- First American DNA — [AI in CRE study](https://dna.firstam.com/insights-blog/ai-in-commercial-real-estate-study-strategic-implications)
- Law360 — [AI can hallucinate metadata](https://www.law360.com/articles/2405475/attys-beware-generative-ai-can-also-hallucinate-metadata)
- CRE Daily — [Crexi review](https://www.credaily.com/reviews/crexi-review/); NextAutomation — [CoStar vs Crexi](https://nextautomation.us/blog/costar-vs-crexi), [Buildout vs Crexi](https://nextautomation.us/blog/buildout-vs-crexi)
- vatcalc — [France/Germany e-invoicing](https://www.vatcalc.com/france/france-german-e-invoicing-standard-update/); SEEBURGER — [ZUGFeRD 2.3 / Factur-X 1.0.07](https://blog.seeburger.com/france-and-germany-publish-their-new-version-of-the-joint-standard-for-electronic-invoicing-zugferd-2-3-and-factur-x-1-0-07-from-ferd-and-fnfe-mpe/); iText — [creating ZUGFeRD](https://itextpdf.com/blog/technical-notes/creating-zugferd-itext)

---

## Part 5 — Pain points by persona → openOM's answer

_For each stakeholder: the concrete pain, what openOM does **today**, and what's still **missing** to
fully win them._

### 5.1 Broker / seller-side (the author — the party that must adopt first)

- **Pain:** builds the OM once, then fields the same data questions from every buyer; has no way to
  prove the numbers are theirs and unaltered; loses control once the PDF is emailed and re-hosted;
  gets misquoted when a buyer's model mis-keys a figure.
- **openOM today:** author-mode capture → review → **assert** (stamps identity + date) → embed;
  on-device extraction to pre-fill; reprice with `supersedes`; the payload travels with the PDF and
  is tamper-evident.
- **Still missing:** the broker has ~zero incentive to do *extra* work → **the embed must be
  invisible** (happen inside Buildout/Crexi at generation time, §4.2), not a separate extension
  step. Also: verifiable *identity* (§2.4) so "asserted by ACME Realty" means something; a
  brokerage-branded "verified data" badge as a *marketing* asset ("our OMs are openOM-verified").

### 5.2 Buyer / acquisitions analyst (the consumer with the money and the pain)

- **Pain:** the CBRE 62% stat — most of their time is data entry; 20–30 min/OM to even screen;
  re-keying errors; AI extraction they don't fully trust.
- **openOM today:** deterministic read → the deal facts in milliseconds, with integrity + honest
  badge; no re-extraction for openOM-enabled OMs.
- **Still missing:** ~~underwriting-grade detail (full rent roll, T-12, lease abstracts)~~
  **[struck 2026-08-21 — deliberately out of scope: the analyst underwrites at the deal desk off
  broker-of-record files, not off the OM; openOM captures the *advertised opinion*, not the
  underwriting model]**; a **fallback** for the majority of OMs that *aren't* openOM-enabled yet
  (the cold-start problem — see §7). Until source adoption is high, the analyst still needs an
  extractor for most deals; openOM should make being openOM-enabled the *premium, trusted* path.
  The buyer's win is a **faster, trustworthy screen** (is this worth a call?), not a filled model.

### 5.3 Portal / marketplace (Crexi, LoopNet, deal rooms — the distribution + trust layer)

- **Pain:** listing data quality is inconsistent; buyers don't trust unverified numbers; the
  platform re-extracts uploaded OMs (Crexi Vault) at its own cost.
- **openOM today:** the embeddable `<openom-badge>` widget; verifyOrigin; the platform *could* host
  the mirror to light up L3 for every listing.
- **Still missing:** a **first-class marketplace integration** (ingest openOM payloads on upload,
  display the verified badge, serve mirrors) — turnkey, not DIY; a reason for the platform to
  care (verified listings as a trust/differentiation feature, fraud reduction).

### 5.4 Lender / underwriter (defensibility is everything)

- **Pain:** underwriting takes days; must produce **defensible, auditable** numbers; AI-generated
  analysis is a liability risk; needs provenance for credit committee and compliance.
- **openOM today:** hash-verified, asserted-by, evidence-cited facts — inherently defensible and
  auditable; deterministic (no hallucination).
- **Still missing:** the T-12/debt/DSCR detail (§2.1); **signature/identity** (§2.4–2.5) for true
  non-repudiation ("the broker cryptographically asserted this"); integration into loan-origination
  systems (Blooma-style).

### 5.5 LLM agent / AI tool (the fastest-growing consumer — and openOM's tailwind)

- **Pain:** hallucination (§3.5); no ground truth; every agent re-reads the PDF; metadata can be
  faked.
- **openOM today:** the **MCP server** gives an agent deterministic `om_read`/`om_validate` — a
  verified, structured fact instead of a vision-parse guess; the process playbook keeps inference at
  the mapping edge only; egress-zero on-device option for privacy.
- **Still missing:** openOM as a **named RAG/grounding primitive** ("ground your CRE agent in
  openOM verified facts"); an agent-facing SDK / tool spec beyond MCP (function-calling schema for
  OpenAI/Anthropic tool use); a public "is this OM openOM-verified?" resolver so an agent can prefer
  verified sources. **This persona is where the AI-hallucination fear converts directly into
  openOM's value** — lean into it hard.

### 5.6 Cross-persona summary

The standard is **strong on the trust/provenance/verification axis** (nobody else has it) and
**strong on the at-source thesis** (validated by the 62% stat + the Factur-X precedent). It is
**weak on data depth** (§2.1 — headline facts only, not underwriting detail) and **weak on
distribution** (adoption depends on source tools + marketplaces embedding it, which isn't wired
yet). The winning sequence: **depth + partner-embed + identity/signature** — in that order of
leverage.

---

## Part 6 — Strategic improvement opportunities

_Beyond everything already built. Each is an opportunity, not a commitment; sized in Part 8._

### 6.1 Product / spec

- **O1 — Asset-class schema modules (highest leverage).** Extend the single-tenant core with a
  **rent roll** module, a **T-12 / operating-statement** module, and per-asset-class profiles
  (multifamily unit mix, multi-tenant lease abstracts, industrial, retail, hospitality, land).
  This converts openOM from "headline facts" to "fills the underwriting model" — the 80% of the pain
  (§2.1, §5.2). Ship as versioned, optional modules under the same core + JCS discipline.
- **O2 — RESO CRE Data-Dictionary alignment.** Map `om:` terms to the emerging RESO CRE fields;
  publish a crosswalk. Position openOM as the *transport + provenance* layer over RESO's *vocabulary*
  (§4.4). Rides an emerging authority instead of fragmenting further.
- **O3 — Excel / Google-Sheets last mile.** A `=OPENOM(...)` function + CSV/XLSX export of a payload
  (and rent roll / T-12). Analysts live in Excel (§2.8); meet them there.
- **O4 — Confidence & source per field, universally.** Generalize the rent `source: extracted|
  asserted` model to every field, plus optional per-field confidence from the extraction step — so
  consumers can filter to "asserted-only" for defensibility.

### 6.2 Trust / identity (the durable moat)

- **O5 — Real cryptographic signatures (L4).** Detached JWS/COSE over the canonical payload (and/or
  PAdES on the PDF), verifiable **offline, mirror-free**. This is the single biggest trust upgrade
  (§2.5) and unblocks lender non-repudiation (§5.4).
- **O6 — DNS/`.well-known` origin anchoring.** Bind a brokerage domain to a signing key via a DNS
  TXT / `.well-known/openom` record, so origin (L3) works without a per-deal same-domain mirror
  (§2.3) — the realistic path to L3 at scale.
- **O7 — Verifiable brokerage identity.** License-number format validation (deterministic, cheap) →
  optional liveness check against state DRE registries (a service) → DID/VC for brokerages (§2.4).
  Turns `assertedBy` from a claim into a credential.
- **O8 — Revocation / latest-state discovery.** A `.well-known` "latest / withdrawn / superseded"
  lookup so a consumer holding v1 can learn v2 exists or the deal was pulled (§2.6).

### 6.3 Distribution / ecosystem (the adoption unlock)

- **O9 — Source-tool embed partnerships (Buildout, Crexi Create).** Get OM-*generation* tools to
  emit openOM at creation time — the data already exists in their property record (§4.2). One
  integration populates the standard at the source overnight. **This is the #1 GTM lever.**
- **O10 — Marketplace integration (Crexi, LoopNet).** Ingest payloads on upload, host mirrors (→ L3
  for every listing), show a "verified data" badge (§4.3). Verified listings as a platform
  trust/fraud-reduction feature.
- **O11 — Multi-language verification libraries.** Tiny read-+-verify-+-badge ports in **Go, Java,
  C#** (and an Excel/VBA shim) so enterprise CRMs/underwriting stacks consume natively (§2.7).
- **O12 — Email/inbox ingestion.** "Forward the OM, get a payload" — OMs arrive by email; a
  forwarding address / Gmail add-in / Outlook add-in bridges the last mile (§2.8).
- **O13 — Firefox + Safari + a hosted web authoring tool.** Broaden the consumer/author surface
  beyond Chrome/Edge (§2 consumer surfaces).

### 6.4 AI positioning (the tailwind)

- **O14 — "openOM = the anti-hallucination grounding layer."** Explicit positioning + docs + an
  agent-facing tool spec (OpenAI/Anthropic function-calling schema alongside MCP) so "ground your
  CRE agent in openOM verified facts" is a one-liner (§3.5, §5.5). Convert the industry's
  hallucination fear directly into demand.
- **O15 — Public "is this OM verified?" resolver.** A hosted endpoint an agent/portal hits to prefer
  verified sources; also the natural home for revocation (O8) and telemetry (§2.12).

### 6.5 Standard governance (how a standard actually wins)

- **O16 — RFC-style normative spec + versioned governance** (working group, deprecation policy,
  1.0 milestone) — §2.11.
- **O17 — Conformance certification program.** Package the codes registry + vectors as a public
  test suite + a "openOM-conformant" badge third parties earn — the mechanism that yields
  independent implementations *without* forks (§2.11).
- **O18 — RESO / industry-body liaison.** Formalize the RESO CRE working-group relationship (O2);
  seek schema.org alignment. Credibility + distribution.

### 6.6 Monetization (keep the cardinal line: deterministic = free, inference/hosted = paid)

Free & open (MIT / CC-BY): the spec, deterministic core/CLI/js, MCP deterministic tools, extension,
conformance suite, a free public deterministic MCP. **Paid, and consistent with the boundary:**

- **M1 — Hosted inference-extraction service** (the already-planned paid product) — the **cold-start
  bridge**: until source tools embed openOM, this *produces* verified payloads from legacy OMs at
  scale. Freemium: verify free, extract-at-volume paid.
- **M2 — Hosted verification/identity/signing service** — brokerage key management, license
  verification, DNS anchoring, signing-as-a-service (O5–O7). The trust layer as a subscription.
- **M3 — Enterprise / marketplace features** — bulk processing, private registries, SLAs, audit
  exports, the distributed limiter/quota + API-key stack already built (§1.5) monetized.
- **M4 — Data-network products (later, carefully)** — anonymized/aggregate deal indices built from
  opted-in verified payloads. Powerful but governance-sensitive; only with explicit consent and
  neutral stewardship.

---

## Part 7 — Adoption barriers, risks & open questions

### 7.1 The cold-start / chicken-and-egg problem (the central risk)

Consumers won't build on openOM until OMs carry it; brokers won't embed until consumers value it.
Unlike Factur-X, **there is no mandate** to force the loop (§3.4). Mitigations:

- **Seed the supply side with the hosted extraction bridge (M1):** produce verified payloads from
  *existing* OMs so consumers get value on day one, before broker adoption. (This is why the paid
  extraction service is strategically load-bearing, not just revenue.)
- **Pull demand with the AI-grounding angle (O14):** agents/tools want verified facts *now* because
  of the hallucination fear — demand can lead supply.
- **Land one source-tool or marketplace partner (O9/O10):** a single Buildout/Crexi integration
  flips a large fraction of new OMs to openOM-enabled at once.

### 7.2 The broker-incentive problem (underappreciated)

Some brokers **prefer** friction — an opaque PDF makes buyers call them, and they control the
narrative on soft numbers (pro-forma, "market" rents). Machine-readable, comparable, verified data
can feel threatening. Counters: frame openOM as a **broker asset** — faster serious-buyer response,
fewer misquotes, a "verified" trust badge that wins listings, better marketplace ranking. But accept
that **the author is the hardest party to move**, which is exactly why source-tool embedding (O9)
that makes it *automatic and invisible* matters more than the author extension.

### 7.3 Incumbent capture

Crexi/CoStar could define a **closed** data format and capture the value. openOM's defense is being
**the neutral, open, already-built** alternative and moving fast on partnerships + RESO alignment
before an incumbent standard hardens. Neutral stewardship (Vervelio, not a marketplace) is a
feature here.

### 7.4 Trust bootstrapping is incomplete

L2 integrity only matters if consumers actually verify, and without signatures (L4) origin (L3) is
fragile and mirror-dependent (§2.3, §2.5). Until O5–O6 land, "verified" is weaker than it sounds —
prioritize signatures/DNS-anchoring to make the trust claim robust.

### 7.5 Liability & governance

"Assertions, not facts" is the right legal posture, but needs explicit framing: openOM proves *who
asserted what, unaltered, when* — **not** that the assertion is true. Data-network products (M4) and
identity services (O7) raise privacy/consent and accuracy-liability questions that need governance
before launch. OMs are confidential; making them machine-readable eases aggregation/scraping —
stewardship must address this.

### 7.6 Sustainability of the neutral steward

The open standard is funded by the paid services (M1–M3). Keep the cardinal line crisp
(deterministic = free forever; inference/hosted = paid) so the "open" promise stays credible while
the business funds it.

### 7.7 Open strategic questions (for the human to decide)

1. **Which asset class to deepen first?** (Multifamily has the highest deal volume and the most
   painful rent-roll/T-12 re-keying — likely the sharpest wedge. Net-lease is simplest and already
   modeled.)
2. **Where to embed — authoring (Buildout), distribution (Crexi), or stay consumer-first
   (extension)?** Authoring gives the cleanest at-source data; distribution gives origin-vouching +
   reach; consumer-first is what's built but is the slowest path to supply.
3. **Signatures vs mirrors for origin** — invest in O5/O6 now, or ride L2-integrity until a partner
   provides mirrors?
4. **Formal RESO alignment** — liaise/join the CRE working group, or stay independent and fast?
5. **Lead with anti-hallucination AI-grounding (O14) as the wedge narrative**, given that's where
   demand is hottest and openOM's differentiation is sharpest?

---

## Part 8 — Prioritized recommendation matrix

_Impact = leverage on adoption/differentiation. Effort = eng+partnership cost. Wave = suggested
sequence. This is a decision aid, not a plan; the open questions in §7.7 gate several choices._

> **⚑ Superseded in part (2026-08-21).** The §7.7 questions are now answered in the
> [decision memo](openOM-decision-memo.md). The matrix below is the **pre-decision** ranking; the
> **actual** priority order is the memo's revised sequence: **(1) O9 redirected — DealGround
> ingestion + the Buildout MCP OAuth pull; (2) O14 AI-grounding narrative.** O1 is dropped, O5/O6
> parked, O2 held. Read the rows for O1/O2/O5/O6 as *analysis only*, not the current plan.

| # | Opportunity | Impact | Effort | Type | Wave |
|---|-------------|:------:|:------:|------|:----:|
| O1 | Asset-class schema modules (rent roll, T-12, multifamily) | **High** | L | Product | **1** |
| O9 | Source-tool embed partnership (Buildout / Crexi Create) | **High** | M* | Distribution | **1** |
| O14 | "Anti-hallucination grounding layer" positioning + agent tool spec | **High** | S | AI / GTM | **1** |
| M1 | Hosted extraction bridge (cold-start supply) | **High** | M | Monetization | **1** |
| O3 | Excel / Sheets + CSV/XLSX last mile | Med | S | Product | **1** |
| O5 | Real cryptographic signatures (L4) | **High** | M | Trust | **2** |
| O6 | DNS / `.well-known` origin anchoring | **High** | M | Trust | **2** |
| O10 | Marketplace integration (Crexi / LoopNet mirrors + badge) | **High** | M* | Distribution | **2** |
| O2 | RESO CRE Data-Dictionary alignment + crosswalk | Med | M | Standard | **2** |
| O11 | Go / Java / C# verification libraries | Med | M | Ecosystem | **2** |
| O7 | Verifiable brokerage identity (license → DID/VC) | Med | L | Trust | **3** |
| O8/O15 | Revocation + public "is-verified?" resolver | Med | M | Trust/Infra | **3** |
| O12 | Email/inbox ingestion | Med | M | Distribution | **3** |
| O16/O17 | RFC spec + conformance certification program | Med | M | Governance | **3** |
| O4 | Per-field source+confidence everywhere | Med | S | Product | **3** |
| O13 | Firefox/Safari + hosted authoring | Low | M | Surface | **3** |
| M2/M3 | Hosted trust/identity + enterprise features | Med | L | Monetization | **3** |
| M4 | Aggregate data-network products | High‡ | L | Monetization | later |

\* Effort is mostly *partnership/BD*, not eng — the code side is largely done.
‡ High upside but governance/privacy-gated (§7.5); only with explicit consent.

### The north-star sequence (if forced to pick)

1. **Deepen the data (O1)** so openOM fills the underwriting model, not just the headline — this is
   what makes a consumer actually care.
2. **Embed at the source (O9)** via one authoring/marketplace partner — this is what populates the
   supply side at scale and breaks the cold start.
3. **Lead the narrative with anti-hallucination AI-grounding (O14)** — this is where demand is
   hottest and openOM's moat (deterministic + provenance) is sharpest, and it pulls both sides of
   the market.
4. **Harden trust with signatures + DNS anchoring (O5/O6)** so "verified" is robust and mirror-free
   — the durable moat once volume arrives.

Everything else compounds behind those four. The engineering foundation is unusually complete for
this stage (deterministic core, byte-parity dual impl, anti-fork oracle, trust model, MCP, hosted
infra, encryption, extension) — **the frontier is now data depth, at-source distribution, and the
trust/identity layer, not more core plumbing.**

---

_End of recon. Feature inventory (Part 1) reflects `main` as of 2026-08-19; market reads
(Parts 3–4) are point-in-time and sourced. Update the matrix (Part 8) as the open questions in
§7.7 are decided._
