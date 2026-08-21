# openOM extension - Privacy Policy

_Last updated: 2026-08-18 · Publisher: Vervelio Labs_

The openOM browser extension is **local-first and deterministic**. It reads offering-memorandum PDFs,
verifies their embedded openOM data, and (in author mode) embeds broker-asserted data - all on your
device. It contains **no analytics, no tracking, no advertising, and no telemetry**, and it sends
**no data to Vervelio Labs**.

## What the extension processes

- **PDF bytes of the page you are viewing or a file you choose.** Processed in memory on your device to
  detect, read, verify, decrypt (empty-password OMs), and embed openOM data. PDFs are not uploaded
  anywhere by the extension.
- **Your broker profile and settings** (name, brokerage, license, webhook endpoints, per-domain
  link-badging preferences). Stored **only** in the browser's local extension storage on your device.

## The only network requests the extension makes

1. **Re-fetching PDF bytes** from the page's own URL, to read/verify it from the source (never by
   scraping the browser's PDF viewer).
2. **Fetching a `.well-known` mirror** from the OM's stated domain, to verify domain-origin (§10.1). This
   is a request to the broker's own site, carrying no personal data.
3. **Delivering a change-notification webhook** - only to an endpoint **you** configure - when you choose
   to publish. The request goes to your/your broker's own receiver, signed with your configured key.

There are no other network requests. In particular:

- **On-device extraction makes zero off-device requests.** When author mode pre-fills data using the
  browser's built-in on-device AI, all inference runs locally; this is enforced and proven by an
  automated egress-zero test ([OM-PRIV-001]).
- The extension never sends your PDFs, profile, or settings to Vervelio Labs or any third party.

## Data sharing and retention

- No data is shared with anyone. Data you enter (profile, settings) stays in local extension storage
  until you remove it or uninstall the extension.
- Uninstalling the extension deletes its local storage.

## Permissions (why each is needed)

- **activeTab** - read the URL/PDF of the tab you act on, only when you invoke the extension.
- **storage** - save your broker profile and settings locally on your device.
- **sidePanel** - open author mode in the browser side panel.
- **Host access to `https://*/*`** - re-fetch PDF bytes and mirror files from the sites you view, and
  badge openOM links on pages where you enable it. Used only to read PDFs/mirrors, never to collect
  browsing data.

## Contact

Questions: hello@vervelio.com · Source: https://github.com/sarthaknimbalkar/OpenOM
