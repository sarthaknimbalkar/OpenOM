# Understanding openOM validation results

**"All validation errors, haha" should never happen again.** This page explains,
in plain English, exactly what openOM is telling you when it checks your deal
data - what stops you, what's just a heads-up, and how to fix each one.

> **You do not need to read this end-to-end.** Skim the two rules below, then jump
> to the specific code you saw (e.g. `OMV-E001`, `OMW-W020`). Every message ends
> in a code like that - search this page for it.

If you are a broker and this feels like a compiler talking to you: you're right,
and the friendliest place to fix all of this is the browser form at
**<https://openom.app/embed/>** (nothing leaves your machine, and it walks you
through the fields). This page is the reference for *why* it said what it said.

---

## The one rule that governs everything

openOM sorts everything it finds into **two buckets**, and the difference is the
whole game:

| Bucket | Code looks like | Does it stop you? | What it actually means |
|--------|-----------------|-------------------|------------------------|
| **Error** | `OMV-E###` | **YES - blocks embed** | The data is *malformed* - a required field is missing, a value is the wrong type, or a number is out of its allowed range. openOM literally cannot produce a valid file until you fix it. |
| **Warning** | `OMW-W###` | **No - never blocks** | An *advisory* about the deal's own internal math. openOM noticed two numbers you entered disagree with each other (e.g. the cap rate doesn't match NOI ÷ price). It's telling you to double-check - it is **not** saying you're wrong. |
| **Info** | `OMI-I###` | No - never blocks | Just context. "You left currency blank, so I assumed USD." Nothing to fix. |

Two things follow from this that matter a lot:

1. **A pile of warnings is not a failure.** You can embed a file with a dozen
   warnings. Many good, honest OMs have a few. Warnings are guidance, not gates.
   The file is "blocked" **only when there is at least one `OMV-E###` error.**

2. **openOM never checks whether your deal is *true*.** It has no idea what the
   real cap rate is, what the market says, or whether the tenant is
   creditworthy. Every warning is a *self-consistency* check - "the numbers you
   typed don't add up against *each other*." That's it. **"Verified" in openOM
   means "unaltered since embed," not "the figures are correct."** These are
   assertions (your stated opinion as of a date), never facts.

So when you see output, ask one question: **are there any `E` codes?**
- No `E` codes → you're good to embed. Read the `W` codes if you want to
  tidy up the deal math, but you don't have to.
- Any `E` code → fix those first. They're listed below with the exact fix.

---

# ERRORS (these block - you must fix them)

There are only four error codes. Most of the time you'll only ever meet the
first one.

---

## `OMV-E001` - Schema error (the catch-all)

**What it means:** something about the *shape* of the data is wrong - a required
field is missing, a value is the wrong type (text where a number belongs), a date
isn't a real date, or a number is outside its allowed range. This is the generic
"that value isn't allowed here" error, so the specific message varies. The most
common real-world cases are below.

### The #1 trap: the cap-rate decimal (this hits almost everyone)

**You'll see:** `Deal › Cap Rate: 6.25 is greater than the maximum of 1 (OMV-E001)`

**Why:** every OM on Earth prints the cap rate as **"6.25%"**, so you naturally
typed **`6.25`**. But openOM stores cap rate as a **decimal fraction**, where
6.25% is **`0.0625`**. Anything above `1` would mean a cap rate over 100%, which
is impossible - so it stops you.

**How to fix:** move the decimal two places left. Drop the `%`, then divide by
100.

| You saw on the OM | Type this |
|-------------------|-----------|
| 6.25% | `0.0625` |
| 5% | `0.05` |
| 7.5% | `0.075` |
| 10% | `0.10` |

(This is a spec rule - `OM-CANON-007`: cap rate is always a decimal fraction, never a percentage number.)

### Other common `OMV-E001` cases

- **A required field is missing.** Every payload needs `@context`, `@type`
  (must be exactly `RealEstateListing`), `specVersion` (must be exactly `0.1`),
  `assertedBy` (who's asserting this), `assertedDate`, and `meta`. *Fix:* fill in
  the missing one. In the browser form these are always present; this bites
  people hand-editing JSON.
- **A date isn't a real date.** Dates must be `YYYY-MM-DD` (e.g. `2026-06-30`).
  `06/30/2026` or `June 30 2026` will fail. *Fix:* rewrite as `2026-06-30`.
- **Currency in the wrong format.** If you set a currency, it must be a
  three-letter ISO code in capitals - `USD`, `EUR`, `CAD`. `$` or `dollars`
  fails. *Fix:* use `USD` (or just leave it blank - blank means USD).
- **Wrong type.** Text where a number belongs, e.g. `askingPrice: "2,500,000"`
  (with quotes and a comma) instead of `askingPrice: 2500000`. *Fix:* numbers
  have no quotes, no commas, no `$`.

**Rule of thumb for `OMV-E001`:** read the field name at the front of the message
(`Deal › Cap Rate`, `Property › Building SF`, …) - it tells you exactly which box
to fix.

---

## `OMV-E002` - You entered an NOI, so NOI type and as-of date are required

**You'll see:** `Deal › Noi As Of Date: noiType/noiAsOfDate required with noi (OMV-E002)`
(or the same for `Noi Type`).

**What it means:** you gave a Net Operating Income (`noi`) figure, but an NOI on
its own is ambiguous. openOM requires you to say **two things** whenever you
state an NOI:

1. **`noiType`** - is it **`in-place`** (the income the building is actually
   earning today) or **`pro-forma`** (a projected / stabilized number)? This
   distinction is the difference between fact and forecast, so it's mandatory.
2. **`noiAsOfDate`** - the date that NOI is "as of" (e.g. `2026-06-30`).

**How to fix:** pick in-place vs pro-forma, and give the as-of date. In the
browser form these appear as required controls next to the NOI box. If you don't
actually have an NOI to assert, remove the NOI figure and the requirement
disappears.

*(Spec rule `OM-DD-003`.)*

---

## `OMV-E003` - The signature field has an invalid shape

**You'll see:** `Meta › Signature: signature must be null or the reserved {alg,keyId,value} shape (OMV-E003)`

**What it means:** cryptographic signatures are *reserved* in openOM 0.1 - the
feature isn't active yet. The `meta.signature` field must therefore be either
empty (`null`) or the exact reserved placeholder shape. Anything else is
rejected.

**How to fix:** you almost certainly don't want a signature. Set
`meta.signature` to `null`, or just delete the field. (You will basically never
hit this from the browser form - it only comes up when hand-editing JSON.)

*(Spec rule `OM-ERR-090`.)*

---

## `OMV-E010` - The "supersedes" pointer is the wrong format

**You'll see:** `Meta › Supersedes: meta.supersedes must be sha256:<64hex>/null (OMV-E010)`

**What it means:** `meta.supersedes` records the hash of the *prior* payload when
you re-embed a corrected version (so readers know this replaces an earlier one).
It has to be either empty (`null`) or the exact form `sha256:` followed by 64 hex
characters. A truncated or made-up value fails.

**How to fix:** for a brand-new OM there is no prior version - set it to `null`
or delete it. The tooling fills this in automatically when you re-embed a
correction, so you rarely type it by hand.

*(Spec rule `OM-ERR-013`.)*

---

# WARNINGS (these never block - they're deal-math heads-ups)

Everything below is advisory. **You can embed with any of these present.** Each
one means "two figures you entered disagree with each other - please
double-check." A warning is right to keep if you *intend* the mismatch (openOM
uses small tolerances, so tiny rounding differences won't trip them). The code
is shown in parentheses at the end of each real message; below we lead with plain
English and de-emphasize the code.

### The money / valuation checks

**Cap rate doesn't match NOI ÷ price** *(`OMW-W010`)*
The cap rate you typed doesn't equal your NOI divided by your asking price.
*Example:* NOI `115,625`, price `1,850,000` → that implies a **6.25%** cap
(`0.0625`), but you entered `0.07`. *Fix:* correct whichever of the three is
wrong. If all three are genuinely as stated, ignore it. *(Tolerance: 0.005
absolute.)*

**Price-per-SF doesn't match price ÷ building size** *(`OMW-W011`)*
Your stated `pricePerSF` doesn't equal asking price ÷ building square footage.
*Fix:* recheck the price, the SF, or the per-SF figure. *(Tolerance: 1%.)*

**Cap rate looks implausible** *(`OMW-W013`)*
The cap rate is outside the sanity band of **2%–20%** (`0.02`–`0.20`). This most
often means you fell into the decimal trap the *other* way (typed `0.000625`) or
entered a percentage as a whole number that slipped past. *Fix:* confirm it's a
decimal fraction in a normal range. A genuinely unusual cap is fine to keep.

**A dollar or size figure is zero or negative** *(`OMW-W014`)*
Asking price, NOI, or building SF came in at `0` or below. *Fix:* almost always a
typo or a blank that got read as zero - put in the real number.

### The rent-schedule checks

**Year-1 rent doesn't match the in-place NOI** *(`OMW-W020`)*
You marked the NOI as `in-place`, but the first year's annual rent in your rent
schedule is a different number. For a single-tenant net-lease deal these usually
match. *Example:* NOI `115,625` but year-1 rent `120,000`. *Fix:* reconcile the
two, or ignore if there's a real reason (e.g. expenses, multi-tenant). *(1%.)*

**Gap between rent periods** *(`OMW-W021`)* - one period starts more than a day
after the previous one ended. *Fix:* check for a missing period or a wrong date.

**Overlapping rent periods** *(`OMW-W022`)* - a period starts on or before the
previous one ended. *Fix:* fix the start/end dates so periods don't overlap.

**Escalation % doesn't match the actual rent step** *(`OMW-W023`)*
The `escalationFromPrior` you entered (say 3%) doesn't match the real jump from
the prior year's rent to this one. *Fix:* recompute the bump or correct the rent.
*(0.005.)*

**Rent-per-SF doesn't match annual rent ÷ building size** *(`OMW-W024`)* - same
idea as W011 but per rent period. *Fix:* recheck the per-SF figure. *(1%.)*

**Monthly rent doesn't match annual ÷ 12** *(`OMW-W025`)* *Fix:* one of the two
is off. *(1%.)*

**A rent period falls outside the lease term** *(`OMW-W026`)* - a period starts
before the lease commences or ends after it expires. *Fix:* correct the period
dates or the lease dates.

### The date / term checks

**Stated remaining term doesn't match the dates** *(`OMW-W030`)* - the
`remainingTermMonths` you typed doesn't match (expiration − the as-of date).
*Fix:* recompute months remaining. *(±31 days.)*

**Stated total term doesn't match the dates** *(`OMW-W031`)* - `termMonths`
doesn't match (expiration − commencement). *Fix:* recompute the term. *(±31 days.)*

**Assertion date is in the future** *(`OMW-W032`)* - the `assertedDate` is later
than the date you're processing on. *Fix:* usually a typo in the year/month.
*(Only appears when a processing date is supplied.)*

**NOI "as of" date is after the assertion date** *(`OMW-W033`)* - you're
asserting today about an NOI dated later than today. *Fix:* correct whichever date
is wrong.

**Lease expires on or before it starts** *(`OMW-W034`)* - expiration is not after
commencement. *Fix:* the dates are swapped or mistyped.

### The lease-type checks

**Net lease, but the landlord is shown paying pass-throughs** *(`OMW-W040`)*
You marked the lease `NN`, `NNN`, or `absolute-net` (tenant pays), but the
landlord-responsibilities list has the landlord covering taxes, insurance, or
CAM. *Fix:* if it's truly net, uncheck those; if the landlord really pays them,
the lease type may be wrong.

**Lease type contradicts the responsibility list** *(`OMW-W041`)* - e.g. a
gross/modified-gross lease with *no* landlord responsibilities recorded, or an
absolute-net lease where the landlord bears roof/structure/parking/HVAC. *Fix:*
make the lease type and the responsibilities agree.

### The provenance / re-embed checks

**This re-embed supersedes an identical copy** *(`OMW-W050`)* - the "supersedes"
pointer points at a payload byte-identical to this one (a no-op re-embed). *Fix:*
harmless; usually means nothing actually changed.

**The published version online is newer than this file** *(`OMW-W051`)* - the
same-domain mirror carries a genuinely newer assertion, so this embedded copy is
**stale/superseded** (not tampered). *Fix:* re-download or re-embed the current
version. The badge is kept - this is a freshness notice, not a failure.

**The source domain shows different data** *(`OMW-W052`)* - the same-domain
mirror serves different, non-superseding figures. *Fix:* investigate which is
correct; the mirror and the embedded copy have drifted.

**A rent line is tagged "verified" but nothing backs it** *(`OMW-W060`)* - a rent
period's `source` is `verified`, but openOM 0.1 carries no verification metadata
to support that claim. *Fix:* use `asserted` (your stated figure) or `extracted`
unless you have real corroboration.

**Currency left blank on a non-US property** *(`OMW-W061`)* - the address is
outside the US but no currency was set, so USD was assumed and is probably wrong.
*Fix:* set `currency` to the right ISO code (e.g. `EUR`, `GBP`, `CAD`).

---

# INFO (just context - nothing to fix)

- **`OMI-I001` - Currency assumed USD.** You left currency blank, so USD was
  used. Perfectly fine for US deals.
- **`OMI-I002` - A rent line had no source tag, assumed "asserted."** Absent =
  "this is the broker's stated figure," which is the normal default.
- **`OMI-I003` - A cross-check was skipped.** openOM wanted to check something
  (say cap rate vs NOI/price) but a needed input was missing, so it skipped that
  check rather than guess. Fill in the missing field if you want the check to run.

---

## Quick recap

- **Errors (`OMV-E###`) block. Warnings (`OMW-W###`) and info (`OMI-I###`) never do.**
- **Blocked = at least one error.** Fix the `E` codes; you can ship with `W` codes.
- **Cap rate is a decimal: 6.25% = `0.0625`.** This single rule is behind most
  "all validation errors" moments.
- **Warnings check your numbers against *each other*, never against the market.**
  openOM checks internal consistency and provenance - never truth.
- **Not a developer?** Skip the file-editing entirely and use the guided form at
  <https://openom.app/embed/>, which prevents most of these before they happen.
