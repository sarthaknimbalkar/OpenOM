import canonicalizeRfc8785 from "canonicalize";
import { OmIoError } from "./errors.js";

/** Max nesting depth (§J) — matches the Python core and parse.ts for cross-impl parity. */
const MAX_DEPTH = 64;

/** Lone (unpaired) UTF-16 surrogate — high without low, or low without high. */
const LONE_SURROGATE =
  /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/;

/**
 * Recursively NFC-normalize and enforce the §C rejection contract — identical to the Python
 * core's canonicalize (the anti-fork guarantee extends to REJECTIONS, not just the happy path):
 *
 * - non-finite numbers, and integer-valued numbers with |v| > 2^53-1 → OM-IO-NUMRANGE
 *   ([OM-CANON-013/014]); this rejects 1e20/1e21 etc., which no CRE figure approaches.
 * - lone surrogates in string values or member names → OM-IO-BADUTF8 ([OM-CANON-010]).
 * - member names that collide after NFC → OM-IO-DUPKEY ([OM-CANON-009]).
 * - nesting deeper than MAX_DEPTH → OM-IO-STRUCTURE (§J).
 *
 * NFC is applied on this Producer path only; the Consumer verification path hashes bytes as
 * received ([OM-CANON-008]).
 */
function prepare(value: unknown, depth: number): unknown {
  if (depth > MAX_DEPTH) {
    throw new OmIoError("OM-IO-STRUCTURE", `nesting exceeds ${MAX_DEPTH}`);
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new OmIoError("OM-IO-NUMRANGE", `non-finite number: ${value}`);
    }
    if (Number.isInteger(value) && !Number.isSafeInteger(value)) {
      throw new OmIoError("OM-IO-NUMRANGE", `integer value exceeds 2^53-1: ${value}`);
    }
    return value;
  }
  if (typeof value === "string") {
    if (LONE_SURROGATE.test(value)) {
      throw new OmIoError("OM-IO-BADUTF8", "string contains an unpaired surrogate");
    }
    return value.normalize("NFC");
  }
  if (Array.isArray(value)) {
    return value.map((el) => prepare(el, depth + 1));
  }
  if (value !== null && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(value)) {
      if (LONE_SURROGATE.test(key)) {
        throw new OmIoError("OM-IO-BADUTF8", "member name contains an unpaired surrogate");
      }
      const nkey = key.normalize("NFC");
      if (Object.prototype.hasOwnProperty.call(out, nkey)) {
        throw new OmIoError("OM-IO-DUPKEY", `duplicate member name after NFC: ${nkey}`);
      }
      out[nkey] = prepare(val, depth + 1);
    }
    return out;
  }
  return value; // null | boolean
}

/**
 * Serialize a JSON value to RFC 8785 (JCS) canonical UTF-8 bytes.
 *
 * Spec: §C [OM-CANON-001..002], [OM-CANON-008..015]. UTF-8, no BOM, NFC-normalized, keys sorted
 * by UTF-16 code unit, no insignificant whitespace, ECMAScript number model. Number/sort/escape
 * formatting is delegated to a vetted RFC 8785 implementation; the §C preprocessing +
 * rejection contract is applied here first (see {@link prepare}).
 */
export function canonicalize(value: unknown): Uint8Array {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new OmIoError(
      "OM-IO-STRUCTURE",
      "payload must be a JSON object (not an array, scalar, or null)",
    );
  }
  const jcs = canonicalizeRfc8785(prepare(value, 0));
  if (jcs === undefined) {
    throw new OmIoError("OM-IO-STRUCTURE", "value is not serializable to JCS");
  }
  return new TextEncoder().encode(jcs);
}
