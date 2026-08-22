// Reference §Y webhook receiver (#143). The three checks below are the ones receivers most often get
// wrong; run them IN ORDER on every delivery, using only the openom-js primitives. Framework-agnostic:
// pass the raw request body TEXT (never a re-serialized object) + the OpenOM-Signature header.
// (A real consumer imports from "openom-js"; in-repo we import the workspace source.)
import {
  verifyWebhookSignature,
  validateEnvelope,
  verifyEnvelopePayloadHash,
  assertSafeUrl,
} from "../src/index.js";

export interface Delivery {
  secret: string; // your configured signing secret
  signatureHeader: string; // the `OpenOM-Signature` request header value
  rawBody: string; // the EXACT received body bytes as text (do not JSON.parse then re-stringify)
  nowUnix: number; // seconds; for the replay-tolerance window
  /**
   * [M6] Idempotency hook: return true if you've already processed this OpenOM-Event-Id. Retries
   * re-deliver the SAME event id (at-least-once), so WITHOUT this a portal double-applies every
   * re-price. If you provide it, also persist the id (see the returned `eventId`) after you ingest.
   */
  seen?: (eventId: string) => boolean;
}

export interface ReceiveResult {
  accepted: boolean;
  reason: string;
  payload?: Record<string, unknown>;
  /** The event id ([OM-Event-Id]); record it to dedupe future retries. */
  eventId?: string;
}

/**
 * Verify signature → validate envelope shape → verify payloadHash binds the payload → guard sourceUrl →
 * dedupe → accept. [M6] `sourceUrl` is attacker-controlled data even on a valid signature (the signer
 * only proves it holds the shared secret), so it is re-checked with assertSafeUrl before a receiver
 * would ever fetch it; and delivery is at-least-once, so an optional `seen` hook drops duplicate event
 * ids. The envelope's `verification.*` is the SENDER's self-report - a receiver MUST recompute its own
 * (this function recomputes signature + payloadHash) and MUST NOT surface the sender's claims as its
 * own trust state.
 */
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

  const env = envelope as { sourceUrl: string; id: string; payload: Record<string, unknown> };

  // [M6] SSRF guard: refuse before anything downstream fetches sourceUrl (metadata IP, internal host…).
  try {
    assertSafeUrl(env.sourceUrl);
  } catch {
    return { accepted: false, reason: "sourceUrl-unsafe", eventId: env.id };
  }

  // [M6] idempotency: retries re-deliver the same event id; skip a duplicate if the caller tracks them.
  if (d.seen?.(env.id)) return { accepted: false, reason: "duplicate", eventId: env.id };

  return { accepted: true, reason: "ok", payload: env.payload, eventId: env.id };
}
