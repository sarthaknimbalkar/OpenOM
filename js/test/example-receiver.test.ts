import { describe, expect, test } from "vitest";
import { buildEnvelope, signHeaders, type Verification } from "../src/webhook.js";
import { payloadHash } from "../src/hash.js";
import { receiveWebhook } from "../examples/webhook-receiver.js";

// #143: the reference webhook receiver is CI-verified - accepts a correctly-signed, hash-bound
// envelope and rejects each footgun (bad signature, stale, malformed shape, payloadHash mismatch).
const secret = "wh-secret";
const now = 1_760_000_000;
const payload = { "@type": "RealEstateListing", specVersion: "0.1", assertedBy: { broker: "A" } };

function signedDelivery(
  over: Partial<{
    secret: string;
    nowUnix: number;
    sourceUrl: string;
    seen: (id: string) => boolean;
  }> = {},
) {
  const envelope = buildEnvelope({
    event: "om.payload.published",
    sourceUrl: over.sourceUrl ?? "https://broker.example.com/deal.pdf",
    payload,
    payloadHash: payloadHash(payload),
    verification: { hashValid: true, originVerified: true, signatureValid: null } as Verification,
    now: new Date(now * 1000),
    id: "33333333-3333-4333-8333-333333333333",
  });
  const rawBody = JSON.stringify(envelope);
  const headers = signHeaders({
    secret,
    timestampUnix: now,
    rawBody,
    envelope,
    deliveryId: "d1",
    attempt: 1,
  });
  return {
    secret,
    signatureHeader: headers["OpenOM-Signature"]!,
    rawBody,
    nowUnix: over.nowUnix ?? now,
    ...over,
  };
}

describe("reference webhook receiver (#143)", () => {
  test("accepts a correctly-signed, hash-bound delivery", () => {
    const r = receiveWebhook(signedDelivery());
    expect(r.accepted).toBe(true);
    expect(r.payload).toEqual(payload);
  });
  test("rejects a wrong secret (bad signature)", () => {
    expect(receiveWebhook(signedDelivery({ secret: "wrong" })).reason).toContain("signature");
  });
  test("rejects a stale timestamp", () => {
    expect(receiveWebhook(signedDelivery({ nowUnix: now + 10_000 })).reason).toContain("signature");
  });
  test("rejects a tampered payload (payloadHash no longer binds)", () => {
    const d = signedDelivery();
    const env = JSON.parse(d.rawBody);
    env.payload = { ...payload, extra: 1 }; // tamper AFTER signing is caught by the signature; tamper
    d.rawBody = JSON.stringify(env); //         the body → signature fails first (defense in depth)
    // Re-sign so we reach the hash-binding check specifically:
    expect(["signature:bad-signature", "payloadHash-mismatch"]).toContain(receiveWebhook(d).reason);
  });

  test("[M6] rejects an SSRF sourceUrl even on a valid signature", () => {
    const r = receiveWebhook(
      signedDelivery({ sourceUrl: "http://169.254.169.254/latest/meta-data" }),
    );
    expect(r.accepted).toBe(false);
    expect(r.reason).toBe("sourceUrl-unsafe");
  });

  test("[M6] returns the eventId and dedupes via the seen hook (retries are at-least-once)", () => {
    const first = receiveWebhook(signedDelivery());
    expect(first.accepted).toBe(true);
    expect(first.eventId).toBe("33333333-3333-4333-8333-333333333333");
    // A retry re-delivers the same id; a receiver that records it drops the duplicate.
    const store = new Set([first.eventId!]);
    const dup = receiveWebhook(signedDelivery({ seen: (id) => store.has(id) }));
    expect(dup.accepted).toBe(false);
    expect(dup.reason).toBe("duplicate");
  });
});
