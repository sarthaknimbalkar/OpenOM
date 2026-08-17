// Fold an extraction result into the M5b-1 draft: each field via setField, its evidence via
// setEvidence. Rent-schedule periods keep whatever source the extractor set ("extracted"); the review
// gate promotes them to "asserted". Pure — the result lands in the review panel exactly like hand
// entry, so the human assertion gate is unchanged ([OM-EXTP-003]).
import { type Draft, setField, setEvidence } from "../draft.js";
import type { ExtractionResult } from "./types.js";

/**
 * Paths a model may NEVER fill ([#90]): the human sets identity + assertion facts at the review gate
 * (assertedBy/assertedDate/noiType/noiAsOfDate — mapping-guide), and finalize owns the system fields
 * (@context/@type/specVersion/meta). Letting extraction write these would pre-seed identity/consent
 * from the document ([OM-EXTP-003] — confidence is never consent). Such fields are dropped, not applied.
 */
function isHumanOrSystemPath(path: string): boolean {
  return (
    path === "/assertedDate" ||
    path === "/specVersion" ||
    path === "/@context" ||
    path === "/@type" ||
    path === "/deal/noiType" ||
    path === "/deal/noiAsOfDate" ||
    path.startsWith("/assertedBy") ||
    path.startsWith("/meta")
  );
}

export function applyExtraction(draft: Draft, result: ExtractionResult): Draft {
  let d = draft;
  for (const f of result.fields) {
    if (isHumanOrSystemPath(f.path)) continue; // extraction cannot pre-fill identity/assertion/system
    d = setField(d, f.path, f.value);
    if (f.evidence) d = setEvidence(d, f.path, f.evidence);
  }
  return d;
}
