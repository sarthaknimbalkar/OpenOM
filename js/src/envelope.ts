// Receiver-side validation of a §Y webhook envelope ([#14], [OM-HOOK-002]) - the other half of the
// two-sided standard. A broker's receiver pairs this with verifyWebhookSignature (webhook.ts): verify
// the signature first, then validate the body shape. Kept in its own module (NOT webhook.ts) so ajv
// never leaks into the consumer popup bundle, which imports openom-js/webhook for signing only.
//
// ENVELOPE_SCHEMA is the source of truth for the validator; spec/webhook-envelope-0.1.schema.json is
// its published mirror. A drift test asserts they stay identical.
import Ajv2020, { type ErrorObject } from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { payloadHash } from "./hash.js";

export const ENVELOPE_SCHEMA = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  $id: "https://openom.app/spec/webhook-envelope-0.1.schema.json",
  title: "openOM webhook envelope 0.1",
  description:
    "The §Y change-notification webhook envelope a consumer POSTs to a broker-configured receiver ([OM-HOOK-002]). Signed per §Y (OpenOM-Signature); this schema validates the JSON body a receiver parses. Human-readable mirror is spec Part II §5b.",
  type: "object",
  required: [
    "envelopeVersion",
    "event",
    "id",
    "publishedAt",
    "sourceUrl",
    "specVersion",
    "payloadHash",
    "verification",
    "payload",
  ],
  additionalProperties: false,
  properties: {
    envelopeVersion: { const: "1" },
    event: { type: "string", minLength: 1, description: "e.g. om.payload.published, om.test.ping" },
    id: {
      type: "string",
      minLength: 1,
      description: "stable event id (== OpenOM-Event-Id, stable across retries)",
    },
    publishedAt: {
      type: "string",
      format: "date-time",
      description: "RFC 3339 UTC with a Z designator",
    },
    sourceUrl: { type: "string", minLength: 1 },
    specVersion: { const: "0.1" },
    payloadHash: {
      type: "string",
      pattern: "^sha256:[0-9a-f]{64}$",
      description:
        "The §C integrity hash of `payload`. JSON Schema cannot bind it to `payload`, so a receiver MUST recompute and compare (verifyEnvelopePayloadHash) after verifying the signature - a schema-valid envelope can still carry a mismatched hash ([OM-HOOK], #120).",
    },
    verification: {
      type: "object",
      required: ["hashValid", "originVerified", "signatureValid"],
      additionalProperties: false,
      properties: {
        hashValid: { type: ["boolean", "null"] },
        originVerified: { type: ["boolean", "null"] },
        signatureValid: { type: ["boolean", "null"] },
      },
    },
    payload: { type: "object" },
  },
} as const;

export interface EnvelopeValidation {
  valid: boolean;
  errors: string[];
}

let _validate: ((v: unknown) => boolean) & { errors?: ErrorObject[] | null };

function validator() {
  if (!_validate) {
    const ajv = new Ajv2020({ allErrors: true, strict: false });
    addFormats(ajv, { mode: "full" }); // calendar-strict date-time for publishedAt
    _validate = ajv.compile(ENVELOPE_SCHEMA as unknown as Record<string, unknown>);
  }
  return _validate;
}

/**
 * Verify the envelope's `payloadHash` actually binds its inline `payload` - i.e. it equals the §C
 * integrity hash of the payload ([OM-HOOK], #120). JSON Schema cannot express this cross-field
 * invariant, so a schema-valid envelope can still carry a mismatched hash; a receiver MUST run this
 * (after verifying the signature) before trusting `payloadHash`. Returns false on any shape error.
 */
export function verifyEnvelopePayloadHash(envelope: unknown): boolean {
  try {
    if (envelope === null || typeof envelope !== "object") return false;
    const { payload, payloadHash: claimed } = envelope as {
      payload?: unknown;
      payloadHash?: unknown;
    };
    if (typeof claimed !== "string") return false;
    if (payload === null || typeof payload !== "object" || Array.isArray(payload)) return false;
    return payloadHash(payload as Record<string, unknown>) === claimed;
  } catch {
    return false;
  }
}

/** Validate a parsed webhook-envelope object against the published §Y schema. */
export function validateEnvelope(value: unknown): EnvelopeValidation {
  const validate = validator();
  if (validate(value)) return { valid: true, errors: [] };
  const errors = (validate.errors ?? []).map(
    (e) => `${e.instancePath || "/"} ${e.message ?? "invalid"}`,
  );
  return { valid: false, errors };
}
