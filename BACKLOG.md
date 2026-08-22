# openOM — Product Backlog

Source: broker/author-persona product-gap audit (2026-08-22), grounded in the actual repo code
(one auditor per journey stage: onboarding, capture, extraction, review, embed, publish, bulk,
trust/verify). Every item cites `file:line` evidence. Deterministic-core / assertions-not-facts /
no-inference-in-core are intentional constraints, **not** backlog items.

Legend — **Severity:** 🔴 Blocker (broker can't finish the job) · 🟠 Major (finishes, but misled or
costly) · ⚪ Polish. **Status:** `todo` unless noted.

---

## 🔴 Blockers

### B1 — No way for a non-technical broker to get the tool / no zero-install embed path
- **Severity:** 🔴 Blocker · **Status:** AT PEAK (buildable parts) — hosted zero-install authoring
  companion at `/embed/` (`js/widget/openom-author.ts` + `js/src/{fields,author}.ts`, single-sourced
  with the extension). Peak: **encrypted-OM decrypt in-browser** (shared `captureFromBytes`), **human
  recap + finalized-JSON preview**, tampered-prior & decrypted notices, **WCAG-AA axe-clean**, and a
  **committed Playwright gate** (`extension/test/embed-companion.spec.ts` + `playwright.site.config.ts`,
  5/5: round-trip+reprice, encrypted, a11y, /verify URL ok+fail). Broken `pip/npm install` copy replaced
  with the honest from-source path (PyPI/npm are 404). **Owner-gated remainder:** Web Store listing,
  PyPI/npm publish, GitHub Release `.zip`.
- **Evidence:** extension "no-toolchain" path `spec/scripts/gen_docs.py:283-287` has no link; only real
  install is `README.md:92-101` (`npm install` → `npm run build` → load-unpacked). No Web Store listing,
  no downloadable `.zip` (`STORE-LISTING.md` is a draft). CLI path opens `pip install openom-core openom-cli`
  (`README.md:22`, `gen_docs.py:289`) — PyPI publish **unverified**; in-repo uses `pip install -e`,
  Status "Pre-1.0" (`README.md:132`). Only zero-install surface `/verify/` (`gen_docs.py:481-497`) is
  read/verify only. Hero routes to `quickstart-broker` (`gen_site.py:285-287,322`) which dead-ends.
- **Gap:** The funnel dies at step zero — both documented broker paths need dev tooling the persona lacks.
- **Fix:** (1) Submit to Chrome Web Store + link from hero/quickstart/README; interim, attach a prebuilt
  `openom-extension-<ver>.zip` to a GitHub Release with 3-step load-unpacked instructions. (2) Verify
  `openom-core`/`openom-cli` are actually on PyPI at the referenced versions, or switch copy to the `-e`
  form until they are. (3) **Ship a hosted client-side authoring companion on `/verify/`** (drop OM →
  schema form → assert → download embedded PDF, bytes never leave the browser) reusing `/js` `embedPayload`.

### B2 — Distribution stage does not exist; manual rehost silently destroys the payload
- **Severity:** 🔴 Blocker · **Status:** AT PEAK — "upload the exact file, don't let the portal
  re-export it" guidance on `/embed/` + broker quick-start; paste-a-URL post-rehost verify on `/verify/`
  (re-fetch + read/verify, honest CORS fallback to download-and-drop or the extension). **The shareable
  verified-view link shipped backend-free** as `/v/?src=<url>` (badge + deal card + download, client-side)
  with a copy-link helper in the companion — see M3. **Committed gates** cover the `/verify` URL box and
  the `/v/` page. (Portal write-back / an `om publish` verb remains a future enhancement, not a gap in
  the broker's path — the broker rehosts and shares the `/v/` link.)
- **Evidence:** after embed the broker gets a browser download only — `assert.ts:87-95`
  (`createObjectURL` + `a.click()`), ending "Embedded - downloaded the OM." (`panel.ts:347-349`). No
  `om publish`/rehost verb in `cli/main.py`. Buildout connector is read-only (`buildout-http.ts` pulls,
  never writes back). `CLAUDE.md` Rule 7 warns "re-export destroys the attachment," yet there is **no
  post-rehost verify loop**; `quickstart-broker` ends at "assert and embed."
- **Gap:** "Extract once, consume downstream" stalls exactly where the file must reach buyers; portals
  re-render on ingest and strip the attachment, and the file looks identical so the broker ships blind.
- **Fix:** (1) Add a closing quickstart step: "Replace the OM with the downloaded `.openom.pdf`; upload it
  as-is — do not let your portal re-export/flatten it." (2) Ship a post-rehost verify step: broker pastes
  the live listing URL, tool re-fetches bytes and confirms the payload survived, warning loudly if not.
  (3) Longer term: a real write path (`om publish` / one-click rehost) or a hosted `openom.app/d/<id>`
  shareable verified link.

### B3 — Back-catalog seed (stated #1 bottleneck) can't pull from Buildout; requires hand-wrangling JSON
- **Severity:** 🔴 Blocker · **Status:** AT PEAK — new `om buildout-pull` (`cli/.../buildout_pull.py`):
  authenticates to a Buildout MCP endpoint and fetches each listing JSON + downloads its OM PDF in one
  pass. Peak: **`--search` whole-catalog enumeration**, **`--skip-existing` resume**, **`--jobs`
  concurrency (order-preserving)**, **`--report`** + per-status counts — parity with `embed-batch`. Pure
  orchestrator, search-result parser, and MCP JSON/SSE parser all unit-tested with fakes; the live
  endpoint call is env-gated (needs a real endpoint + token, stated not faked, like #75).
- **Evidence:** `buildout_manifest` (`cli/src/openom_cli/main.py:316-370`) requires `--listings-dir` of
  pre-fetched `<id>.json` + `--pdf-dir` of `<id>.pdf`. Grep of `cli/` for fetch/httpx/token/get_listing →
  **no HTTP client**. Entirely CLI + hand-authored JSON (`main.py:62-64`), JSON in / JSON summary out.
- **Gap:** Broker must by hand extract one JSON per listing and download every PDF, renamed by numeric id;
  a brokerage admin/marketer can't do it — needs a developer.
- **Fix:** Ship `om buildout-pull` that authenticates to the Buildout MCP/API (token in env/config),
  enumerates the brokerage's listings, and writes both the `get_listing` JSON and the OM PDF named by id.
  Wrap the whole path (pull → map → review-report → embed) in one command with sane defaults, or a
  drag-a-folder GUI/hosted job.

---

## 🟠 Major friction

### M1 — Embed silently invalidates digitally-signed OMs and strips owner DRM
- **Severity:** 🟠 Major · **Status:** AT PEAK — deterministic `pdfHasSignature` (`js/src/signature.ts`,
  unit-tested) surfaces `Capture.signed`; both author surfaces now **warn + require an explicit
  acknowledgement before Assert** (companion gate + extension panel), gated by committed tests (site
  gate `[M1]` + headed author gate `[M1]`). DRM/decrypt already carried an unencrypted-output notice.
  NB: preserving a signature needs the incremental byte-preserving save [OM-EMB-020] (separate item);
  the CLI remains the documented path when a signature must survive.
- **Evidence:** `js/src/embed.ts:24-26` uses pdf-lib load→save (not incremental), rewriting the xref so any
  `/Sig` byte-range breaks; `assert.ts:49-60` and `panel.ts:117-138` never inspect for a signature.
  `capture.ts:47-56` replaces bytes with a decrypted copy; published copy drops print/copy restrictions
  with only a passive one-line notice (`panel.ts:148-156`).
- **Gap:** Broker publishes a signed-looking OM whose signature now fails in Acrobat (a liability), or
  silently drops the owner's DRM.
- **Fix:** Detect `/Sig` (or `/Perms /DocMDP`) at capture and warn/refuse before Assert; prioritize the
  incremental byte-preserving save `[OM-EMB-020]` for the signed case rather than deferring as YAGNI. Make
  the DRM-strip an explicit acknowledged checkbox; document the CLI when restrictions must be preserved.

### M2 — "Origin-verified" (strongest badge) is unreachable; public surfaces never show staleness
- **Severity:** 🟠 Major · **Status:** AT PEAK — **mirror emitter**: new `om mirror` + `om embed
  --mirror` write the exact canonical (JCS) preimage bytes (byte hash == embedded `payloadHash`), so a
  self-hosting broker can reach domain-origin (CLI-tested: mirror hash == payload hash). **Staleness**:
  `classifyStale` single-sourced into `js/src/stale.ts` (extension re-exports) and wired into the public
  badge (`evaluateBadge` → `view.stale`/`mirrorAssertedDate`; the shell renders a "superseded" sub-line),
  proven by a widget unit test + the consumer gate's stale-mirror case. Honest fallback: a genuine
  mismatch is never labelled stale.
- **Evidence:** `js/src/origin.ts:44-52` requires a same-domain HTTPS JSON-LD mirror whose byte hash equals
  the embedded `payloadHash`; **no tool emits those exact bytes** — `om read` (`main.py:375-388`)
  pretty-re-serializes, breaking JCS byte-equality; no mirror emitter in `/cli`, `/js/widget`, `/site`.
  Staleness (OMW-W051) computed only in the extension (`stale.ts` → `service-worker.ts:117-122`);
  `badge-core.ts:68-101` and `/verify` never run it.
- **Gap:** Self-hosting broker is stuck at grey "Unaltered since embed" forever; buyers see a confident
  badge on a superseded deal.
- **Fix:** Add `om mirror <pdf> -o payload.jsonld` (or `om read --raw`) emitting the exact JCS preimage
  bytes; have `embed`/`embed-batch` optionally emit the mirror alongside the PDF. Document the
  `<openom-badge src=… mirror=…>` step. Port `classifyStale` into `badge-core` so the public widget/`/verify`
  show a "superseded — newer version available" sub-line.

### M3 — "Publish" in the popup is a developer HMAC webhook, not broker distribution
- **Severity:** 🟠 Major · **Status:** AT PEAK (buildable part) — the popup section is reframed: an
  "Advanced: send to a connected system (webhook)" `<details>` disclosure with an honest hint ("this is
  not how buyers receive the OM — rehost the embedded PDF"), the button relabeled "Publish"→"Send",
  gated by unit + consumer + a11y tests. **Shareable verified-view link shipped backend-free:** a new
  `/v/?src=<url>` page renders the trust badge + deal card (address/price/cap/NOI/tenant) + a download,
  entirely client-side from the hash-verified payload (honest CORS fallback), and the `/embed/` companion
  hands the broker a copyable `/v/` link after embed. Site-gated (3 cases).
- **Evidence:** `popup.ts:93-113` asks for a "https://your-webhook…" URL + "signing secret";
  `publish.ts:45-60` POSTs a §Y HMAC envelope. A buyer receiving the PDF has no low-friction verify path —
  every route (`examples/README.md:6-15`) needs an install or a manual re-upload.
- **Gap:** Broker reads "Publish," expects to send a deal to buyers, faces a portal/CRM dev integration
  they can't use — illusion of a distribution path delivering nothing.
- **Fix:** Rename to "Send to connected system (webhook)" and hide behind an advanced/portal toggle. Give a
  real primitive — a shareable hosted verified-view link (`openom.app/v/<hash>` showing badge + deal card +
  PDF download) so buyers trust the file without installing.

### M4 — Extraction leaves the highest-value, most error-prone fields blank on every path
- **Severity:** 🟠 Major · **Status:** AT PEAK — **propertyType** now mapped (Buildout research attr +
  on-device hint), and **pricePerUnit / pricePerSF / termMonths** derived deterministically from
  already-mapped values/dates, in BOTH the CLI mapper (`buildout.py`) and the extension connector
  (`buildout.ts`) at parity, each unit-tested. On-device text now reads **80 pages** (was 40) so
  back-of-OM rent rolls/exhibits reach the model. NB: rent-schedule import from Buildout is intentionally
  NOT added — the real base-rent field name isn't in the known shape, and guessing it would violate
  "never invent"; on-device extraction still fills `rentSchedule[]` from the OM text.
- **Evidence:** rent schedule never auto-filled from Buildout (`buildout.ts:117-123` maps only
  tenant/leaseType/dates; no `rentSchedule[]`). `propertyType` never auto-filled by either path
  (`buildout.ts:98-106`, `on-device.ts:28-35`). Only first 40 pages read (`text.ts:29` default,
  `panel.ts:363` no override). `termMonths`/`pricePerUnit` deterministically derivable but computed by
  nothing; landlord-responsibility grid + options 100% manual.
- **Gap:** The numbers buyers underwrite (and most likely to be miskeyed) are always hand-typed; the rent
  roll/financial exhibits at the back of long OMs are never sent to the model.
- **Fix:** Map Buildout base-rent/escalation into at least `rentSchedule[0]` (`source: extracted`); map
  property type/subtype (in `research_property_attributes`) to `property.propertyType` and add to the
  on-device hint; raise/remove the text page cap or select pages by keyword (rent/NOI/schedule/lease);
  derive `termMonths` and `pricePerUnit` at draft time.

### M5 — On-device AI advertises "ready" when Gemini Nano isn't downloaded
- **Severity:** 🟠 Major · **Status:** AT PEAK — new `readiness()` on the extractor seam distinguishes
  **ready / needs-download / unavailable** (`on-device.ts`, unit-tested); the panel labels the button
  "Download on-device AI (~1-2 GB), then extract" + shows a manual-entry hint when the model isn't
  downloaded, and `extract()` passes a `create({monitor})` so a first-use download reports **progress**
  ("Downloading on-device AI… NN%") instead of hanging silently. Proven by unit tests + a headed author
  gate `[M5]` case. #75 (real Nano hand-verify) stays environment-blocked.
- **Evidence:** `on-device.ts:113-120` `available()` returns true for `'downloadable'`/`'downloading'`;
  `extract()` (`on-device.ts:124`) calls `lm.create()` with no progress monitor; `panel.ts:355-382` only
  prints "Extraction failed." Compounded by #75 (real Prompt API never hand-verified, environment-blocked).
- **Gap:** Broker on stock Chrome clicks Extract and either waits through a silent multi-GB download or gets
  a bare failure toast; realistic default for most brokers is no auto-fill at all.
- **Fix:** Split availability into ready vs needs-download; label the button "Download on-device AI (~Xgb)
  then extract" and pass a `create()` monitor for progress. Treat manual entry as the honest default and
  say so up front.

### M6 — Capture is inconsistent and hides the most valuable path
- **Severity:** 🟠 Major · **Status:** AT PEAK (correctness) — the tab path now returns a **typed reason**
  (`refetchPdfResult` → `oversize` | `fetch`, unit-tested); a >25 MB OM gets a clear, actionable message
  ("larger than 25 MB — use the file picker (no limit) or the CLI") instead of a generic network error,
  and every fetch failure points to the (uncapped) file picker. **Connector prominence added:** the
  capture screen now detects a Buildout listing tab (`buildoutRefFromUrl`, unit-tested) and shows a hint
  that fields will be imported once the OM PDF is chosen — the connector is no longer buried in the flow.
- **Evidence:** `detect.ts:7` caps `refetchPdf` at 25MB → null → `panel.ts:103-108` generic "Could not
  fetch this page's PDF bytes"; the file path (`panel.ts:85-89`) has **no cap**. On a Buildout listing page,
  `panel.ts:92-95` fetches `tab.url` unconditionally; `startReview` gates on `looksLikePdf`
  (`panel.ts:117-125`) and errors on HTML; the Buildout connector is only reachable inside `startReview`
  (`panel.ts:214-238`).
- **Gap:** Image-heavy CRE OMs >25MB behave differently by route with no explanation; the most
  effort-saving capture path (connector import) is undiscoverable.
- **Fix:** Return a typed oversize reason ("larger than 25MB — use the file picker or the CLI"); ideally
  unify the caps. Detect a connector-matching active-tab URL up front and surface "Import fields from this
  Buildout listing."

### M7 — The review/assertion gate is illegible and can't cite the numbers that matter
- **Severity:** 🟠 Major · **Status:** AT PEAK (legibility bugs) — (a) **assertedBy no longer shows
  "Omitted"** (dropped from the schema-expected paths — it's the profile, stamped at Assert); (b)
  **rent-schedule/options rows are no longer flagged "no evidence"** (they have no citation inputs), nor
  is assertedBy; (c) the derived panel now speaks **human language** — omissions, errors, and the
  reprice diff use `humanizeField` ("Deal › Cap Rate", not `/deal/capRate`), and the reprice shows
  "replaces your prior assertion (sha256:abcd…)" instead of a raw 64-char hash; and (d) every cited
  field now has a **"view page" affordance** that opens the source OM at the cited page (blob URL +
  `#page=N`, bytes stay local) so the broker can check the number against the document. Unit + author +
  a11y gated.
- **Evidence:** `form.ts:151-174` `rentEditor()` renders no page/quote inputs for rent periods, yet
  `draft.ts:75-80` flags each rent leaf as evidence-missing. `schema-paths.ts:11` includes `assertedBy`, so
  `/assertedBy/broker|brokerage|license` list under "Omitted" even after being typed (stamped later in
  `assert.ts:29`). Derived panel speaks JSON-pointers (`review-panel.ts:62,80,88-90`) while the form
  humanizes (`schema-fields.ts:50`). `form.ts:94-110` shows only a numeric `pg` input + truncating quote;
  the panel never renders the PDF.
- **Gap:** The gate the whole spec hangs on is confusing where it must be trustworthy; rent (most-disputed)
  can't be cited; the broker's own profile reads as "you forgot your name"; the reprice diff is least legible.
- **Fix:** Give rent rows the same page/quote evidence inputs as `fieldRow()`. Exclude `assertedBy` from
  expected paths (or compute omissions against the finalized payload). Reuse `humanize()` across
  omissions/errors/reprice-diff. Render the cited page (pdf.js already loaded) or show wrapped read-only
  quote text with a "jump to page N" affordance.

### M8 — Bulk embed mis-asserts across the catalog and skips silently
- **Severity:** 🟠 Major · **Status:** DONE — `buildout-manifest` gained `--overrides` (per-listing
  broker/brokerage/license/noiType/noiAsOfDate, so a multi-broker catalog asserts truthfully instead of
  one identity stamped on all), a `coverage.json` report (per-listing filled/omitted fields + `--min-fields`
  sparse flag, P8 folded in), and reasoned skips (`{id, reason}` instead of a silent count). NB: broker
  identity is taken from flags/overrides, NOT guessed from Buildout (the real broker field isn't in the
  known shape — guessing it would violate "never invent").
- **Evidence:** `main.py:328-344` takes single `--broker/--noi-type` flags applied unchanged to every
  listing (`main.py:348-357`, `buildout.py:120-127`); Buildout JSON carries per-listing broker info the
  mapper never reads. `main.py:348-353` pairs by exact `<id>` stem; a mismatch is silently appended to
  `skipped` with only a count printed (`main.py:366-367`). Docstring says "review before embedding" but the
  only review tool is the one-OM extension panel.
- **Gap:** Mass mis-assertion baked into hundreds of OMs (worst Rule 6 failure); real (non-numeric) OM
  filenames quietly never embed; at catalog scale review is skipped.
- **Fix:** Default `assertedBy` and `noiType` per-listing from the listing's own fields (overridable). Join
  on a field inside the JSON (the OM filename/url Buildout returns) and list each skip with its reason. Emit
  a human-readable coverage report (CSV/HTML: per-listing filled fields, omissions, consistency warnings,
  near-empty flags) for triage before bulk embed.

---

## ⚪ Polish / nice-to-have

### P1 — No starter `deal.json`
- **Status:** DONE — a valid starter payload is deployed at `/sample/deal.json` and the broker
  quick-start links it (`curl -O …/sample/deal.json`, edit, embed).

### P2 — Manual entry nags "please cite" on every objective field
- **Status:** DONE — the "please cite" flag is scoped to financially-material figures only (an allowlist:
  askingPrice/capRate/noi/pricePerSF/pricePerUnit/buildingSF/units/occupancy); addresses, enums, and
  dates are no longer nagged. Unit-tested (`[P2]`).

### P3 — "Will be embedded" preview is raw JSON; reprice diff shows an opaque 64-char supersedes hash
- **Status:** DONE — the extension "Will be embedded" section now leads with a plain-language recap
  (property/price/cap/NOI/tenant/asserted-by) and the raw JSON is a collapsible block; the reprice diff's
  opaque hash was already humanized in M7.

### P4 — Tab capture silently does nothing when `tab.url` is undefined; no feedback during large re-fetch
- **Status:** DONE — `captureFromTab` shows a clear message when there's no tab URL, and `captureFromUrl`
  renders a "Fetching PDF…" state during the re-fetch.

### P5 — PDF sniff only inspects first 8 bytes
- **Status:** DONE (during M1) — `looksLikePdf` (single-sourced in `js/src/author.ts`) scans the first
  1024 bytes, so a BOM/leading-bytes OM is no longer wrongly rejected.

### P6 — RC4/password-encrypted OMs refused in-browser with only a "go use the CLI" message
- **Status:** DONE — in-browser **RC4 empty-password decrypt** shipped (`decrypt.ts`: "V2" CFM, per-object
  keys without the AESV2 sAlT suffix, RC4 string/stream + object-stream bodies). Proven by the previously
  "must return null" `enc-rc4.pdf` fixture, now a full decrypt + openOM embed round-trip. Genuine
  passwords still fall back to the CLI (correctly).

### P7 — No per-deal copy-paste badge snippet after embed; `/verify` shows plain text not the real badge
- **Status:** DONE — `/verify` (file + URL) now renders a real colored trust **pill** (matching the
  `<openom-badge>` widget), not plain text; live-URL check shipped in B2; and after embed the companion's
  share helper hands the broker a copy-paste `<script>` + `<openom-badge src=…>` snippet for their listing
  page. Site-gated.

### P8 — Sparse Buildout listings embed as near-empty-but-valid payloads
- **Status:** DONE (folded into M8) — `buildout-manifest --min-fields` + `coverage.json` per-item
  field counts + a `sparse` list.
- **Evidence:** Bulk finding 6.

---

## ✅ Working well — leave as-is
Encrypted-refuse, empty-password AES decrypt notice, scanned "enter fields manually," and
tampered-prior-payload messaging are all specific and actionable (Capture finding 5). Genuinely good.

---

## Top-3 leverage (if only three ship)
1. **B1** — tool + zero-install embed path (Web Store + Release `.zip` + hosted `/verify/` authoring companion).
2. **B2** — close the last mile: upload-exact-file guidance + paste-a-URL post-rehost verify loop (ideally a shareable hosted verified link).
3. **B3 + M8** — one authenticated `om buildout-pull` with per-listing truthful assertions + a coverage report.

The engine and trust model are sound; the gaps are almost entirely at the human edges —
**acquisition, distribution, legibility** — where a standard lives or dies on adoption.
