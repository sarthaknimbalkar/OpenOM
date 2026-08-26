import Ajv2020, { type ErrorObject, type ValidateFunction } from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import {
  type ConsistencyOptions,
  DEFAULT_TOLERANCES,
  type Tolerances,
  consistencyFindings,
} from "./consistency.js";
import { OM_SCHEMA } from "./schema.js";
import type { OmCode } from "./codes.js";

/** Validator version reported in the envelope ([OM-ERR-010]). */
const VALIDATOR_VERSION = "0.1.0";

/** A single validation Finding ([OM-ERR-007]). */
export interface Finding {
  readonly code: OmCode;
  readonly severity: "error" | "warning" | "info";
  /** RFC 6901 JSON Pointer into the payload; "" = whole document ([OM-ERR-008]). */
  readonly path: string;
  readonly message: string;
  readonly requirement?: string;
  readonly expected?: unknown;
  readonly actual?: unknown;
}

/** The `om_validate` report envelope ([OM-ERR-010]). */
export interface ValidationReport {
  readonly specVersion: string;
  readonly validatorVersion: string;
  readonly errors: Finding[];
  readonly warnings: Finding[];
  readonly info: Finding[];
  readonly summary: { errorCount: number; warningCount: number; infoCount: number };
  /** MUST equal errorCount > 0 ([OM-ERR-004]). */
  readonly blocked: boolean;
}

const SEVERITY_RANK = { error: 0, warning: 1, info: 2 } as const;

/**
 * A compiled schema validator with ajv's error shape. Supplied precompiled (ajv standalone codegen)
 * by callers that cannot run ajv's runtime `new Function` compile - notably the MV3 consumer bundle,
 * whose CSP forbids `unsafe-eval` ([OM-DoD-006]). Same schema, same error objects, zero eval.
 */
export interface PrecompiledValidate {
  (data: unknown): boolean;
  errors?: ErrorObject[] | null;
}

/**
 * Validate a payload against the openOM JSON Schema - the schema-error tier
 * (VAL-01, §H) AND the consistency tier (`OMW-W###`) + info tier (`OMI-I###`). Errors
 * block `om_embed`; warnings/info never block. The schema is injected so
 * `/js` stays free of a hardcoded `spec/` path and the function stays pure.
 *
 * ajv findings are mapped to the stable §H codes: a populated `meta.signature`
 * → OMV-E003, a missing `noiType`/`noiAsOfDate` under `deal` → OMV-E002, a
 * malformed `meta.supersedes` → OMV-E010, everything else → OMV-E001.
 *
 * `schema` defaults to the bundled `OM_SCHEMA` ([Bl1]) so `validatePayload(payload)` works from a
 * fresh install with no caller-vendored schema - matching the Python core's auto-loading default
 * ([Ma21]). Pass an explicit schema (or a precompiled `options.validate`) to override.
 */
export function validatePayload(
  payload: unknown,
  schema: Record<string, unknown> = OM_SCHEMA,
  options: ConsistencyOptions & { tolerances?: Tolerances; validate?: PrecompiledValidate } = {},
): ValidationReport {
  // Prefer an injected eval-free validator (MV3/CSP); fall back to runtime ajv compile off-browser.
  const validate = options.validate ?? compile(schema);
  const errors: Finding[] = [];

  if (!validate(payload)) {
    const seen = new Set<string>();
    for (const err of validate.errors ?? []) {
      const finding = mapError(err);
      const dedupKey = `${finding.code}\u0000${finding.path}`;
      if (!seen.has(dedupKey)) {
        seen.add(dedupKey);
        errors.push(finding);
      }
    }
  }

  // Out-of-safe-range numbers: the schema accepts any integer, but canonicalization (OM-CANON-013)
  // rejects an integer-valued number with |v| > 2^53-1, so embed would throw after a green validate.
  // Flag it here too, with the SAME test canonicalize uses, so validate and embed agree.
  for (const [path, value] of iterNumbers(payload, "")) {
    if (!Number.isFinite(value)) {
      // NaN / Infinity: canonicalization rejects these, so validate must too (else green-validate
      // then failed-embed). Parity with the Python core's finiteness guard.
      errors.push({
        code: "OMV-E011",
        severity: "error",
        path,
        message: `non-finite number; embed would reject it: ${value}`,
        requirement: "OM-CANON-013",
      });
    } else if (Number.isInteger(value) && !Number.isSafeInteger(value)) {
      errors.push({
        code: "OMV-E011",
        severity: "error",
        path,
        message: `integer value exceeds the safe range (2^53-1); embed would reject it: ${value}`,
        requirement: "OM-CANON-013",
      });
    }
  }

  // Shared normal form (parity with the Python core): drop a generic OMV-E001 whose path is a strict
  // ancestor of another error's path, so a bubbled-up parent (/deal) or root ("") error doesn't
  // clutter the list when a specific error already sits deeper. Specific codes are never dropped; the
  // root "" survives only when it is the sole error.
  const paths = errors.map((e) => e.path);
  const isAncestor = (a: string, b: string): boolean =>
    a !== b && (a === "" || b.startsWith(a + "/"));
  const deduped = errors.filter(
    (e) => !(e.code === "OMV-E001" && paths.some((p) => isAncestor(e.path, p))),
  );
  errors.length = 0;
  errors.push(...deduped);
  errors.sort(compareFindings);

  const isObject = payload !== null && typeof payload === "object" && !Array.isArray(payload);
  const { warnings, info } = isObject
    ? consistencyFindings(
        payload as Record<string, unknown>,
        options.tolerances ?? DEFAULT_TOLERANCES,
        options,
      )
    : { warnings: [] as Finding[], info: [] as Finding[] };
  warnings.sort(compareFindings);
  info.sort(compareFindings);

  return {
    specVersion: schemaSpecVersion(schema),
    validatorVersion: VALIDATOR_VERSION,
    errors,
    warnings,
    info,
    summary: { errorCount: errors.length, warningCount: warnings.length, infoCount: info.length },
    blocked: errors.length > 0,
  };
}

/** [Po5] The report's specVersion is the schema's own `properties.specVersion.const`, not a literal,
 *  so it can never disagree with the schema that was validated against. Falls back to "0.1". */
function schemaSpecVersion(schema: Record<string, unknown>): string {
  const props = (schema.properties ?? {}) as Record<string, unknown>;
  const sv = (props.specVersion ?? {}) as Record<string, unknown>;
  return typeof sv.const === "string" ? sv.const : "0.1";
}

/** Compile a schema with 2020-12 support and `format` (date) validation. */
function compile(schema: Record<string, unknown>): ValidateFunction {
  // strict:false tolerates the schema's non-standard "comment" annotation.
  const ajv = new Ajv2020({ allErrors: true, strict: false });
  // mode: "full" -> calendar-strict date validation, matching Track A's jsonschema
  // format-checker (rejects impossible-but-regex-valid dates like 2026-02-30). Cross-impl
  // parity for the schema-tier format assertion ([OM-VAL-002]).
  addFormats(ajv, { mode: "full" });
  return ajv.compile(schema);
}

/** Map one ajv error to a stable §H Finding. */
function mapError(err: ErrorObject): Finding {
  const path = jsonPointerFor(err);

  // #117: signature is null OR the reserved {alg,keyId,value} shape. A malformed value fails the
  // schema oneOf - every resulting error sits at or under /meta/signature - and maps to one OMV-E003
  // (deduped by code+path). A well-formed signature produces no error and is accepted (then ignored).
  if (err.instancePath.startsWith("/meta/signature")) {
    return {
      code: "OMV-E003",
      severity: "error",
      path: "/meta/signature",
      message: "meta.signature must be null or the reserved {alg,keyId,value} shape",
      requirement: "OM-ERR-090",
    };
  }

  if (err.keyword === "required" && err.instancePath === "/deal" && isNoiRequirement(err)) {
    return {
      code: "OMV-E002",
      severity: "error",
      path: `/deal/${(err.params as { missingProperty: string }).missingProperty}`,
      message: "noiType and noiAsOfDate are REQUIRED whenever noi is present",
      requirement: "OM-DD-003",
    };
  }

  if (err.instancePath === "/meta/supersedes") {
    return {
      code: "OMV-E010",
      severity: "error",
      path: "/meta/supersedes",
      message: "meta.supersedes must be a sha256:<64-hex> string or null",
      requirement: "OM-ERR-013",
    };
  }

  return {
    code: "OMV-E001",
    severity: "error",
    path,
    message: `schema violation (${err.keyword}): ${err.message ?? "invalid"}`,
    requirement: "OM-DD-001",
  };
}

/** Yield [json-pointer, number] for every numeric leaf, depth-first. Booleans are not numbers in JS,
 * so they're naturally excluded; the path style matches jsonPointerFor (unescaped '/'-joined). */
function* iterNumbers(node: unknown, path: string): Generator<[string, number]> {
  if (typeof node === "number") {
    yield [path, node];
  } else if (Array.isArray(node)) {
    for (let i = 0; i < node.length; i++) yield* iterNumbers(node[i], `${path}/${i}`);
  } else if (node !== null && typeof node === "object") {
    for (const [key, value] of Object.entries(node)) yield* iterNumbers(value, `${path}/${key}`);
  }
}

function isNoiRequirement(err: ErrorObject): boolean {
  const missing = (err.params as { missingProperty?: string }).missingProperty;
  return missing === "noiType" || missing === "noiAsOfDate";
}

/** Build the RFC 6901 pointer, extending `required` errors with the missing key. */
function jsonPointerFor(err: ErrorObject): string {
  if (err.keyword === "required") {
    const missing = (err.params as { missingProperty?: string }).missingProperty;
    if (missing) return `${err.instancePath}/${missing}`;
  }
  return err.instancePath;
}

/** Deterministic order: severity, then code asc, then path as a byte string ([OM-ERR-009]). */
function compareFindings(a: Finding, b: Finding): number {
  if (SEVERITY_RANK[a.severity] !== SEVERITY_RANK[b.severity]) {
    return SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity];
  }
  if (a.code !== b.code) return a.code < b.code ? -1 : 1;
  if (a.path !== b.path) return a.path < b.path ? -1 : 1;
  return 0;
}
