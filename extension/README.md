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
