# openOM browser extension (MV3)

Two personas over the [`openom-js`](../js) core:

- **Consumer mode** (toolbar popup): re-fetch the viewed PDF's bytes → read → verify integrity →
  domain-origin (§10.1) → honest badge; optional §Y webhook publish and per-domain link-badging.
- **Author mode** (side panel): capture → schema-driven review → explicit human assert → embed →
  download. In-browser decryption of empty-password AES OMs; optional on-device (Prompt API)
  extraction that pre-fills the review (egress-zero, human-only-consent gate).

The shipped bundle is **inference-free** (`scripts/assert-no-inference.mjs`), worker-free on the read
path, and eval-free (ajv standalone) under the MV3 CSP.

```sh
npm --prefix js install && npm --prefix extension install
npm --prefix extension run build     # → extension/dist (Load unpacked at chrome://extensions)
npm --prefix extension run package   # → openom-extension-<version>.zip (Web Store)
npm --prefix extension run test:unit # vitest; the live headed-Chromium gate is `test:consumer`
```

See [STORE-LISTING.md](STORE-LISTING.md) for submission and [PRIVACY.md](PRIVACY.md) for the
local-first privacy posture.

## Browser support (#145)

- **Chrome 116+** — primary target; load unpacked or install the packaged zip.
- **Edge** — the same MV3 `dist/` loads as-is (Edge is Chromium): `edge://extensions` →
  Developer mode → Load unpacked → `extension/dist`. No separate build.
- **Firefox** — roadmapped. Firefox MV3 differs (it prefers an event-page `background.scripts`
  over a `service_worker`, and needs `browser_specific_settings.gecko`), so it needs a distinct
  manifest target and a headed-Firefox pass on the live gate before we claim it. Tracked for a
  follow-up; the deterministic `/js` core it depends on is already browser-portable.

**Not a browser at all?** For server-side / CI embedding and validation, use the
[openom-embed GitHub Action](../.github/actions/openom-embed/) or the `om` CLI directly — no browser
needed. To *verify* a PDF without installing anything, use the hosted tool at `…/openom/verify/`.
