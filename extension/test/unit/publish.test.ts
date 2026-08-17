import { describe, expect, test, vi } from "vitest";
import { hmacSha256Hex } from "openom-js";
import { envelopeText, publish, testFire } from "../../src/publish.js";

const base = {
  sourceUrl: "https://broker.example.com/deal.pdf",
  payload: { "@type": "RealEstateListing", specVersion: "0.1" },
  payloadHash: "sha256:" + "a".repeat(64),
  verification: { hashValid: true, originVerified: true, signatureValid: null },
  target: "https://hooks.example.com/x",
  secret: "shh",
  now: new Date("2026-08-17T12:00:00.000Z"),
  id: "11111111-1111-4111-8111-111111111111",
  deliveryId: "22222222-2222-4222-8222-222222222222",
};

describe("publish (§Y)", () => {
  test("rejects an unsafe target before sending", async () => {
    const send = vi.fn();
    await expect(publish({ ...base, event: "e", target: "http://hooks.example.com/x", send })).rejects.toThrow();
    expect(send).not.toHaveBeenCalled();
  });

  test("POSTs the signed envelope; signature is HMAC over the exact body", async () => {
    let captured: { url: string; init: RequestInit } | null = null;
    const send = (async (url: string, init: RequestInit) => {
      captured = { url, init };
      return { status: 200 } as Response;
    }) as unknown as typeof fetch;

    const res = await publish({ ...base, event: "om.payload.published", send });
    expect(res.status).toBe(200);
    expect(captured!.url).toBe(base.target);
    const headers = captured!.init.headers as Record<string, string>;
    const t = Math.floor(base.now.getTime() / 1000);
    const rawBody = captured!.init.body as string;
    expect(headers["OpenOM-Signature"]).toBe(`t=${t},v1=${hmacSha256Hex("shh", `${t}.${rawBody}`)}`);
    expect(headers["OpenOM-Event-Id"]).toBe(base.id);
  });

  test("testFire uses the sample event", async () => {
    let body = "";
    const send = (async (_url: string, init: RequestInit) => {
      body = init.body as string;
      return { status: 202 } as Response;
    }) as unknown as typeof fetch;
    const res = await testFire({ ...base, send });
    expect(res.status).toBe(202);
    expect(JSON.parse(body).event).toBe("om.test.ping");
  });

  test("envelopeText is valid JSON with the §Y fields", () => {
    const e = JSON.parse(envelopeText({ ...base, event: "e" }));
    expect(e).toMatchObject({ event: "e", sourceUrl: base.sourceUrl, payloadHash: base.payloadHash });
  });
});
