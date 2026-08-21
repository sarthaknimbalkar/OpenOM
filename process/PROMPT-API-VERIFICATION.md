# On-device Prompt API - manual verification kit (#75)

The author-mode on-device extractor is the **only inference site** in openOM
([extension/src/author/extract/on-device.ts](../extension/src/author/extract/on-device.ts)). CI proves
its architecture with an **injected fake** `LanguageModel` (egress-zero, JSON shape, the review gate).
What CI *cannot* run is the **real Gemini Nano** - so this is the turnkey hand-check for a
Prompt-API-capable Chrome. It takes ~5 minutes and yields a clear pass/fail to paste into #75.

## 0. Prerequisites (one-time)

- Desktop **Chrome** (recent), Windows 10/11 · macOS 13+ · Linux/ChromeOS, with several GB free disk.
- Enable flags, then restart:
  - `chrome://flags/#prompt-api-for-gemini-nano` → **Enabled**
  - `chrome://flags/#optimization-guide-on-device-model` → **Enabled BypassPerfRequirement**
- Let the model download: `chrome://components` → **Optimization Guide On Device Model** → *Check for
  update* until a version appears (not `0.0.0.0`).
- Confirm the API is live - in DevTools console: `await LanguageModel.availability()` → `"available"`.
- Build + load the extension: `npm --prefix extension run build`, then load `extension/dist` unpacked.

## 1. Run the extraction

1. Open the ground-truth OM **[process/example/sample-om.pdf](example/sample-om.pdf)** in a tab.
2. Open the extension popup → **“Embed a payload…”** (author side panel).
3. Click **“Extract with on-device AI”** and wait for the draft to populate the review form.

## 2. Expected draft (ground truth = [example/expected-payload.json](example/expected-payload.json))

The model drafts only the machine-readable fields (never assertedBy/assertedDate/noiType - those are
the human's at review). Values should match, each with a page + quote evidence:

| Field | Expected value |
|-------|----------------|
| `property.address.streetAddress` | 500 Example Blvd |
| `property.address.addressLocality` / `addressRegion` / `postalCode` | Testville / TX / 75000 |
| `deal.askingPrice` | 2500000 |
| `deal.capRate` | **0.0575** (decimal fraction, not `5.75`) |
| `deal.noi` | 143750 |
| `lease.tenantEntity` | Placeholder Quick Service, LLC |
| `lease.leaseTypeAsserted` | NNN |
| `lease.rentSchedule` | ≥1 row; first ≈ {periodStart 2021-06-01, annualRent 143750} |

## 3. Pass/fail checklist - record each

- [ ] **Real model used** - `LanguageModel.availability()` was `"available"`; the draft appeared with
      no fake injected (not the CI harness).
- [ ] **JSON adherence** - every drafted field parsed cleanly; no prose leaked into values, `capRate`
      is the decimal fraction `0.0575` (the responseConstraint held).
- [ ] **Evidence cited** - each field shows a page number + the exact quoted OM text.
- [ ] **No over-reach** - fields the OM doesn't state are omitted (not guessed); assertedBy/
      assertedDate/noiType/noiAsOfDate are **blank** (human-only, [OM-PRIV] review gate).
- [ ] **Session API shape** - `create()` → `prompt(input, {responseConstraint})` → `destroy()` all
      behaved; no unhandled rejection in the console.
- [ ] **Egress-zero (spot-check)** - with the DevTools **Network** tab open during extraction, **no**
      request leaves the device (already CI-proven with the fake; confirm on the real path too).

## 4. Report

Paste the ticked checklist + Chrome version + model version into **#75**. Any unchecked box is a real
finding - file it (prompt tuning, JSON-constraint gap, or session-API drift) and link it there.
