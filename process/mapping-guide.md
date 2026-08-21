# openOM mapping guide

> How an extracting agent turns an offering-memorandum (OM) PDF into an openOM 0.1 payload that the
> deterministic validator accepts. Shared substance for both `SKILL.md` (Claude) and
> `agent-instructions.md` (any MCP client). This is the load-bearing artifact of the `/process`
> layer.

## Stance - assertions, not facts

An OM is an **advertisement** - a broker's **opinion of value**, agreed to by the seller before
publication. So an openOM payload is **one identified party's opinion as of a date**, not ground
truth: it records who asserted it, unaltered, and as of when - never that the opinion is true
(*verified means provenance, not truth*). Your job is to *transcribe* what the OM states into
structured fields - never to appraise, compute market truth, or fill gaps with plausible guesses.

- **Inference lives only here, in the mapping step.** Every `om_*` tool you call is deterministic
  and holds no model - you supply the reading/mapping; the tools embed, read, validate, and extract
  bytes. Nothing you do adds inference to `/core`, the MCP server, or consumer mode (§6a).
- **Never invent facts.** If the OM does not state a field, **omit it**. An absent field is honest;
  a guessed one is a lie that ships forever.
- **You are not the asserting party.** `assertedBy` is the *reviewing broker*, filled at the review
  gate - not you. Until a human reviews and approves, the payload is a draft.

## The loop (tool by tool)

1. **Classify** - `om_inspect(pdf)` → `class` ∈ {native, hybrid, scanned}, page count, text
   coverage, payload presence. `scanned` (image-only) → read the pages with your own vision/OCR;
   the tools still never run inference.
2. **Gather** - `om_extract_text(pdf, pageRange, cursor)` for the text + best-effort tables
   (paginate by passing `nextCursor` back verbatim); `om_extract_images(pdf)` for site plans /
   figures as context. Do not stream unbounded text - page through it.
3. **Map** - build the payload from what you read, per the Field map + Vocabularies below. Set
   `source: "extracted"` on rent-schedule periods. Omit anything unsupported.
4. **Validate & iterate** - `om_validate(payload, schema)`; see Consistency relationships. Fix
   every `OMV-E###`; treat every `OMW-W###` as *your extraction is probably wrong* and re-read the
   source - never silence a warning.
5. **Human review gate** - the assertion moment (next section). Stop; present; wait.
6. **Embed** - `om_embed(pdf, payload, assertedDate)`. A reprice re-embed replaces in place and
   sets `meta.supersedes` to the prior payload hash; no signing.

## Field map

Payload path → where it typically appears in an OM → notes.

| Path | Typical OM location | Notes |
|---|---|---|
| `assertedBy.broker` / `.brokerage` / `.license` | Contact block / disclaimer / broker of record | Required. Filled/confirmed by the reviewing broker at the gate. |
| `assertedBy.website` / `.licenseJurisdiction` / `.licenseAuthority` | Contact block / disclaimer | Optional identity anchors (#118). `website` = the broker/brokerage domain (feeds §10 origin verification); `licenseJurisdiction` = ISO 3166 (e.g. US-CA); `licenseAuthority` = issuing body. Confirmed by the broker, not guessed. |
| `assertedDate` | - | The assertion date; set at the review gate, not extracted. |
| `currency` | Financials (assume USD if unstated) | Optional; omit to default USD ([OM-DD-002]). |
| `property.address.{streetAddress,addressLocality,addressRegion,postalCode,addressCountry}` | Cover / property summary | `addressRegion` 2-letter US; `addressCountry` ISO-2 (default US). |
| `property.geo.{latitude,longitude}` | Aerial/map caption, rarely printed | Omit unless stated. |
| `property.propertyType` | Cover / property summary | Optional (#114). retail\|office\|industrial\|multifamily\|land\|mixed-use\|hospitality\|self-storage\|other (open string). |
| `property.apn` | Property details | Assessor parcel number, as printed. |
| `property.buildingSF` | Property details / "±X SF" | Number only. |
| `property.lotAcres` / `.yearBuilt` / `.yearRenovated` | Property details | Omit if absent. |
| `property.units` | Cover / property summary ("40 units") | Integer unit count (multifamily / mixed-use). Omit if absent. |
| `property.occupancy` | Cover / rent-roll summary ("95% occupied") | **Decimal fraction: 95% → 0.95** (matches capRate). Omit if absent. |
| `deal.askingPrice` | Cover / financial summary ("Offering Price") | Bare number, major units. |
| `deal.capRate` | Financial summary ("Cap Rate 6.25%") | **Decimal fraction: 6.25% → 0.0625.** |
| `deal.noi` | Financial summary ("NOI") | Bare number. |
| `deal.noiType` | Financials ("in-place" vs "pro forma") | Enum in-place\|pro-forma; required with `noi`. Set/confirmed at gate. |
| `deal.noiAsOfDate` | Rent roll date / "as of" | Required with `noi`. |
| `deal.pricePerSF` | Financial summary | Should equal askingPrice÷buildingSF. |
| `deal.pricePerUnit` | Financial summary ("$/unit") | Multifamily analog of pricePerSF; should equal askingPrice÷units. |
| `deal.status` | Marketing status | Enum active\|under-contract\|sold\|withdrawn. |
| `lease.tenantEntity` | Lease abstract / tenant summary | Legal entity name as printed. |
| `lease.guarantor.name` / `.type` | Lease abstract | `type` ∈ corporate\|franchisee\|personal\|none. |
| `lease.landlordResponsibilities.{roof,structure,parking,hvac,taxes,insurance,cam}` | Lease abstract ("Landlord Responsibilities") | Booleans; true = landlord bears it. |
| `lease.leaseTypeAsserted` | Lease abstract ("NNN") | Enum N\|NN\|NNN\|absolute-net\|gross\|modified-gross; the broker's *label* (advisory). |
| `lease.commencement` / `.expiration` | Lease abstract ("Lease Term") | ISO dates. |
| `lease.termMonths` / `.remainingTermMonths` | Lease abstract | Cross-checked against the dates (W030/W031). Omit if not stated. |
| `lease.rentSchedule[]` = `{periodStart,periodEnd,annualRent,monthlyRent?,rentPSF?,escalationFromPrior?,abatement?,source}` | Rent schedule / bumps table | Chronological; each period `source: "extracted"`. |
| `lease.options[]` = `{count,lengthYears,escalation}` | "Options to Renew" | Option periods - NOT appended to rentSchedule. |
| `meta.supersedes` | - | `null` on first embed; prior payload hash on a reprice re-embed. |
| `meta.sourceDocHash` | - | Optional; hash of the source doc if tracked. |
| `meta.imageRights` | Disclaimer / photo credits | Optional rights statement for the OM's imagery. |
| `ext` | - | Optional (#115). Vendor/non-standard fields ONLY, namespaced by vendor (`ext.<vendor>.…`). Never extracted into core paths; preserved untouched. |

## Vocabularies & units (the traps)

- **`capRate` is a decimal fraction.** Worked example: the OM prints "Cap Rate: 6.25%" → `"capRate": 0.0625`. Never `6.25`.
- **Money:** bare JSON numbers in **major units** (dollars) - no `$`, no thousands separators, no suffix. "$2,500,000" → `2500000`.
- **Dates:** ISO `YYYY-MM-DD`.
- **Enums (use exactly):** `leaseTypeAsserted` {N, NN, NNN, absolute-net, gross, modified-gross}; `deal.status` {active, under-contract, sold, withdrawn}; `guarantor.type` {corporate, franchisee, personal, none}; `noiType` {in-place, pro-forma}.
- **`landlordResponsibilities`** are booleans; a `true` means the *landlord* pays it (so an NNN lease usually has all of taxes/insurance/cam `false`).

## Provenance rules

- Every rent-schedule period you extract carries **`source: "extracted"`** - unreviewed. The review
  gate promotes it to `"asserted"`. Never write `"verified"` from extraction ([OM-SCOPE-007]).
- Omit unknowns; do not default-fill. `noiType`/`noiAsOfDate` are required *whenever* `noi` is
  present - if the OM doesn't make NOI's basis clear, surface that at review rather than guess.
- Market truth (valuation, investment merit, legal opinion) is out of scope - never add it.

## Ambiguity & uncertainty - omit and flag, never guess

When a value is unreadable, ambiguous, or you are not confident you read it correctly:

- **Omit the field.** Do not write a placeholder, a rounded guess, or a "probably" value. An absent
  field is honest and forward-compatible; a guessed one is a lie that ships.
- **Record what you omitted and why**, and surface it at the review gate (see the *Omissions* item
  in [`./review-contract.md`](./review-contract.md)) so the reviewing broker can supply it from
  knowledge or confirm the omission.
- **Never manufacture corroboration to raise confidence.** Unreviewed extraction stays
  `source: "extracted"`; you may not promote it to `"verified"` because you feel sure.
- **NOI basis ambiguity is common and load-bearing.** If `noi` appears but whether it is in-place
  vs pro-forma, or its `noiAsOfDate`, is unclear, do NOT guess `noiType`/`noiAsOfDate` - they are
  *required* whenever `noi` is present, so surface the ambiguity and leave the payload a draft until
  the human resolves it at the gate. (Guessing here silently mislabels the single most scrutinized
  number in the OM.)
- A **consistency warning is also an uncertainty signal** - see the next section; treat it as
  "re-read," not "override."

## Consistency relationships (why warnings mean "look again")

`om_validate` never judges market truth; it checks the payload's internal arithmetic. Each warning
tells you a number you transcribed disagrees with another - almost always an extraction error:

- `OMW-W010` cap rate ≠ NOI ÷ askingPrice · `W011` pricePerSF ≠ askingPrice ÷ buildingSF · `W013`
  capRate outside [0.02, 0.20] · `W014` non-positive askingPrice/noi/buildingSF.
- `W020` year-1 annualRent ≠ in-place NOI · `W021`/`W022` schedule gap/overlap · `W023`
  escalationFromPrior ≠ the annualRent step · `W024` rentPSF ≠ annualRent ÷ buildingSF · `W025`
  monthlyRent ≠ annualRent ÷ 12 · `W026` period outside the lease term.
- `W030`/`W031` remaining/total term ≠ the date math · `W032` assertedDate in the future ·
  `W033` noiAsOfDate after assertedDate · `W034` expiration ≤ commencement.
- `W040`/`W041` `leaseTypeAsserted` contradicts `landlordResponsibilities`.

A warning is not a schema error (it never blocks embed), but shipping one means you probably mis-read
the OM. Re-read, correct, re-validate - until schema-clean and warning-clean or the residual is
explained to the reviewer.

## Worked traps (read these before you map)

Each is a real first-pass mistake, the warning it trips, and the fix. These are machine-checked in
`spec/tests/test_process_traps.py` against the demo OM.

- **Percent vs decimal.** OM prints "Cap Rate: 5.75%". Writing `capRate: 5.75` trips `OMW-W013`
  (outside the [0.02, 0.20] band) and `OMW-W010` (5.75 ≠ 143750÷2500000). **Fix:** `0.0575`.
- **NNN but a landlord flag is true.** Lease is "NNN" (tenant pays all) but you set
  `landlordResponsibilities.taxes: true`. Trips `OMW-W040`. **Fix:** for an NNN lease the pass-
  through flags (taxes/insurance/cam) are `false` - re-read who pays.
- **Schedule gap/overlap.** You mis-read a period boundary so period 2 starts a month after
  period 1 ends → `OMW-W021` (gap); starts before it ends → `OMW-W022` (overlap). **Fix:** periods
  are chronological and contiguous (`periodStart[i] = periodEnd[i-1] + 1 day`).
- **rentPSF that doesn't tie.** `rentPSF: 30.00` when `annualRent 143750 ÷ buildingSF 6000 = 23.96`
  → `OMW-W024`. **Fix:** transcribe the printed rent/SF and confirm it ties, or omit it.
- **Term math.** `termMonths: 60` when `expiration − commencement ≈ 120` months → `OMW-W031`.
  **Fix:** omit stated terms you can't reconcile, or correct the dates you read.
- **Wrong escalation.** `escalationFromPrior: 0.05` when 158125÷143750 − 1 = 0.10 → `OMW-W023`.
  **Fix:** it is the *fraction* between adjacent `annualRent`, not a guess.

A warning is never fatal (it can't block embed), but it almost always means you mis-read the OM.
Re-read, correct, re-validate.

## The review gate - the assertion moment

Extraction output is a **draft**. It becomes a broker assertion only when a human reviews the
payload against the source and approves (§7a, [OM-EXTP-003]). What you MUST present at the gate is
specified in [`./review-contract.md`](./review-contract.md). In short, at the gate:

1. Present the payload, the source evidence for each field, and any residual warnings.
2. On approval: set `assertedBy` to the reviewing broker, set `assertedDate` (today), confirm
   `noiType`/`noiAsOfDate`, and promote each rentPeriod `source` `"extracted"` → `"asserted"`.
3. Only then `om_embed`. The agent MUST NOT self-assert or skip the gate.
