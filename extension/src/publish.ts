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

export interface RetryOpts {
  maxAttempts?: number;
  sleep?: (ms: number) => Promise<void>;
  newDeliveryId?: () => string;
}

/**
 * Deliver with bounded retry + exponential backoff on RETRIABLE failures (5xx / network) — §Y is
 * built for this: the OpenOM-Event-Id stays stable across attempts (== envelope.id) while each retry
 * mints a fresh OpenOM-Delivery-Id and increments OpenOM-Delivery-Attempt ([#85]). 2xx/4xx are final.
 * The unsafe-target check runs ONCE up front (a bad target is not retriable).
 */
export async function publishWithRetry(
  a: PublishArgs,
  opts: RetryOpts = {},
): Promise<{ status: number; attempts: number }> {
  assertSafeWebhookTarget(a.target); // throws immediately; never retried
  const maxAttempts = opts.maxAttempts ?? 3;
  const sleep = opts.sleep ?? ((ms) => new Promise((r) => setTimeout(r, ms)));
  const newDeliveryId = opts.newDeliveryId ?? (() => crypto.randomUUID());

  let lastStatus = 0;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const deliveryId = attempt === 1 ? a.deliveryId : newDeliveryId();
    try {
      const { status } = await publish({ ...a, attempt, deliveryId });
      lastStatus = status;
      if (status < 500) return { status, attempts: attempt }; // 2xx/4xx: final
    } catch (e) {
      if (attempt === maxAttempts) throw e; // network error on the last try
    }
    if (attempt < maxAttempts) await sleep(250 * 2 ** (attempt - 1)); // 250ms, 500ms, …
  }
  return { status: lastStatus, attempts: maxAttempts };
}
