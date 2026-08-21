# Review-presentation contract

> What an extracting agent MUST surface to the human at the review gate before an embed. The review
> gate is the assertion moment (§7a, [OM-EXTP-003]): extraction output is a draft until a human
> reviews it against the source and approves. This contract is what "review" concretely means - for
> the playbook now, and for the M5b extension review panel later.

## The agent MUST present

1. **Per field - value + evidence + provenance.** For every field in the draft payload:
   - the payload path and the value (e.g. `deal.capRate = 0.0575`);
   - the **source evidence**: where in the OM it came from - page + the quoted text/table cell
     (e.g. p.1 "Cap Rate: 5.75%"). A field with no citable evidence MUST be flagged, not asserted;
   - the current **`source` tag** (`extracted` pre-approval; rentPeriods carry it explicitly).
2. **Omissions.** The fields the agent deliberately left out because the OM did not state them
   (never invented). The human may supply them or confirm the omission.
3. **Residual warnings.** Every remaining `OMW-W###` with its meaning and why it is still present
   (e.g. "rounding on rentPSF, within tolerance" or "unresolved - please check"). Warnings never
   block embed, but the human decides whether each is acceptable.
4. **Reprice diff (when re-embedding).** When a payload is already embedded, present a diff of the
   new payload vs the prior one: fields added / changed (old → new) / removed, the `assertedDate`
   bump, and the `meta.supersedes` link to the prior payload's hash. The human is approving a
   *change*, not a fresh assertion.

## On approval, the agent then

- sets `assertedBy` to the **reviewing broker** (broker / brokerage / license);
- sets `assertedDate` to today, and confirms `noiType` / `noiAsOfDate`;
- promotes each rentPeriod `source` `"extracted"` → `"asserted"`;
- only then calls `om_embed`.

## Hard rule

The agent MUST NOT approve on the human's behalf, pre-check the box, or embed without an explicit
human decision. No approval → no assertion → no embed. Extraction confidence, however high, is not
consent.
