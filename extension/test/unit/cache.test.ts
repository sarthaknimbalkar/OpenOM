import { beforeEach, describe, expect, test, vi } from "vitest";
import { getCachedDetect, setCachedDetect } from "../../src/cache.js";
import type { DetectResult } from "../../src/service-worker.js";

const RESULT = { state: "integrity-ok", label: "Unaltered", caption: "", sourceUrl: "u", payload: null, payloadHash: null, verification: { hashValid: true, originVerified: false, signatureValid: null }, findings: [] } as unknown as DetectResult;

beforeEach(() => {
  const store: Record<string, unknown> = {};
  (globalThis as unknown as { chrome: unknown }).chrome = {
    storage: {
      local: {
        get: async (k: string) => ({ [k]: store[k] }),
        set: async (o: Record<string, unknown>) => Object.assign(store, o),
      },
      sync: { set: vi.fn(), get: vi.fn() },
    },
  };
});

describe("detection cache (#68) - 24h TTL", () => {
  test("returns a fresh cached result, null once expired", async () => {
    await setCachedDetect("https://x/deal.pdf", RESULT, 1_000);
    expect(await getCachedDetect("https://x/deal.pdf", 1_000 + 60_000)).toEqual(RESULT); // within TTL
    expect(await getCachedDetect("https://x/deal.pdf", 1_000 + 25 * 3600 * 1000)).toBeNull(); // expired
  });
  test("miss for an uncached URL", async () => {
    expect(await getCachedDetect("https://y/other.pdf", 0)).toBeNull();
  });
});
