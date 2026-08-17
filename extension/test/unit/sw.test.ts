import { describe, expect, test, vi } from "vitest";
import { integrityHashOfBytes, type ReadResult } from "openom-js";
import { handleDetect } from "../../src/service-worker.js";

const SRC = "https://broker.example.com/deal.pdf";
const BYTES = new Uint8Array([1, 2, 3]);
const MIRROR_BODY = new TextEncoder().encode('{"@type":"RealEstateListing","assertedDate":"2026-06-15"}');
const H = integrityHashOfBytes(MIRROR_BODY);

const readResult = (over: Partial<ReadResult>): ReadResult => ({
  state: "present",
  payload: { "@type": "RealEstateListing", assertedDate: "2026-06-15" },
  payloadHash: H,
  verification: { hashValid: true, originVerified: null, signatureValid: null },
  ...over,
});

describe("handleDetect — §AA pipeline", () => {
  test("absent when no bytes", async () => {
    const r = await handleDetect(SRC, { refetch: async () => null });
    expect(r.state).toBe("absent");
  });

  test("encrypted PDF → badge absent but a distinct 'encrypted' label + finding (#72)", async () => {
    const r = await handleDetect(SRC, {
      refetch: async () => BYTES,
      read: async () => readResult({ state: "encrypted", payload: null, payloadHash: null }),
    });
    expect(r.state).toBe("absent");
    expect(r.findings).toContain("encrypted");
    expect(r.label).toBe("Encrypted PDF");
    expect(r.caption.toLowerCase()).toContain("encrypted");
  });

  test("hash-mismatch is terminal (no origin fetch)", async () => {
    const mirrorFetch = vi.fn();
    const r = await handleDetect(SRC, {
      refetch: async () => BYTES,
      read: async () => readResult({ state: "hash-mismatch", verification: { hashValid: false, originVerified: null, signatureValid: null } }),
      mirrorFetch,
    });
    expect(r.state).toBe("hash-mismatch");
    expect(mirrorFetch).not.toHaveBeenCalled();
  });

  test("origin-verified when mirror matches on same domain", async () => {
    const r = await handleDetect(SRC, {
      refetch: async () => BYTES,
      read: async () => readResult({}),
      mirrorFetch: async () => ({ https: true, body: MIRROR_BODY }),
    });
    expect(r.state).toBe("origin-verified");
  });

  test("integrity-ok when mirror unreachable", async () => {
    const r = await handleDetect(SRC, {
      refetch: async () => BYTES,
      read: async () => readResult({}),
      mirrorFetch: async () => null,
    });
    expect(r.state).toBe("integrity-ok");
  });

  test("stale mirror → OMW-W051, badge held at integrity-ok (not downgraded)", async () => {
    const newerMirror = new TextEncoder().encode(
      '{"@type":"RealEstateListing","assertedDate":"2026-09-01","meta":{"supersedes":"' + H + '"}}',
    );
    const r = await handleDetect(SRC, {
      refetch: async () => BYTES,
      read: async () => readResult({}), // embedded hash = H
      mirrorFetch: async () => ({ https: true, body: newerMirror }), // mirror hash != H, newer
    });
    expect(r.state).toBe("integrity-ok");
    expect(r.findings).toContain("OMW-W051");
    expect(r.stale).toBe("OMW-W051");
  });

  test("sets the toolbar badge", async () => {
    const setBadge = vi.fn();
    await handleDetect(SRC, { refetch: async () => null, setBadge });
    expect(setBadge).toHaveBeenCalledWith("absent");
  });
});
