import { describe, expect, test } from "vitest";
import { hmacSha256Hex } from "../src/crypto.js";
import {
  assertSafeWebhookTarget,
  buildEnvelope,
  signHeaders,
  type Verification,
} from "../src/webhook.js";

const VERIF: Verification = { hashValid: true, originVerified: true, signatureValid: null };
const PAYLOAD = { "@type": "RealEstateListing", specVersion: "0.1" };

function env() {
  return buildEnvelope({
    event: "om.payload.published",
    sourceUrl: "https://broker.example.com/deal.pdf",
    payload: PAYLOAD,
    payloadHash: "sha256:" + "a".repeat(64),
    verification: VERIF,
    now: new Date("2026-08-17T12:00:00.000Z"),
    id: "11111111-1111-4111-8111-111111111111",
  });
}

describe("buildEnvelope (§Y)", () => {
  test("carries every required field", () => {
    const e = env();
    expect(e).toMatchObject({
      envelopeVersion: expect.any(String),
      event: "om.payload.published",
      id: "11111111-1111-4111-8111-111111111111",
      publishedAt: "2026-08-17T12:00:00.000Z",
      sourceUrl: "https://broker.example.com/deal.pdf",
      specVersion: "0.1",
      payloadHash: "sha256:" + "a".repeat(64),
      verification: VERIF,
      payload: PAYLOAD,
    });
  });
});

describe("signHeaders (§Y [OM-HOOK-003/005])", () => {
  test("signs the EXACT rawBody (no re-serialize) and sets all headers", () => {
    const e = env();
    const rawBody = '{"spaced":  "body"}'; // deliberately not JSON.stringify(e)
    const t = 1_755_432_000;
    const h = signHeaders({
      secret: "shh",
      timestampUnix: t,
      rawBody,
      envelope: e,
      deliveryId: "22222222-2222-4222-8222-222222222222",
      attempt: 1,
    });
    const expectedSig = hmacSha256Hex("shh", `${t}.${rawBody}`);
    expect(h["OpenOM-Signature"]).toBe(`t=${t},v1=${expectedSig}`);
    expect(h["OpenOM-Event"]).toBe("om.payload.published");
    expect(h["OpenOM-Event-Id"]).toBe(e.id); // stable across retries
    expect(h["OpenOM-Delivery-Id"]).toBe("22222222-2222-4222-8222-222222222222"); // per attempt
    expect(h["OpenOM-Delivery-Attempt"]).toBe("1");
    expect(h["OpenOM-Timestamp"]).toBe(String(t));
    expect(h["Content-Type"]).toBe("application/json");
  });
});

describe("assertSafeWebhookTarget (SSRF host/IP-literal bound)", () => {
  test.each([
    "http://hooks.example.com/x",
    "https://127.0.0.1/x",
    "https://10.0.0.1/x",
    "https://192.168.1.5/x",
    "https://169.254.169.254/x",
    "https://localhost/x",
    "https://foo.local/x",
    "https://metadata.google.internal/x",
  ])("rejects %s", (url) => {
    expect(() => assertSafeWebhookTarget(url)).toThrow();
  });

  test.each(["https://hooks.example.com/x", "https://8.8.8.8/x"])("accepts %s", (url) => {
    expect(() => assertSafeWebhookTarget(url)).not.toThrow();
  });
});
