import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, test } from "vitest";
import { embedPayload } from "openom-js";
import { PDFDocument } from "pdf-lib";
import worker from "../src/index.js";

function toB64(b: Uint8Array): string {
  let s = "";
  for (const x of b) s += String.fromCharCode(x);
  return btoa(s);
}

const validPayload = JSON.parse(
  readFileSync(join(__dirname, "..", "..", "spec", "samples", "valid-stnl.json"), "utf8"),
);

function post(body: unknown): Request {
  return new Request("https://mcp.openom.app/mcp", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("worker dispatch + [M5] JSON-RPC batch", () => {
  test("a batch array returns an array of responses (notifications omitted)", async () => {
    const res = await worker.fetch(
      post([
        { jsonrpc: "2.0", id: 1, method: "initialize" },
        { jsonrpc: "2.0", method: "notifications/initialized" }, // no response expected
        { jsonrpc: "2.0", id: 2, method: "tools/call", params: { name: "om_validate", arguments: { payload: validPayload } } },
        { jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "om_validate", arguments: { payload: {} } } },
      ]),
    );
    const arr = (await res.json()) as Array<{ id: unknown; result?: { structuredContent?: { blocked?: boolean } } }>;
    expect(Array.isArray(arr)).toBe(true);
    expect(arr).toHaveLength(3); // the notification produced no response
    expect(arr.find((r) => r.id === 1)?.result).toBeTruthy();
    expect(arr.find((r) => r.id === 2)?.result?.structuredContent?.blocked).toBe(false); // valid
    expect(arr.find((r) => r.id === 3)?.result?.structuredContent?.blocked).toBe(true); // empty → errors
  });

  test("an empty batch is a JSON-RPC error", async () => {
    const res = await worker.fetch(post([]));
    const j = (await res.json()) as { error?: { code: number } };
    expect(j.error?.code).toBe(-32600);
  });

  test("[M5] an over-large batch is rejected (bounded fan-out)", async () => {
    const big = Array.from({ length: 21 }, (_, i) => ({ jsonrpc: "2.0", id: i, method: "ping" }));
    const res = await worker.fetch(post(big));
    const j = (await res.json()) as { error?: { code: number; message: string } };
    expect(j.error?.code).toBe(-32600);
    expect(j.error?.message).toMatch(/batch too large/);
  });

  test("[polish] om_read surfaces consistency warnings on a present payload (no 2nd round-trip)", async () => {
    // Inconsistent-but-schema-valid: capRate doesn't match NOI/price → an OMW-W0xx consistency warning.
    const inconsistent = { ...validPayload, deal: { ...validPayload.deal, capRate: 0.02 } };
    const doc = await PDFDocument.create();
    doc.addPage([200, 200]);
    const embedded = await embedPayload(new Uint8Array(await doc.save()), inconsistent);
    const res = await worker.fetch(
      post({
        jsonrpc: "2.0", id: 1, method: "tools/call",
        params: { name: "om_read", arguments: { pdfBase64: toB64(embedded) } },
      }),
    );
    const j = (await res.json()) as { result: { structuredContent: { state: string; warnings?: { code: string }[] } } };
    expect(j.result.structuredContent.state).toBe("present");
    expect((j.result.structuredContent.warnings ?? []).length).toBeGreaterThan(0);
  });

  test("a single request still works (initialize)", async () => {
    const res = await worker.fetch(post({ jsonrpc: "2.0", id: 9, method: "initialize" }));
    const j = (await res.json()) as { id: number; result?: { serverInfo?: unknown } };
    expect(j.id).toBe(9);
    expect(j.result?.serverInfo).toBeTruthy();
  });

  test("[polish] rate limiter (when bound) returns 429 + Retry-After; absent binding = no limit", async () => {
    const denyEnv = { RATE_LIMITER: { limit: async () => ({ success: false }) } };
    const res = await worker.fetch(post({ jsonrpc: "2.0", id: 1, method: "ping" }), denyEnv);
    expect(res.status).toBe(429);
    expect(res.headers.get("Retry-After")).toBe("60");
    // No binding (local/tests) → limiter skipped, request proceeds.
    const ok = await worker.fetch(post({ jsonrpc: "2.0", id: 2, method: "ping" }));
    expect(ok.status).toBe(200);
  });
});
