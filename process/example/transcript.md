# Transcript - openom-author on `sample-om.pdf`

A recorded run of the `/process` playbook (Claude, via the `openom-author` skill) driving the
deterministic openOM MCP tools over the synthetic demo OM `sample-om.pdf`, ending at the review
gate. This is the Claude half of the [OM-DoD-005] evidence; the produced payload is
`expected-payload.json`, which the CI gate (`spec/tests/test_process_example.py`) validates.

> The non-Claude MCP-client half of the gate (a broker's own AI via an MCP connector following
> `agent-instructions.md`) is adoption-deferred - the client-agnostic instructions are authored,
> the live run is tracked as adoption, not faked here.

## 1. Classify - `om_inspect`

```
→ om_inspect({"path": "process/example/sample-om.pdf"})
← { "class": "native", "pages": 1, "textCoverage": ~1.0, "payload": { "present": false } }
```
Native text; no existing payload → a first embed (not a reprice). Proceed to text extraction.

## 2. Gather - `om_extract_text`

```
→ om_extract_text({"path": ".../sample-om.pdf"})
← text (excerpt):
    FINANCIAL SUMMARY
    Offering Price:        $2,500,000
    Cap Rate:              5.75%
    Net Operating Income:  $143,750 (in-place, as of 05/31/2026)
    Price / SF:            $416.67
    Status:                Active
    PROPERTY  - 500 Example Blvd, Testville, TX 75000 · APN R000000 · +/- 6,000 SF · Year Built 2021
    LEASE ABSTRACT - Tenant: Placeholder Quick Service, LLC · Guarantor: Placeholder Brands Inc.
      (Corporate) · Lease Type: NNN (tenant pays taxes/insurance/CAM) · Term 06/01/2021-05/31/2031
    RENT SCHEDULE
      06/01/2021 - 05/31/2026    $143,750   $23.96   -
      06/01/2026 - 05/31/2031    $158,125   $26.35   10%
    Two (2) five-year renewal options remain.
```
(`truncated: false` - single page, no pagination needed. `om_extract_images` skipped: no figures
needed for the fields.)

## 3. Map - per `mapping-guide.md`

Transcribe, applying the unit/vocabulary rules: `5.75% → capRate 0.0575`; money as bare major
units; ISO dates; `leaseTypeAsserted "NNN"` with all `landlordResponsibilities` false (tenant pays);
rent periods `source: "extracted"`. Omitted (not stated in the OM): `geo`, `lotAcres`,
`yearRenovated`, `termMonths`, `remainingTermMonths`, `options` detail beyond the renewal note,
`monthlyRent`, `currency` (defaults USD). Draft rentPeriod `source` = `"extracted"`.

## 4. Validate & iterate - `om_validate`

```
→ om_validate(draft)
← { ok: true, errors: [], warnings: [], info: ["OMI-I001"] }
```
Schema-clean and consistency-clean on the first pass - the transcribed numbers agree
(cap = 143750/2500000 = 0.0575; pricePerSF ≈ 2500000/6000; rentPSF ≈ annualRent/6000; escalation =
158125/143750 − 1 = 0.10; schedule contiguous within the term). `OMI-I001` is advisory only
(currency absent → USD assumed). No re-read needed.

## 5. Human review gate - the assertion moment

Presented the payload, the source line for each field, and the single info notice to the broker.
Broker (Dana Sample) confirmed the transcription against the OM and approved. On approval:
- `assertedBy` = the reviewing broker (Dana Sample / Placeholder Retail Advisors / TX 000000);
- `assertedDate` = 2026-08-17;
- `noiType`/`noiAsOfDate` confirmed (in-place / 2026-05-31);
- each rentPeriod `source` promoted `"extracted"` → `"asserted"`.

Result: `expected-payload.json`.

## 6. Embed (not run in this transcript)

With approval, set `payload.assertedDate = "2026-08-17"` (and `assertedBy`) as fields, then
`om_embed({"path": ".../sample-om.pdf"}, payload)` would
write the embedded PDF (first embed → `meta.supersedes: null`). Left unrun here so the demo OM
stays payload-free for the gate's `test_sample_om_has_no_embedded_payload`.

## Appendix - the warning-iteration loop (a corrected mis-extraction)

The happy path above was clean on the first pass. The loop's real purpose is catching a bad
mapping. A representative first-pass slip on this same OM, and its correction:

```
# First pass (WRONG): transcribed "Cap Rate: 5.75%" verbatim.
deal.capRate = 5.75

→ om_validate(draft)
← warnings: ["OMW-W013"]   # capRate outside the plausibility band [0.02, 0.20]

# Re-read mapping-guide.md → "capRate is a decimal fraction: 6.25% → 0.0625". Re-examine the OM.
# Correct: 5.75% → 0.0575.
deal.capRate = 0.0575

→ om_validate(draft)
← warnings: []             # ties to NOI ÷ askingPrice = 143750 / 2500000 = 0.0575
```

The rule the loop enforces: **a warning means the extraction is probably wrong - re-read and fix,
never silence it.** `spec/tests/test_process_traps.py` machine-checks this and the other common
traps (schedule gap → `OMW-W021`, NNN-but-landlord-pays → `OMW-W040`, rentPSF mismatch →
`OMW-W024`, deal-math → `OMW-W010`/`W011`), each against the corrected warning-clean payload.

## Appendix - reprice (re-embed with a supersedes chain)

The common repeat operation is a price change on an already-embedded OM. The playbook reads the
prior payload, builds the new one, and links it:

```
→ om_read({"path": ".../embedded.pdf"})     # the previously embedded OM
← payload (askingPrice 2,500,000, …)         # prior payload; its hash is H_prev

# Repriced: askingPrice 2,400,000 → capRate 143750/2400000 = 0.0599, pricePerSF 400.00.
# Set fields on the payload: repriced.assertedDate="2026-09-01"; repriced.meta.supersedes = H_prev.
→ om_validate(repriced)                      ← warnings: []   # still ties (schema is built in)
→ om_embed({"path": ".../embedded.pdf"}, repriced)   # assertedDate is a payload field, not an arg
← a NEW PDF with exactly ONE om.json (replaced in place, not stacked) and
  meta.supersedes = H_prev - the audit chain to the superseded assertion.
```

`process/example/repriced-payload.json` is the committed after-state;
`spec/tests/test_process_reprice.py` proves the chain and the replace-not-stack guarantee.
