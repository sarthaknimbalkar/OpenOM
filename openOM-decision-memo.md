# openOM — Decision Memo (Response to Recon, §7.7)

> Responding to the strategic questions raised in the recon doc (Part 7.7, Part 8). This is a
> decision record, not a new recon — it captures where we're landing and why, including one new
> distribution mechanism (Buildout MCP ingestion) not covered in the original recon.

_Decisions dated 2026-08-21. Supersedes the recon's Part 8 north-star sequence where they conflict._

---

## 0. Core philosophy (confirmed, sharpened)

An OM is **not** a source of truth. It is **an advertisement** — a broker's **opinion of value**,
which the **seller has agreed to before the OM/listing is created**. Keyword: *opinion*. The
objective is: ingest once, make the payload faithfully reflect what the PDF asserted, and leave
reconciliation to the parties who actually do it — brokers and underwriters working from
broker-of-record files (mortgage, lease, etc.) at deal-desk stage.

The recon's "assertions, not facts" trust model already matches this. No change needed to the
spec's posture — just keep stating it explicitly wherever the product is described, so "verified"
is never mistaken for "true." **Verified means: this is the broker's asserted opinion, unaltered,
by whom, as of when — not that the number is correct.**

---

## 1. Schema depth / underwriting data (recon's O1)

**Recon recommended:** deepen the schema with rent-roll, T-12, multifamily, and debt modules as
the top-priority, highest-leverage investment — "this is what makes a consumer actually care."

**Decision: deprioritize.** Underwriting only happens once a deal desk has the file — nobody
underwrites off OM data pre-LOI. Credit profiles change, and real underwriting is triggered by the
deal desk receiving broker-of-record materials, not by anything captured at OM stage. Building deep
underwriting schema solves a problem that doesn't occur at the point openOM actually operates.

---

## 2. Asset class focus

**Recon considered:** multifamily as the "sharpest wedge" given deal volume and re-keying pain.

**Decision:** stay **investment-property focused**. For multifamily, ship only the lowest
common-denominator fields — don't chase schema depth here either. This asset class inherently
requires buyers to inspect, visit, and run real due diligence regardless of what the OM says, so
thin data isn't a defect to engineer around.

Thin/uneven data is treated as a **feature, not a gap**: it lets listings with genuinely better
data rise to the top on their own. Multifamily sellers who want attention will have to improve
their own documentation — the standard doesn't need to compensate for that by building more schema.

---

## 3. Where to embed (recon's O9)

**Recon proposed:** Buildout or Crexi Create as the source-tool embed partner.

**Decision: redirect to where the data actually lives and where teams actually work.**

- **DealGround** — already parsing and collecting OM data; a natural ingestion partner rather than
  a cold-start build.
- **Meet brokerage teams at their actual authoring point**, not a fixed platform assumption. Many
  shops (e.g., Marcus & Millichap) use Buildout as the base but modify downstream — the work
  product of record isn't always the platform export. Target wherever the generating team actually
  finalizes the file.

### 3.1 NEW: Buildout MCP connector as an ingestion path

A Buildout.com MCP server already exists (OAuth connector, built and working). This should be
brought into the openOM product as a **first-class ingestion path**:

- Instead of relying on OCR / blind text-extraction from a flattened OM PDF, the parser can connect
  directly to a user's own **Buildout data** via the MCP OAuth connector and pull structured fields
  at the source — property, deal, lease, rent schedule — before the OM is ever flattened to PDF.
- This slots cleanly under the deterministic-core / inference-at-the-edges rule: the MCP connector
  is a **data-fetch, not an inference step**. It's a cleaner "author mode" input path than the
  current on-device extraction (Gemini Nano) fallback used for scanned/undocumented OMs — those
  remain useful, but they become the *fallback*, not the primary path, when Buildout data is
  available.
- Net effect on the cold-start problem (§7.1 in the recon): this gives supply-side seeding a second
  lever beyond the hosted extraction bridge (M1) — for any user with Buildout access, ingestion
  doesn't require touching the PDF at all. It's arguably a stronger wedge than the M1 hosted
  extraction bridge, since it produces higher-fidelity payloads with zero OCR risk.
- Practically, this also reframes the "where to embed" question: rather than needing a formal
  Buildout *partnership*, this is a **user-authorized OAuth pull** — no BD dependency, just product
  work to wire the connector into the parser's input selection (Buildout MCP vs. PDF/OCR).

### 3.2 Architecture notes & open questions (pre-design — NOT yet decided, NOT built)

_Recorded from a walk of the current code so the eventual design pass starts grounded. These are
understanding + open forks, not commitments._

**How it fits the existing code.** Author mode already has a clean extraction seam,
`extension/src/author/extract/` (`Extractor` interface + three adapters: on-device Prompt API,
hosted-stub, test-double; chosen by `pickExtractor`). Two structural facts matter:

- **A Buildout pull is NOT a drop-in `Extractor`.** That interface is
  `extract(pages: PageText[]) → fields` — a *text → fields inference* over PDF page text. A Buildout
  pull takes **no PDF text**; it fetches structured records directly. So it belongs as a new **input
  source *above* the seam** — a source selector ("Buildout structured pull" vs. "PDF text →
  extractor") that emits the same `ExtractionResult` shape **deterministically**. This is precisely
  what puts it on the deterministic side of the cardinal rule and demotes Gemini-Nano to *fallback*.
- **The human review gate still applies.** A Buildout pull is still a **draft** the human asserts —
  higher-fidelity input, not auto-assertion. Consistent with §0 (opinion of value, seller-agreed).

**Open questions the design pass must resolve (need your input):**

1. **Where does the OAuth/MCP pull actually run?** An MV3 browser extension doing an OAuth MCP
   handshake is architecturally awkward — MCP clients are normally Node / CLI / hosted, not a
   browser sandbox. Candidate homes, each a materially different build:
   - (a) extension author mode calls out to a small **hosted "author service"** that holds the
     Buildout MCP client + token;
   - (b) the **CLI / watch path** becomes the primary Buildout ingestion surface (fits the existing
     `om watch` server-side story);
   - (c) a local **Node companion** the extension talks to.
2. **What does the Buildout MCP expose?** Need the tool/resource shapes (property, deal, lease, rent
   schedule) to write the Buildout → openOM field map.
3. **Mapping ownership.** The Buildout → openOM field map is **deterministic** and should live in a
   drift-lockable mapping module (structural map — analogous to `process/mapping-guide.md` but code,
   not a prompt).
4. **Provenance labeling.** Is Buildout-sourced data `source: "extracted"`, `"asserted"`, or a new
   `"connected"`/`"imported"` provenance? It's the broker's own pre-flatten data (stronger than
   OCR), but the human still gates the assertion — so the label needs a deliberate choice.
5. **Token custody.** The extension already has an AES-GCM secret-store; a hosted/CLI home would
   need its own token handling.

### 3.3 Resolved defaults (2026-08-21 — decided by analysis; adopt unless overridden)

Of the §3.2 open questions, these are settled with sound engineering defaults so only the truly
external fact (Q2) blocks the build:

- **Q1 (where it runs) → DEFAULT: extension author mode**, matching the stated intent ("during the
  creation process read the buildout connection"). *Contingent on transport:* if the Buildout MCP is
  HTTP / OAuth-web-flow it lives in the extension (`chrome.identity`); if stdio-only it falls back to
  a Node/CLI companion. The `StructuredConnector` interface is transport-agnostic, so code isn't
  blocked either way. **Reversible once the transport (part of Q2) is known.**
- **Q3 (mapping ownership) → DONE.** The deterministic map is `partialPayloadToFields`
  (`extension/src/author/extract/source.ts`) — a pure, drift-lockable module, not a prompt.
- **Q4 (provenance label) → DECIDED: reuse `source: "extracted"`**, promoted to `"asserted"` at the
  review gate — the SAME path as the on-device extractor. No new enum value, so **no spec change**
  (stays thin). A connector pull is a higher-fidelity draft, but still a draft the human asserts.
- **Q5 (token custody) → DECIDED: defer to the Buildout MCP's own OAuth.** openOM consumes the
  authenticated MCP client and does not re-implement token storage (in-extension: `chrome.identity`;
  Node/CLI: the MCP client's own store).

**Still needs you — the ONLY remaining external input: Q2** — your Buildout MCP's actual
tools/resources, their field shapes, and its transport (HTTP vs stdio). Everything else is decided
and the generic seam is built (25c3749); the concrete connector is then a thin adapter that
normalizes your API into a partial openOM payload.

---

## 4. Signing / trust layer (recon's O5/O6)

**Recon recommended:** invest in real cryptographic signatures + DNS/`.well-known` origin
anchoring as a high-impact Wave 2 trust upgrade.

**Decision:** keep **casual (L2 integrity-only) signing**. No further investment in expanding the
trust layer at this time — revisit later if the space develops in a way that makes it worth it.

---

## 5. RESO alignment (recon's O2)

**Recon considered:** joining/liaising with the RESO CRE working group.

**Decision: hold.** RESO's goals differ from openOM's. Stay independent for now; open to
conversation only if RESO initiates interest.

---

## 6. GTM narrative (recon's O14)

**Decision: confirmed.** Anti-hallucination / AI-grounding stays the lead framing — this is where
demand is hottest and where openOM's deterministic + provenance model is sharpest relative to
general-purpose extraction tools. Ground it explicitly in the §0 posture: OMs are advertisements /
broker opinions of value, so the right grounding claim is *"the broker asserted this opinion,
unaltered, as of this date,"* never *"this is true."*

---

## 7. Net sequence vs. the recon's Part 8 north star

The recon's proposed order was **O1 (schema depth) → O9 (embed partner) → O14 (AI-grounding
narrative) → O5/O6 (signatures/DNS)**.

Revised sequence:

1. **O9, redirected** — DealGround integration + Buildout MCP connector as a direct ingestion path,
   plus meeting authoring teams where their real work product lives (not a fixed Buildout/Crexi BD
   partnership).
2. **O14** — anti-hallucination/grounding stays the GTM lead, unchanged.
3. Schema stays thin, common-denominator, investment-property-first across asset classes —
   explicitly **not** the deep T-12/multifamily buildout the recon proposed as top priority.
4. Trust layer (signing, RESO) — parked. Casual signing only; revisit if the landscape shifts.

This drops what the recon called the highest-leverage technical investment (O1) entirely, and
replaces both named embed partners with a mechanism (Buildout MCP OAuth pull) that requires no BD
dependency — just product integration work.

---

## 8. Domain: openom.app (2026-08-21)

`openom.app` has been acquired. Decision: **use it as the site / front-door only — do NOT migrate the
canonical namespace.**

- **Canonical machine namespace stays `https://verveliolabs.com/openom/...`** — the schema `$id`, the
  JSON-LD `@context`, and every payload's `@context` are pinned there and remain unchanged. This
  deliberately avoids regenerating the anti-fork keystone (all expected hashes + golden PDFs) and
  keeps the CLAUDE.md-locked namespace intact.
- **`openom.app` is the human front-door**: the docs site, the verify tool, marketing, and the
  eventual hosted deterministic MCP. Serve the same `site/` tree there (in addition to
  verveliolabs.com), with `verveliolabs.com/openom/*` remaining the authoritative host where the
  namespace URLs resolve.
- **No repo/spec churn**: only the deploy target + docs framing change (see
  `.github/workflows/deploy-site.yml`). Operationally: point GoDaddy DNS for openom.app at the
  Cloudflare Pages project and attach both custom domains.
- Revisit a full namespace migration to openom.app only if/when it's worth a versioned, breaking
  change (best decided before wide adoption; for now the split is intentional).

### 8.1 Update (2026-08-21) — superseded: migrated to openom.app

The §8 "site-only, keep namespace at verveliolabs.com" decision was **reversed** once domain
ownership was confirmed: the owner holds both `verveliolabs.com` (the company domain, with its own
email/site) and `openom.app` (fresh, dedicated). Contorting the company apex to also serve
`/openom/*` was the wrong shape. So the canonical namespace was **migrated to openom.app**: schema
`$id`, JSON-LD `@context`, and the XMP marker namespace now anchor at `https://openom.app/...`
(the `/openom/` path prefix was kept for a minimal change). Vectors + golden PDFs were regenerated
and both implementations re-verified byte-identical. Deploy attaches **openom.app only**;
verveliolabs.com is untouched. See DEPLOY.md.
