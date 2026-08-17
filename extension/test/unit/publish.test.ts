import { describe, expect, test, vi } from "vitest";
import { hmacSha256Hex } from "openom-js";
import { envelopeText, publish, publishWithRetry, testFire } from "../../src/publish.js";

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

describe("publishWithRetry (#85) — bounded retry + backoff", () => {
  test("retries 5xx then succeeds; Event-Id stable, Delivery-Id changes per attempt", async () => {
    let n = 0;
    const seen: { eventId: string; deliveryId: string; attempt: string }[] = [];
    const send = vi.fn<typeof fetch>(async (_url, init) => {
      const h = (init?.headers ?? {}) as Record<string, string>;
      seen.push({ eventId: h["OpenOM-Event-Id"], deliveryId: h["OpenOM-Delivery-Id"], attempt: h["OpenOM-Delivery-Attempt"] });
      n++;
      return { status: n < 3 ? 503 : 200 } as Response;
    });
    let ids = 100;
    const r = await publishWithRetry(
      { ...base, event: "om.payload.published", send },
      { sleep: async () => {}, newDeliveryId: () => `d${ids++}` },
    );
    expect(r).toEqual({ status: 200, attempts: 3 });
    expect(new Set(seen.map((s) => s.eventId)).size).toBe(1); // Event-Id stable
    expect(new Set(seen.map((s) => s.deliveryId)).size).toBe(3); // Delivery-Id per attempt
    expect(seen.map((s) => s.attempt)).toEqual(["1", "2", "3"]);
  });

  test("does NOT retry a 4xx (final)", async () => {
    const send = vi.fn<typeof fetch>(async () => ({ status: 400 }) as Response);
    const r = await publishWithRetry({ ...base, event: "e", send }, { sleep: async () => {} });
    expect(r.attempts).toBe(1);
    expect(send).toHaveBeenCalledTimes(1);
  });
});
