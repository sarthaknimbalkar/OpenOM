// Consumer "Publish" — POST a §Y HMAC-signed, replay-protected envelope to a broker-configured
// receiver. Reuses the A /js webhook core; deterministic (clock/id injected). SSRF-guarded target.

import {
  assertSafeWebhookTarget,
  buildEnvelope,
  signHeaders,
  type Verification,
} from "openom-js";

export interface PublishArgs {
  event: string;
  sourceUrl: string;
  payload: Record<string, unknown>;
  payloadHash: string;
  verification: Verification;
  target: string;
  secret: string;
  now: Date;
  id: string;
  deliveryId: string;
  attempt?: number;
  send?: typeof fetch;
}

function envelopeAndBody(a: PublishArgs) {
  const envelope = buildEnvelope({
    event: a.event,
    sourceUrl: a.sourceUrl,
    payload: a.payload,
    payloadHash: a.payloadHash,
    verification: a.verification,
    now: a.now,
    id: a.id,
  });
  const rawBody = JSON.stringify(envelope);
  return { envelope, rawBody };
}

/** The exact text a "copy"/"download" action hands the user (== the bytes POSTed). */
export function envelopeText(a: PublishArgs): string {
  return envelopeAndBody(a).rawBody;
}

export async function publish(a: PublishArgs): Promise<{ status: number }> {
  assertSafeWebhookTarget(a.target); // throws on http/private/metadata → caller surfaces it
  const { envelope, rawBody } = envelopeAndBody(a);
  const t = Math.floor(a.now.getTime() / 1000);
  const headers = signHeaders({
    secret: a.secret,
    timestampUnix: t,
    rawBody,
    envelope,
    deliveryId: a.deliveryId,
    attempt: a.attempt ?? 1,
  });
  const send = a.send ?? fetch;
  const resp = await send(a.target, { method: "POST", headers, body: rawBody });
  return { status: resp.status };
}

/** Send a sample event so a broker can confirm their receiver + secret before going live. */
export async function testFire(a: Omit<PublishArgs, "event">): Promise<{ status: number }> {
  return publish({ ...a, event: "om.test.ping" });
}
