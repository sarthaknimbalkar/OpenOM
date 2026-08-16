import { OmIoError } from "./errors.js";

/** Max nesting depth for a payload (§J JSON-hardening guard). */
const MAX_DEPTH = 64;

/**
 * Default maximum payload size in bytes (§J [OM-SEC-002]). Payloads are ~2–5 KB
 * in practice; the 5 MiB cap is a generous bomb guard, overridable per call.
 */
export const DEFAULT_MAX_PAYLOAD_BYTES = 5 * 1024 * 1024;

/** Options for {@link parsePayload}. */
export interface ParseOptions {
  /** Reject input larger than this many UTF-8 bytes. Default 5 MiB. */
  readonly maxBytes?: number;
}

/** Lone (unpaired) UTF-16 surrogate — high without low, or low without high. */
const LONE_SURROGATE =
  /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/;

/**
 * Parse a payload from raw JSON text or UTF-8 bytes with the §C/§J hardening
 * that `JSON.parse` alone cannot provide: malformed-UTF-8 and unpaired-
 * surrogate rejection ([OM-CANON-010], OM-IO-BADUTF8), duplicate member-name
 * rejection compared after NFC ([OM-CANON-009], OM-IO-DUPKEY), a top-level
 * object precondition ([OM-CANON-010], OM-IO-STRUCTURE), and a depth guard.
 *
 * Does NOT re-normalize string values — a Consumer hashes bytes as received
 * ([OM-CANON-008]); NFC here is used only to compare key names for duplicates.
 */
export function parsePayload(
  input: string | Uint8Array,
  options: ParseOptions = {},
): Record<string, unknown> {
  const maxBytes = options.maxBytes ?? DEFAULT_MAX_PAYLOAD_BYTES;
  const byteLength =
    typeof input === "string" ? new TextEncoder().encode(input).length : input.byteLength;
  if (byteLength > maxBytes) {
    throw new OmIoError(
      "OM-IO-BOMB",
      `payload is ${byteLength} bytes, exceeding the ${maxBytes}-byte cap`,
    );
  }

  const text = typeof input === "string" ? input : decodeUtf8(input);

  assertNoDuplicateKeys(text);

  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch (e) {
    throw new OmIoError("OM-IO-STRUCTURE", `invalid JSON: ${(e as Error).message}`);
  }

  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new OmIoError(
      "OM-IO-STRUCTURE",
      "payload must be a JSON object (not an array, scalar, or null)",
    );
  }

  assertWellFormedStrings(value, 0);
  return value as Record<string, unknown>;
}

/** Decode UTF-8 bytes, rejecting malformed sequences ([OM-CANON-010]). */
function decodeUtf8(bytes: Uint8Array): string {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new OmIoError("OM-IO-BADUTF8", "input is not well-formed UTF-8");
  }
}

/**
 * Recursively reject any string value or member name containing a lone
 * surrogate — such strings survive `JSON.parse` (e.g. from a `\uD83D` escape)
 * but are not well-formed Unicode ([OM-CANON-010]).
 */
function assertWellFormedStrings(value: unknown, depth: number): void {
  if (depth > MAX_DEPTH) {
    throw new OmIoError("OM-IO-STRUCTURE", `payload nesting exceeds ${MAX_DEPTH}`);
  }
  if (typeof value === "string") {
    if (LONE_SURROGATE.test(value)) {
      throw new OmIoError("OM-IO-BADUTF8", "string contains an unpaired surrogate");
    }
    return;
  }
  if (Array.isArray(value)) {
    for (const el of value) assertWellFormedStrings(el, depth + 1);
    return;
  }
  if (value !== null && typeof value === "object") {
    for (const [key, val] of Object.entries(value)) {
      if (LONE_SURROGATE.test(key)) {
        throw new OmIoError("OM-IO-BADUTF8", "member name contains an unpaired surrogate");
      }
      assertWellFormedStrings(val, depth + 1);
    }
  }
}

/**
 * Scan the raw text for duplicate member names within the same object,
 * comparing names after NFC ([OM-CANON-009]). A member name is a string token
 * immediately followed by `:`. Repeated names across sibling objects are fine.
 */
function assertNoDuplicateKeys(text: string): void {
  const seenStack: Array<Set<string>> = [];
  let i = 0;
  const n = text.length;

  while (i < n) {
    const ch = text[i];
    if (ch === "{") {
      seenStack.push(new Set());
      i++;
    } else if (ch === "}") {
      seenStack.pop();
      i++;
    } else if (ch === "[") {
      // Push a non-object frame so a `:` cannot mis-attribute to an outer object.
      seenStack.push(new Set());
      i++;
    } else if (ch === "]") {
      seenStack.pop();
      i++;
    } else if (ch === '"') {
      const end = scanStringToken(text, i);
      const raw = text.slice(i, end); // includes surrounding quotes
      i = end;
      const next = skipWhitespace(text, i);
      if (text[next] === ":") {
        // This string is a member name in the current (innermost) object.
        const frame = seenStack[seenStack.length - 1];
        if (frame) {
          const name = decodeKey(raw).normalize("NFC");
          if (frame.has(name)) {
            throw new OmIoError("OM-IO-DUPKEY", `duplicate member name: ${name}`);
          }
          frame.add(name);
        }
      }
    } else if (ch === "-" || (ch !== undefined && ch >= "0" && ch <= "9")) {
      // A number token starts here (strings are consumed above, so any digit
      // or leading '-' at this level begins a JSON number value).
      i = scanAndCheckNumber(text, i);
    } else {
      i++;
    }
  }
}

/**
 * Read a JSON number token starting at `start`, enforce §C.2 representability
 * ([OM-CANON-013/014]), and return the index just past it.
 *
 * An integer-form token (digits only, no `.`/`e`) whose value is not a safe
 * integer denotes a magnitude binary64 rounds silently — a data corruption, so
 * rejected with OM-IO-NUMRANGE. Any token that overflows to a non-finite value
 * (e.g. `1e309`) is rejected too. Float/exponent forms within range (e.g.
 * `1e21`, `0.0625`) are accepted; their canonicalization is defined ([OM-CANON-015]).
 */
function scanAndCheckNumber(text: string, start: number): number {
  let i = start;
  const n = text.length;
  while (i < n) {
    const c = text[i]!;
    if ((c >= "0" && c <= "9") || c === "-" || c === "+" || c === "." || c === "e" || c === "E") {
      i++;
    } else {
      break;
    }
  }
  const token = text.slice(start, i);
  const value = Number(token);
  if (!Number.isFinite(value)) {
    throw new OmIoError("OM-IO-NUMRANGE", `number token is not finite: ${token}`);
  }
  // Value-based (not token-form) — matches the Python core and canonicalize.ts: any
  // integer-valued number beyond 2^53-1 is rejected, whether written 1000...0 or 1e21.
  if (Number.isInteger(value) && !Number.isSafeInteger(value)) {
    throw new OmIoError(
      "OM-IO-NUMRANGE",
      `integer value exceeds safe-integer range (2^53-1): ${token}`,
    );
  }
  return i;
}

/** Return the index just past the closing quote of a JSON string starting at `start`. */
function scanStringToken(text: string, start: number): number {
  let i = start + 1;
  const n = text.length;
  while (i < n) {
    const ch = text[i];
    if (ch === "\\") {
      i += 2; // skip the escaped char
      continue;
    }
    if (ch === '"') {
      return i + 1;
    }
    i++;
  }
  throw new OmIoError("OM-IO-STRUCTURE", "unterminated string in JSON");
}

function skipWhitespace(text: string, start: number): number {
  let i = start;
  while (i < text.length && (text[i] === " " || text[i] === "\t" || text[i] === "\n" || text[i] === "\r")) {
    i++;
  }
  return i;
}

/** Decode a raw quoted JSON string token (with escapes) into its string value. */
function decodeKey(rawQuoted: string): string {
  try {
    return JSON.parse(rawQuoted) as string;
  } catch {
    throw new OmIoError("OM-IO-STRUCTURE", "malformed member name");
  }
}
