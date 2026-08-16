import canonicalizeRfc8785 from "canonicalize";
import { OmIoError } from "./errors.js";

/**
 * Reject non-finite numbers ([OM-CANON-014]) with OM-IO-NUMRANGE.
 *
 * At the VALUE level every finite double is exactly representable and has a
 * well-defined ECMAScript serialization — including large magnitudes such as
 * `1e21` (canonical `1e+21`, [OM-CANON-015]) — so only `NaN`/`±Infinity` are
 * rejected here. Silent integer-precision loss ([OM-CANON-013]) is a property
 * of the SOURCE TOKEN, not of an already-parsed double, so it is caught at the
 * parse boundary (parse.ts), not here.
 */
function assertFiniteNumbers(value: unknown): void {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new OmIoError("OM-IO-NUMRANGE", `non-finite number: ${value}`);
    }
    return;
  }
  if (Array.isArray(value)) {
    for (const el of value) assertFiniteNumbers(el);
    return;
  }
  if (value !== null && typeof value === "object") {
    for (const val of Object.values(value)) assertFiniteNumbers(val);
  }
}

/**
 * Recursively NFC-normalize every JSON string value and object member name.
 *
 * Spec: §C.1 [OM-CANON-008]. RFC 8785 performs no Unicode normalization, so
 * openOM mandates NFC as a preprocessing step on the Producer (authoring)
 * path. This is intentionally NOT applied on the Consumer verification path,
 * which hashes bytes exactly as received ([OM-CANON-008]).
 */
function normalizeNfc(value: unknown): unknown {
  if (typeof value === "string") {
    return value.normalize("NFC");
  }
  if (Array.isArray(value)) {
    return value.map(normalizeNfc);
  }
  if (value !== null && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(value)) {
      out[key.normalize("NFC")] = normalizeNfc(val);
    }
    return out;
  }
  return value;
}

/**
 * Serialize a JSON value to RFC 8785 (JCS) canonical UTF-8 bytes.
 *
 * Spec: §C [OM-CANON-001..002], [OM-CANON-008], [OM-CANON-011..015]. UTF-8,
 * no BOM, NFC-normalized, object keys sorted by UTF-16 code unit, no
 * insignificant whitespace, ECMAScript number model. Delegates number/string/
 * sort formatting to a vetted RFC 8785 implementation rather than hand-rolling
 * it (§6 anti-fork guidance); NFC is applied here first ([OM-CANON-008]).
 */
export function canonicalize(value: unknown): Uint8Array {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new OmIoError(
      "OM-IO-STRUCTURE",
      "payload must be a JSON object (not an array, scalar, or null)",
    );
  }
  assertFiniteNumbers(value);
  const jcs = canonicalizeRfc8785(normalizeNfc(value));
  if (jcs === undefined) {
    throw new OmIoError("OM-IO-STRUCTURE", "value is not serializable to JCS");
  }
  return new TextEncoder().encode(jcs);
}
