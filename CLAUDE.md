# OpenOM - repo rules (auto-loaded)

> Claude Code reads this every session. It is the short, load-bearing contract for this repo.
> Full context lives in the handoff doc (`om-standard-handoff-*.md`) and `/spec`.

## What this repo is
An open (MIT) **standard + toolchain** that embeds a machine-readable, broker-asserted data
payload inside commercial-real-estate offering-memorandum PDFs (Factur-X mechanism), and exposes
the same payload as JSON-LD on the web. One extraction at the source, infinite cheap consumption
downstream. Published under **Vervelio** (neutral steward), not Fortis.

**The spec is the product; the tool is a commodity.** What compounds is the versioned schema,
validator, vocabulary, and governance - ship those with the code.

## The one rule that governs everything
**Deterministic core, inference at the edges.** The engine, MCP server, and consumer mode contain
**zero LLM/inference calls, ever** - no keys, no per-call cost, fully testable. LLM mapping runs
client-side or on-device (author mode / process layer only). Hosted inference extraction, if it
ever exists, is a separate commercial service - never the open server. If you find yourself adding
a model call to `/core`, `/mcp`, or consumer-mode `/js`, stop - you're in the wrong layer.

## 🚨 HARD ENFORCEMENT RULES

**These are not suggestions. Violations block progress.**

### Rule 1: Production Standard Only
- This is a **published standard + sellable tool**, not a learning project. Senior production
  engineer perspective only. Zero deferrals, zero tolerated tech debt.
- A shipped spec is forever - a bad field name or a silent round-trip bug outlives every excuse.
  Get the spec and the PDF mechanics right before anything cosmetic.

### Rule 2: The spec and process layer ARE product - commit them; planning docs are not
- `/spec` (JSON Schema, sample payloads, `@context`, changelog) and `/process` (`SKILL.md`,
  agent instructions) are **first-class product - always committed.**
- Design specs, brainstorms, and plans → `docs/superpowers/` and `.planning/` (git-ignored).
- The root handoff doc (`om-standard-handoff-*.md`) and `CLAUDE.md` are committed.
- `git status` before every commit; never stage planning scratch or the `.htm` marketing mock.

### Rule 3: Workflow Discipline - SKILLS BEFORE CODE
- Before any implementation, invoke the appropriate superpowers skill:
  - `superpowers:brainstorming` - design, architecture, planning
  - `superpowers:writing-plans` - multi-step tasks
  - `superpowers:systematic-debugging` - bugs
  - `superpowers:verification-before-completion` - before claiming work is done
- No flow-driven chaos. No random refactoring. No scope creep.
- **Plans = pseudocode, never full code.** Interfaces, algorithm-in-prose, exact file paths +
  verification commands - NOT complete implementations. This OVERRIDES the writing-plans skill's
  "show full code" instruction. Execute from the plan; never rewrite an over-coded one.

### Rule 4: Code Quality (Non-Negotiable)
- **Python core:** type-hinted throughout, `mypy`-clean, `ruff`-clean. Deterministic, pure functions
  where possible. Libraries: pikepdf, PyMuPDF, jsonschema, typer, FastMCP. No LLM deps in `/core`.
- **TS subset (`/js`):** strict TypeScript, no `any` unless unavoidable. Libraries: pdf-lib, ajv,
  pdf.js. Powers the extension and web/Node consumers.
- **No legacy patterns.** Replace with the best modern solution, even outside the current task.
- **Compact tool outputs.** MCP tools paginate text and return image manifests + links - never
  dump raw bytes into context.

### Rule 5: Testing - real fixtures, no mocks
- OpenOM is a deterministic library: **tests against real OM PDFs ARE the proof**, not mocks.
- **`/fixtures`** holds 10–15 real OMs across producers (InDesign, Word-to-PDF, Buildout, scans) -
  producer diversity is where PDF tooling breaks. Fixtures land **before** extraction logic.
- **Named, non-negotiable tests:** (a) round-trip embed→read on native/hybrid/scanned OMs;
  (b) idempotent re-embed with `supersedes` hash (never stacks); (c) non-destructive embed
  (visually identical, bookmarks/links preserved); (d) survival through download/re-upload;
  (e) **cross-implementation round-trip** - pdf-lib output readable by pikepdf and vice versa,
  byte-for-byte payload fidelity. This last one silently kills standards; it exists from day one.
- No mocked inference, no happy-path-only. Attack messy rent schedules, CMYK/SMask images,
  flattened scans, empty payloads, hash mismatches.

### Rule 6: Spec & payload integrity
- **Assertions, not facts.** Every payload is an identified party's opinion as of a date:
  `assertedBy` + `assertedDate` required; `noiType` (in-place|pro-forma) + `noiAsOfDate` required.
- **Never invent facts.** Tooling checks internal consistency (NOI÷price vs cap rate, schedule
  sums, date/term math) - never market truth. Warnings never block; schema errors always block.
- **Every payload change bumps `assertedDate`.** Re-embed replaces (never stacks) and records
  `supersedes` = prior payload hash.
- **Never modify visual content** without an explicit flag. The output PDF looks identical.
- Payloads SHOULD be human-reviewed before embed (the extension review panel is the assertion gate).

### Rule 7: Hard rules that never bend
- No inference in the open server or consumer mode - ever.
- No chat-UI puppeteering: never inject into or scrape logged-in ChatGPT/Claude sessions
  (ToS, fragility, account risk). Use MCP connectors / on-device / hosted paths instead.
- Detection re-fetches PDF bytes; it never scrapes the browser's PDF viewer internals.
- Rehost the embedded file itself - never re-export (re-export destroys the attachment).

### Rule 8: Commit Discipline
- Small, conventional commits (`feat:`, `fix:`, `chore:`, `refactor:`, `spec:`).
- Message explains **WHY**, not what.
- **Commit and push ONLY when the user asks.** Do not add Co-Authored-By trailers.

### Rule 9: When in Doubt, Ask
- Do not guess or rationalize. Clarify with the user before proceeding.

---

## Structure (target repo layout - non-negotiable boundaries)
Monorepo, one repo, layered so surfaces attach at boundaries without touching the deterministic core.

- `/core` - Python lib. Deterministic PDF/data verbs (embed, read, inspect, extract, validate).
  Zero LLM deps. The heart of the standard.
- `/cli` - `om` command / watch-folder over `/core`. Zero UI. Also the server-side path.
- `/mcp` - thin FastMCP wrapper, dual transport (stdio + hosted Streamable HTTP). Deterministic.
- `/spec` - JSON Schema 0.1, sample payloads, `@context` / vocabulary, webhook envelope, changelog.
  **The product.**
- `/process` - `SKILL.md` (Claude) + generic agent-instructions (all other clients). The
  extraction/mapping playbook. No code.
- `/js` - TS subset: embed/read/validate. Powers the extension + web/Node consumers. npm package.
- `/extension` - MV3 Chrome extension, two personas: consumer mode (detect/view/verify/publish,
  ships first) + author mode (capture/review/embed, ships second).
- `/fixtures` - real OMs across producers. Committed (or LFS/pointer if large).

**Cardinal boundary:** `/core`, `/mcp`, and consumer-mode `/js` never import an inference client.

## MCP tool surface (all deterministic)
`om_inspect` · `om_extract_text` · `om_extract_images` · `om_read` · `om_validate` · `om_embed`.
Two-tier validation: schema errors block; consistency warnings never block; market truth is out of
scope forever.

## Current state (2026-08)
**M1 + M1.x shipped and at peak** (2026-08-17), on `main`. Built: `/core` (embed/read/inspect/
extract/text/validate), `/cli` (`om embed/read/inspect/validate/check/extract/conformance`),
`/mcp` (stdio, six deterministic tools), `/js` (embed/read/validate/consistency at byte-parity
with Python), `/spec` (schema 0.1, samples, vectors, `@context`, changelog), and the seeded-defect
gate (`fixtures/seeded_defects` + `core/tests/test_consistency.py`). The cross-impl anti-fork
oracle runs in CI (now manual, `workflow_dispatch`).

**Name locked (Q1):** **openOM**, published by **Vervelio Labs**; namespace
`https://verveliolabs.com/openom/...`. GitHub slug stays `sarthaknimbalkar/OpenOM`.

**Free/paid boundary locked (Q2, 2026-08-17 - handoff §15.1):** everything deterministic +
self-hostable is free MIT (spec CC-BY-4.0); the sole paid product is Vervelio-hosted **inference
extraction**, a service **separate** from the open server, **built in M3**; Vervelio also runs a
free public deterministic MCP. The cardinal rule is unchanged - no inference in `/core`, `/mcp`,
or consumer `/js`, ever.

**M3 gate [OM-DoD-004] met** (2026-08-17, deterministic-only scope). Built in `/mcp`: hosted
Streamable HTTP transport (`build_http_app`/`main_http`), SSRF-hardened `url` fetch
(`fetch.py`, resolve-then-pin), R2/local blob store (`blobstore.py` - ≤24h TTL, delete-on-completion,
server-bound owner), per-principal rate limit, HTTP transport security (Host/Origin), untrusted-PDF
parse isolation (`guard.py` - killable subprocess, timeout→OM-IO-003 / crash→OM-IO-010), and a
per-call page ceiling. The paid inference-extraction service is a **seam only** (`extraction.py`);
zero inference in `/mcp` (enforced by the `boundary` CI job + `test_boundary.py`). Q4 resolved
(≤24h TTL + delete-on-completion). Hardening backlog: #51/#52 (distributed limiter, API-key
lifecycle) are **hosted-deploy-gated**; the CLI/image items #16/#17/#18 are separate.

**M4 gate [OM-DoD-005] met** (2026-08-17). `/process` extraction playbook shipped: `mapping-guide.md`
(shared field/vocabulary/consistency substance) + `SKILL.md` (Claude-invocable `openom-author`) +
`agent-instructions.md` (any MCP client), driving `om_inspect→extract→map→om_validate→review→om_embed`
with `source: extracted` until the human review gate. Inference lives only in the agent's mapping
step; every `om_*` tool stays deterministic. Committed demo (`process/example/`: synthetic OM +
produced payload + transcript) is gated by `spec/tests/test_process_example.py` (zero errors +
warning-clean). The live non-Claude client run is adoption-deferred.

**M5a gate [OM-DoD-006] met** (2026-08-17). Consumer extension shipped in two sub-projects.
**A** (`/js` trust core): `verifyOrigin` (§10.1 domain-origin), `badgeState`/`honestLabel`/FORBIDDEN
(§AA precedence + UI-honesty), `buildEnvelope`/`signHeaders`/`assertSafeWebhookTarget` (§Y HMAC +
SSRF host-guard), all byte-parity with Python. **B** (`/extension`, MV3 Chrome consumer): service
worker runs detect (re-fetch bytes, never the viewer) → read → validate → verifyOrigin → stale →
badge; popup card with source tags + residual warnings + OMW-W051 stale notice; named-webhook
publish (test-fire/copy/download). The read path is **worker-free** (pdf-lib + zlib/DecompressionStream,
pdf.js only as an encrypted fallback) and the schema validator is **eval-free** (ajv standalone
codegen) - both forced by the MV3 CSP and proven by a real-browser Playwright gate (7/7 §AA states +
publish HMAC over a self-signed HTTPS harness). `assert-no-inference` over `extension/dist` keeps the
consumer bundle inference-free (cardinal rule holds).

**M5b gate [OM-DoD-007] met** (2026-08-17). Author mode shipped in two sub-projects, extending the
`/extension` shell. **B1 (deterministic):** side-panel capture (re-fetch/file) → review panel
rendering `process/review-contract.md` (per-field value+evidence, omissions, residual warnings,
reprice diff) → explicit human assert (stamps `assertedBy`/`assertedDate`, promotes rent
`source: extracted→asserted`, `meta.supersedes` on reprice) → embed via `/js` → blob-download. **B2
(on-device extraction):** an `Extractor` seam isolates inference to one adapter - the browser Prompt
API (`LanguageModel`/`window.ai`, a global, not an npm dep) - that pre-fills the draft with evidence
(`source: extracted`); text comes from a worker-agnostic pdf.js pass (`js/src/text.ts`); the hosted
path is a throwing seam (§15 Q2); the review panel stays the human assertion gate (confidence is
never consent). Proven by the live author gate (12/12 Playwright): fresh/gated/reprice embed +
**[OM-PRIV-001] egress-zero** (0 off-device requests during extraction, via an injected fake
`LanguageModel` exercising the real adapter - the real Gemini Nano can't run in CI, stated not faked).
The gate also caught + fixed a latent `/js` non-idempotent re-embed bug (cross-impl parity restored).

**M5 driven to peak** (2026-08-18). A full audit → issue → fix sweep across all four M5 parts +
shared shell: **39 of 41 peak issues (#63–#103) resolved**, each TDD'd (js 211 · ext 91 unit ·
live gate 19/19 incl. 3 axe a11y audits + a real-page link-badging test · cross-impl 6/6 ·
inference-free throughout). Highlights: §Y made two-sided + SSRF-encoding-proof (`verifyWebhookSignature`,
constant-time compare); on-device extraction made trustworthy (human-only-field guard, prompt-injection
fence) AND usable on real OMs (context chunking, table-aware text); the raw-JSON author editor replaced
by a schema-driven form (+ noiType/noiAsOfDate gate controls + finalized preview); a full design system
+ WCAG-AA a11y (axe-gated); an options page + opt-in proactive detection + per-domain link-badging
content script; popup bundle 664KB→14KB. Latent bugs fixed along the way: `setField` array corruption,
UTC assertedDate, non-idempotent JS re-embed, per-tab badge, PSL private-suffix origin cross-vouch, an
Assert blur-race. **#74** (chrome.downloads interception) **deferred by decision** (adds only a trigger;
not worth the broad `downloads` permission). **#75** (real Prompt-API hand-verify) **environment-blocked**
(needs a machine with Gemini Nano running). See GitHub #63–#103.

**Real-OM evidence (2026-08-18).** Against a **1330-OM corpus across ~60 producers** (Adobe/InDesign,
Acrobat, iText, Prince, Word/Publisher/PowerPoint, Buildout.com, Ghostscript, Quartz/macOS, scanned/
RICOH - local, gitignored `OMs/`): the extension's `/js` embed is **non-destructive on 1203/1331**
(zero structural change on any producer) and **pixel-identical** (ssim 1, maxdiff 0) on a
one-per-producer visual spot-check - so [OM-DoD-001] non-destructiveness holds across real producers,
and the M1/M5b real-OM outcome bars are met with evidence. The only failure mode is **encryption**
(128, ~10%): pd-lib can't load encrypted PDFs so the *browser* refuses them gracefully (#107, points
to the CLI), but the **Python core embeds them** (hash-valid round-trip) - so the standard covers 100%.
Harness: `node js/scripts/real-om-fast.mjs`. A committed synthetic non-destructive test (#105) guards
this in CI without the private corpus. #14 (envelope schema+validator) shipped.

**In-browser encrypted-embed shipped (#4, 2026-08-18).** Author mode now decrypts empty-user-password
AES OMs (permission encryption - restrict print/copy - NOT password-protected) in-browser, then embeds
into the plaintext. New deterministic `js/src/decrypt.ts` (`decryptPdf(bytes)→Uint8Array|null`): reads
`/Encrypt` via pdf-lib, derives the file key with `@noble/hashes` (MD5 R4 / SHA-2 "Algorithm 2.B" R6),
AES-CBC via `@noble/ciphers` (the one new light dep), validates the empty user password against `/U`
(RC4 for R4, SHA-2 for R6) BEFORE decrypting, and a PKCS#7 failure aborts to `null` - a wrong key can
never emit a corrupt OM. Handles the real-world structure: compressed **object streams** + xref streams
(pdf-lib dissolves an encrypted ObjStm at load, so containers are located by a safe raw scan - ObjStm
dicts are plaintext - decrypted, and reparsed via `PDFObjectStreamParser`). Scope is empty-password AES
only (V4/R4 + V5/R6); RC4 / real passwords / out-of-scope → `null` → the #107 CLI-refuse. `captureFromBytes`
decrypts-then-authors (`wasDecrypted`), the panel shows an unencrypted-output notice. **Proven by the
pikepdf render oracle over the real corpus: 102 R4 + 23 R6 = 125/125 in-scope encrypted OMs decrypt
render-identical (ssim 1, maxdiff 0)**; CI-gated by synthetic AES-128/256 fixtures WITH object streams
(`js/test/decrypt.test.ts`) + the live author gate (`author/encrypted.pdf`, 9/9); bundle stays inference-free.

**Next: adoption / GA hardening** - the truly-incremental byte-preserving save ([OM-EMB-020], YAGNI given
the load→save evidence - matters only for signed OMs), Web-Store submission (packaging shipped, #104),
and the hosted inference-extraction service (the sole paid product, a separate Vervelio build).
M2/M3/M4/M5a/M5b all shipped; M5 at peak; embed proven on real OMs across producers; encrypted OMs now
covered in-browser as well as via the CLI (100% corpus coverage from either surface).
