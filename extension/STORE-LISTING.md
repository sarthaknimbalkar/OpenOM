# Chrome Web Store — submission reference (openOM)

Operational reference for submitting the openOM extension. Publisher: **Vervelio Labs**.
Package with `npm run package` → `openom-extension-<version>.zip` (deterministic, forward-slash entries,
manifest at root). Privacy policy: **PRIVACY.md** (host it at a public URL and paste that URL in the
dashboard).

## Store listing copy

- **Name:** openOM
- **Category:** Productivity
- **Single-purpose description (required):**
  > openOM detects, verifies, and embeds machine-readable openOM data in commercial-real-estate
  > offering-memorandum PDFs. Its single purpose is working with openOM data in OM PDFs.
- **Summary (132 chars max):**
  > Detect, verify, and embed openOM data in CRE offering-memorandum PDFs — locally, with no tracking.
- **Detailed description:** what it does (consumer: detect/read/verify/badge; author: capture/review/
  assert/embed, incl. in-browser decrypt of permission-encrypted OMs), that it is deterministic and
  local-first, and that inference (author pre-fill) is on-device only.

## Permission justifications (paste into the dashboard)

- **activeTab** — Read the URL and PDF of the tab the user is acting on, only on user invocation, to
  detect/verify/embed openOM data in that OM.
- **storage** — Persist the user's broker profile and settings locally on the device.
- **sidePanel** — Present author mode (capture → review → assert → embed) in the side panel.
- **Host permission `https://*/*`** — Re-fetch the PDF bytes and the domain `.well-known` mirror of the
  sites the user views (to read/verify from source, not the viewer), and badge openOM links on pages
  where the user enables link-badging. Not used to collect browsing history or personal data.
- **Content script on `https://*/*`** — Badge openOM `.pdf` links; runs only on domains the user opts in
  to via the options page. (If review pushes back on breadth, the fallback is `activeTab`-gated dynamic
  injection instead of a static all-sites content script.)

## Data-use disclosures (Privacy practices tab)

- Does the extension collect user data? **No** personal data is collected or transmitted to the
  publisher. Profile/settings stay in local storage; webhooks go only to user-configured endpoints.
- Not sold to third parties; not used for unrelated purposes; not used for creditworthiness/lending.

## Assets still required before submit (not code — gather these)

- [ ] **Screenshots:** 1–5, 1280×800 or 640×400 PNG (popup verify card; author review panel; options
      page; a badged listing page).
- [ ] **Small promo tile:** 440×280 PNG (optional but recommended).
- [ ] **Store icon:** 128×128 — already in `public/icons/icon-128.png`.
- [ ] **Privacy-policy URL:** host `PRIVACY.md` content at a public URL (e.g. a Vervelio page or the
      repo's GitHub Pages) and paste it in the dashboard.
- [ ] **Support/homepage URL:** the GitHub repo or a Vervelio landing page.

## Pre-submit engineering checklist (code-side — all currently satisfied)

- [x] MV3 manifest, `minimum_chrome_version` set, icons 16/32/48/128 present.
- [x] Only used permissions declared (removed unused `scripting`).
- [x] Package zip uses forward-slash paths, manifest at root (`npm run package`).
- [x] Bundle is inference-free (`node scripts/assert-no-inference.mjs dist`).
- [x] Live gate green (consumer + author + a11y + link-badging), unit + js suites green.
- [ ] Bump `version` in `public/manifest.json` per release before packaging.
