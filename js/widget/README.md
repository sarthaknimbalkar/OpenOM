# `<openom-badge>` — embeddable trust badge

A drop-in web component that shows the openOM verification state for a PDF, for portals and listing
sites that want the §AA badge next to a deal without shipping the browser extension (#144).

It runs the **exact same** deterministic, inference-free `openom-js` read/verify path the extension
uses (re-fetch bytes → read embedded payload → integrity check → optional origin verification), so a
portal badge can never disagree with the extension. No inference, no keys, no per-view cost.

## Use it

```html
<script src="https://openom.app/openom/widget/openom-badge.js" defer></script>

<!-- integrity badge: proves the payload is unaltered since embed -->
<openom-badge src="https://cdn.example.com/listings/123/deal.pdf"></openom-badge>

<!-- add a mirror on the SAME registrable domain to reach the origin-verified state -->
<openom-badge
  src="https://broker.example.com/deal.pdf"
  mirror="https://broker.example.com/deal.json"
  details="https://broker.example.com/listing/123"
></openom-badge>
```

The badge fetches the PDF bytes itself, so the PDF host must allow the fetch (same-origin, or
`Access-Control-Allow-Origin` on cross-origin PDFs). It **never** scrapes a PDF viewer.

## What it shows (honest by construction, §AA / [OM-TRUST-003])

| State                  | Shown                       | Means                                                                     |
| ---------------------- | --------------------------- | ------------------------------------------------------------------------- |
| `absent` / `encrypted` | _nothing_                   | not an openOM PDF (or unreadable) — no false reassurance, no nag          |
| `hash-mismatch`        | ⚠ **Altered payload**       | embedded data doesn't match its hash — do not trust                       |
| `integrity-ok`         | ✓ **Unaltered since embed** | integrity checks out; **not** proof of authorship (never says "verified") |
| `origin-verified`      | ✓✓ **Origin-verified**      | the domain vouches for this exact payload (HTTPS + matching mirror)       |

A fetch/parse error fails **closed** to `absent` (renders nothing) — an error is not evidence of
tampering. Only static `honestLabel` copy is rendered; no payload-derived text touches the DOM, so a
malicious payload has no XSS surface.

## Programmatic use

```ts
import { evaluateBadge, computeBadge } from "openom-js/widget/badge-core.js";
const view = await evaluateBadge({ src: pdfUrl }); // { state, label, caption, ariaLabel, honest }
```

## Build

`npm run build:widget` (from `/js`) emits `widget/dist/openom-badge.js` (a single minified IIFE
classic script) and asserts it is inference-free. Deploy it alongside the hosted namespace (see
`spec/README.md`), e.g. at `…/openom/widget/openom-badge.js`.
