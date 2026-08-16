/**
 * Transport/parse-level rejection codes (`OM-IO-*`).
 *
 * Spec: §C.1 [OM-CANON-009/010/013/014], §J. These are distinct from the §H
 * schema/consistency codes (`OMV-E###` / `OMW-W###`): an `OM-IO-*` error means
 * the input could not be canonicalized/parsed at all, so no hash or schema
 * verdict is meaningful.
 */
export type OmIoCode =
  | "OM-IO-NUMRANGE" // non-representable or non-finite number ([OM-CANON-013/014])
  | "OM-IO-STRUCTURE" // structural precondition failed ([OM-CANON-010])
  | "OM-IO-BADUTF8" // unpaired surrogate / malformed Unicode ([OM-CANON-010])
  | "OM-IO-DUPKEY" // duplicate member name ([OM-CANON-009])
  | "OM-IO-BOMB"; // input exceeds the size cap (§J [OM-SEC-002])

export class OmIoError extends Error {
  readonly code: OmIoCode;

  constructor(code: OmIoCode, message: string) {
    super(message);
    this.name = "OmIoError";
    this.code = code;
  }
}
