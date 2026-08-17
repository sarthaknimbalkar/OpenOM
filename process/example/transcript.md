# Transcript — openom-author on `sample-om.pdf`

A recorded run of the `/process` playbook (Claude, via the `openom-author` skill) driving the
deterministic openOM MCP tools over the synthetic demo OM `sample-om.pdf`, ending at the review
gate. This is the Claude half of the [OM-DoD-005] evidence; the produced payload is
`expected-payload.json`, which the CI gate (`spec/tests/test_process_example.py`) validates.

> The non-Claude MCP-client half of the gate (a broker's own AI via an MCP connector following
> `agent-instructions.md`) is adoption-deferred — the client-agnostic instructions are authored,
> the live run is tracked as adoption, not faked here.

## 1. Classify — `om_inspect`

```
→ om_inspect({"path": "process/example/sample-om.pdf"})
← { "class": "native", "pages": 1, "textCoverage": ~1.0, "payloadPresent": false }
```
Native text; no existing payload → a first embed (not a reprice). Proceed to text extraction.

## 2. Gather — `om_extract_text`

```
→ om_extract_text({"path": ".../sample-om.pdf"})
← text (excerpt):
    FINANCIAL SUMMARY
    Offering Price:        $2,500,000
    Cap Rate:              5.75%
    Net Operating Income:  $143,750 (in-place, as of 05/31/2026)
    Price / SF:            $416.67
    Status:                Active
    PROPERTY  — 500 Example Blvd, Testville, TX 75000 · APN R000000 · +/- 6,000 SF · Year Built 2021
    LEASE ABSTRACT — Tenant: Placeholder Quick Service, LLC · Guarantor: Placeholder Brands Inc.
      (Corporate) · Lease Type: NNN (tenant pays taxes/insurance/CAM) · Term 06/01/2021-05/31/2031
    RENT SCHEDULE
      06/01/2021 - 05/31/2026    $143,750   $23.96   -
      06/01/2026 - 05/31/2031    $158,125   $26.35   10%
    Two (2) five-year renewal options remain.
```
(`truncated: false` — single page, no pagination needed. `om_extract_images` skipped: no figures
needed for the fields.)

## 3. Map — per `mapping-guide.md`

Transcribe, applying the unit/vocabulary rules: `5.75% → capRate 0.0575`; money as bare major
units; ISO dates; `leaseTypeAsserted "NNN"` with all `landlordResponsibilities` false (tenant pays);
rent periods `source: "extracted"`. Omitted (not stated in the OM): `geo`, `lotAcres`,
`yearRenovated`, `termMonths`, `remainingTermMonths`, `options` detail beyond the renewal note,
`monthlyRent`, `currency` (defaults USD). Draft rentPeriod `source` = `"extracted"`.

## 4. Validate & iterate — `om_validate`

```
→ om_validate(draft, schema)
← { ok: true, errors: [], warnings: [], info: ["OMI-I001"] }
```
Schema-clean and consistency-clean on the first pass — the transcribed numbers agree
(cap = 143750/2500000 = 0.0575; pricePerSF ≈ 2500000/6000; rentPSF ≈ annualRent/6000; escalation =
158125/143750 − 1 = 0.10; schedule contiguous within the term). `OMI-I001` is advisory only
(currency absent → USD assumed). No re-read needed.

## 5. Human review gate — the assertion moment

Presented the payload, the source line for each field, and the single info notice to the broker.
Broker (Dana Sample) confirmed the transcription against the OM and approved. On approval:
- `assertedBy` = the reviewing broker (Dana Sample / Placeholder Retail Advisors / TX 000000);
- `assertedDate` = 2026-08-17;
- `noiType`/`noiAsOfDate` confirmed (in-place / 2026-05-31);
- each rentPeriod `source` promoted `"extracted"` → `"asserted"`.

Result: `expected-payload.json`.

## 6. Embed (not run in this transcript)

With approval, `om_embed({"path": ".../sample-om.pdf"}, payload, assertedDate="2026-08-17")` would
write the embedded PDF (first embed → `meta.supersedes: null`). Left unrun here so the demo OM
stays payload-free for the gate's `test_sample_om_has_no_embedded_payload`.
