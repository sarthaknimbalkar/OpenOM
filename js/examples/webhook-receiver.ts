// Reference §Y webhook receiver (#143). The three checks below are the ones receivers most often get
// wrong; run them IN ORDER on every delivery, using only the openom-js primitives. Framework-agnostic:
// pass the raw request body TEXT (never a re-serialized object) + the OpenOM-Signature header.
// (A real consumer imports from "openom-js"; in-repo we import the workspace source.)
import {
  verifyWebhookSignature,
  validateEnvelope,
  verifyEnvelopePayloadHash,
} from "../src/index.js";

export interface Delivery {
  secret: string; // your configured signing secret
  signatureHeader: string; // the `OpenOM-Signature` request header value
  rawBody: string; // the EXACT received body bytes as text (do not JSON.parse then re-stringify)
  nowUnix: number; // seconds; for the replay-tolerance window
}

export interface ReceiveResult {
  accepted: boolean;
  reason: string;
  payload?: Record<string, unknown>;
}

/** Verify signature → validate envelope shape → verify payloadHash binds the payload → accept. */
export function receiveWebhook(d: Delivery): ReceiveResult {
  const sig = verifyWebhookSignature({
    rawBody: d.rawBody,
    signatureHeader: d.signatureHeader,
    secret: d.secret,
    nowUnix: d.nowUnix,
  });
  if (!sig.valid) return { accepted: false, reason: `signature:${sig.reason}` };

  let envelope: unknown;
  try {
    envelope = JSON.parse(d.rawBody);
  } catch {
    return { accepted: false, reason: "bad-json" };
  }

  const shape = validateEnvelope(envelope);
  if (!shape.valid) return { accepted: false, reason: `envelope:${shape.errors[0] ?? "invalid"}` };

  // Schema can't bind payloadHash to payload - a schema-valid envelope may still carry a mismatch.
  if (!verifyEnvelopePayloadHash(envelope))
    return { accepted: false, reason: "payloadHash-mismatch" };

  return {
    accepted: true,
    reason: "ok",
    payload: (envelope as { payload: Record<string, unknown> }).payload,
  };
}
