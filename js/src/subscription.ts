// Webhook SUBSCRIPTION object ([B2], consumer audit #25) - the missing relationship-establishment
// half of §Y. The envelope (envelope.ts) is what a publisher POSTs; a subscription is what a
// consumer/portal registers with a publisher so it receives those POSTs: where to deliver, the
// per-(publisher,receiver) HMAC signing secret, an optional event filter, and an active flag.
//
// Provisioning is deliberately OUT-OF-BAND in 0.1 (a broker/publisher configures this object however
// they onboard a receiver - a form, an API, a config file); this schema standardizes the SHAPE so the
// secret exchange and event filter mean the same thing everywhere. SUBSCRIPTION_SCHEMA is the source
// of truth; spec/webhook-subscription-0.1.schema.json is its published mirror (a drift test locks them).
import Ajv2020, { type ErrorObject } from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

/** The events a subscription may filter on - only events the tooling actually emits ([#3]). Absent/
 * empty `events` = deliver all. The set is additive across 0.1.x as new events are defined+emitted. */
export const SUBSCRIPTION_EVENTS = ["om.payload.published", "om.test.ping"] as const;

export const SUBSCRIPTION_SCHEMA = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  $id: "https://openom.app/spec/webhook-subscription-0.1.schema.json",
  title: "openOM webhook subscription 0.1",
  description:
    "A change-notification subscription ([B2], §Y): the receiver a publisher delivers signed envelopes to, the per-(publisher,receiver) HMAC signing secret, an optional event filter, and an active flag. Provisioning is out-of-band in 0.1; this standardizes the object's shape. Human-readable mirror is spec Part II §5c.",
  type: "object",
  required: ["subscriptionVersion", "specVersion", "receiverUrl", "secret", "active"],
  additionalProperties: false,
  properties: {
    subscriptionVersion: { const: "1" },
    specVersion: { const: "0.1" },
    receiverUrl: {
      type: "string",
      pattern: "^https://",
      description:
        "HTTPS endpoint the publisher POSTs signed envelopes to (https required, no http).",
    },
    secret: {
      type: "string",
      minLength: 16,
      description:
        "The per-(publisher,receiver) HMAC signing secret (OpenOM-Signature). Exchanged out-of-band; MUST be unique per pair and MUST NOT be reused across receivers. >=16 chars.",
    },
    events: {
      type: "array",
      items: { enum: SUBSCRIPTION_EVENTS },
      uniqueItems: true,
      description: "Event filter; absent or empty = deliver all events.",
    },
    active: { type: "boolean", description: "Whether the publisher should currently deliver." },
    createdAt: { type: "string", format: "date-time", description: "RFC 3339 UTC (optional)." },
    description: { type: "string", description: "Human label for the subscription (optional)." },
  },
} as const;

export interface SubscriptionValidation {
  valid: boolean;
  errors: string[];
}

let _validate: ((v: unknown) => boolean) & { errors?: ErrorObject[] | null };

function validator() {
  if (!_validate) {
    const ajv = new Ajv2020({ allErrors: true, strict: false });
    addFormats(ajv, { mode: "full" });
    _validate = ajv.compile(SUBSCRIPTION_SCHEMA as unknown as Record<string, unknown>);
  }
  return _validate;
}

/** Validate a parsed webhook-subscription object against the published §Y subscription schema. */
export function validateSubscription(value: unknown): SubscriptionValidation {
  const validate = validator();
  if (validate(value)) return { valid: true, errors: [] };
  const errors = (validate.errors ?? []).map(
    (e) => `${e.instancePath || "/"} ${e.message ?? "invalid"}`,
  );
  return { valid: false, errors };
}
