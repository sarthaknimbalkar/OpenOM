// Fold an extraction result into the M5b-1 draft: each field via setField, its evidence via
// setEvidence. Rent-schedule periods keep whatever source the extractor set ("extracted"); the review
// gate promotes them to "asserted". Pure — the result lands in the review panel exactly like hand
// entry, so the human assertion gate is unchanged ([OM-EXTP-003]).
import { type Draft, setField, setEvidence } from "../draft.js";
import type { ExtractionResult } from "./types.js";

export function applyExtraction(draft: Draft, result: ExtractionResult): Draft {
  let d = draft;
  for (const f of result.fields) {
    d = setField(d, f.path, f.value);
    if (f.evidence) d = setEvidence(d, f.path, f.evidence);
  }
  return d;
}
