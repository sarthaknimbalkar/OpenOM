import { describe, expect, test } from "vitest";
import { hmacSha256Hex } from "../src/crypto.js";
import {
  assertSafeWebhookTarget,
  buildEnvelope,
  signHeaders,
  verifyWebhookSignature,
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

  // #79 — every encoding of 127.0.0.1 / private / metadata that a browser still resolves.
  test.each([
    "https://2130706433/x", // dword-decimal 127.0.0.1
    "https://0x7f000001/x", // hex 127.0.0.1
    "https://0x7f.0.0.1/x", // mixed hex
    "https://0177.0.0.1/x", // octal 127
    "https://127.1/x", // short form
    "https://0.0.0.0/x", // unspecified
    "https://[::1]/x", // IPv6 loopback
    "https://[::ffff:127.0.0.1]/x", // IPv4-mapped IPv6
    "https://[::ffff:7f00:1]/x", // IPv4-mapped IPv6 (hex)
    "https://[fd00::1]/x", // ULA
    "https://[fe80::1]/x", // link-local
    "https://2852039166/x", // dword 169.254.169.254 (metadata)
  ])("rejects encoded/mapped literal %s (#79)", (url) => {
    expect(() => assertSafeWebhookTarget(url)).toThrow();
  });
});

describe("verifyWebhookSignature (§Y receiver, #78)", () => {
  const secret = "shh";
  const rawBody = '{"event":"om.payload.published"}';
  const t = 1_755_432_000;
  const good = `t=${t},v1=${hmacSha256Hex(secret, `${t}.${rawBody}`)}`;

  test("accepts a valid signature within the tolerance window", () => {
    expect(
      verifyWebhookSignature({ rawBody, signatureHeader: good, secret, nowUnix: t + 10 }),
    ).toEqual({
      valid: true,
      reason: "ok",
    });
  });
  test("rejects a tampered body", () => {
    const r = verifyWebhookSignature({
      rawBody: rawBody + " ",
      signatureHeader: good,
      secret,
      nowUnix: t,
    });
    expect(r).toEqual({ valid: false, reason: "bad-signature" });
  });
  test("rejects a wrong secret", () => {
    expect(
      verifyWebhookSignature({ rawBody, signatureHeader: good, secret: "nope", nowUnix: t }).valid,
    ).toBe(false);
  });
  test("rejects a replay outside the tolerance window", () => {
    expect(
      verifyWebhookSignature({ rawBody, signatureHeader: good, secret, nowUnix: t + 3600 }),
    ).toEqual({
      valid: false,
      reason: "stale",
    });
  });
  test("rejects a malformed header", () => {
    expect(
      verifyWebhookSignature({ rawBody, signatureHeader: "garbage", secret, nowUnix: t }).reason,
    ).toBe("malformed-header");
  });
});
